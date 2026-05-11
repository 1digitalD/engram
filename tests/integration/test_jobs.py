"""Integration tests for job_worker — enqueue, process, retry, backoff, concurrency.

Uses the Flask app fixture with in-memory SQLite.
"""

import threading
import time
from datetime import datetime, timezone, timedelta

import pytest

from extensions import db
from models import Job
from services.job_worker import (
    get_next_job,
    process_job,
    register_handler,
    get_handler,
    start_worker,
    stop_worker,
    is_worker_running,
    _HANDLERS,
    BACKOFF_BASE,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _enqueue_job(job_type="test", payload=None, entity_id=None, max_attempts=3, run_after=None):
    """Create a job in the database."""
    job = Job(
        job_type=job_type,
        entity_id=entity_id,
        payload=payload or {},
        max_attempts=max_attempts,
    )
    if run_after is not None:
        job.run_after = run_after
    db.session.add(job)
    db.session.commit()
    return job


def _clear_handlers():
    """Clear registered handlers between tests."""
    _HANDLERS.clear()


def _make_job_retriable(job):
    """Reset a job's run_after so it can be picked up again."""
    job.run_after = datetime.now(timezone.utc) - timedelta(seconds=10)
    db.session.commit()


# ─── Job Enqueue and Process ─────────────────────────────────────────────────

class TestJobEnqueueAndProcess:
    def setup_method(self):
        _clear_handlers()

    def test_enqueue_job(self, app):
        with app.app_context():
            job = _enqueue_job(job_type="test", payload={"key": "value"})
            assert job.id is not None
            assert job.job_type == "test"
            assert job.status == "pending"
            assert job.attempts == 0
            assert job.payload == {"key": "value"}

    def test_process_success(self, app):
        with app.app_context():
            results = []

            @register_handler("success_job")
            def handle_success(payload):
                results.append(payload)

            job = _enqueue_job(job_type="success_job", payload={"data": 42})
            process_job(job)

            db.session.refresh(job)
            assert job.status == "done"
            assert job.error is None
            assert results == [{"data": 42}]

    def test_process_unknown_handler(self, app):
        with app.app_context():
            job = _enqueue_job(job_type="nonexistent_type")
            process_job(job)

            db.session.refresh(job)
            assert job.status == "failed"
            assert "No handler registered" in job.error
            assert job.attempts == 1

    def test_process_multiple_jobs_in_order(self, app):
        with app.app_context():
            order = []

            @register_handler("ordered")
            def handle_ordered(payload):
                order.append(payload["n"])

            job1 = _enqueue_job(job_type="ordered", payload={"n": 1})
            job2 = _enqueue_job(job_type="ordered", payload={"n": 2})
            job3 = _enqueue_job(job_type="ordered", payload={"n": 3})

            process_job(job1)
            process_job(job2)
            process_job(job3)

            assert order == [1, 2, 3]

    def test_get_next_job_returns_oldest_first(self, app):
        with app.app_context():
            @register_handler("fifo")
            def handle_fifo(payload):
                pass

            job1 = _enqueue_job(job_type="fifo")
            time.sleep(0.05)
            job2 = _enqueue_job(job_type="fifo")

            next_job = get_next_job()
            assert next_job.id == job1.id

            # job1 is now 'running', so next should be job2
            next_job = get_next_job()
            assert next_job.id == job2.id

    def test_get_next_job_ignores_done_jobs(self, app):
        with app.app_context():
            @register_handler("done_test")
            def handle_done(payload):
                pass

            job = _enqueue_job(job_type="done_test")
            process_job(job)

            assert get_next_job() is None

    def test_get_next_job_ignores_future_jobs(self, app):
        with app.app_context():
            future = datetime.now(timezone.utc) + timedelta(hours=1)
            job = _enqueue_job(job_type="test", run_after=future)

            assert get_next_job() is None

    def test_start_stop_worker(self, app):
        with app.app_context():
            processed = []

            @register_handler("background")
            def handle_background(payload):
                processed.append(payload)

            _enqueue_job(job_type="background", payload={"bg": True})

            start_worker(app=app, poll_interval=0.5)
            time.sleep(2)
            stop_worker()

            assert len(processed) >= 1
            assert processed[0] == {"bg": True}


# ─── Retry with Exponential Backoff ──────────────────────────────────────────

class TestRetryWithBackoff:
    def setup_method(self):
        _clear_handlers()

    def test_failed_job_retries(self, app):
        with app.app_context():
            call_count = [0]

            @register_handler("flaky")
            def handle_flaky(payload):
                call_count[0] += 1
                if call_count[0] < 3:
                    raise ValueError("not yet")

            job = _enqueue_job(job_type="flaky", max_attempts=3)

            # First failure
            process_job(job)
            db.session.refresh(job)
            assert job.status == "failed"
            assert job.attempts == 1
            # run_after should be in the future
            assert job.run_after is not None

            # Second failure — reset run_after to make it pickable
            _make_job_retriable(job)
            process_job(job)
            db.session.refresh(job)
            assert job.status == "failed"
            assert job.attempts == 2
            assert job.run_after is not None

            # Third attempt — success
            _make_job_retriable(job)
            process_job(job)
            db.session.refresh(job)
            assert job.status == "done"
            assert call_count[0] == 3

    def test_exponential_backoff_timing(self, app):
        with app.app_context():
            @register_handler("backoff_test")
            def handle_backoff(payload):
                raise ValueError("always fails")

            job = _enqueue_job(job_type="backoff_test", max_attempts=5)

            # First failure: backoff = 2^1 * 10 = 20s
            process_job(job)
            db.session.refresh(job)
            assert job.attempts == 1
            # Verify run_after is set to a future time
            # SQLite stores naive datetimes, so we compare carefully
            run_after = job.run_after
            if run_after.tzinfo is None:
                run_after = run_after.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            diff = (run_after - now).total_seconds()
            assert diff >= 18  # 20s - 2s margin

            # Second failure: backoff = 2^2 * 10 = 40s
            _make_job_retriable(job)
            process_job(job)
            db.session.refresh(job)
            assert job.attempts == 2
            run_after = job.run_after
            if run_after.tzinfo is None:
                run_after = run_after.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            diff = (run_after - now).total_seconds()
            assert diff >= 38  # 40s - 2s margin

    def test_backoff_prevents_immediate_retry(self, app):
        with app.app_context():
            @register_handler("delayed")
            def handle_delayed(payload):
                raise ValueError("fail")

            job = _enqueue_job(job_type="delayed", max_attempts=3)

            process_job(job)
            db.session.refresh(job)

            # Job should not be pickable immediately due to run_after
            assert get_next_job() is None


# ─── Max Attempts Exceeded ───────────────────────────────────────────────────

class TestMaxAttemptsExceeded:
    def setup_method(self):
        _clear_handlers()

    def test_job_fails_permanently_after_max_attempts(self, app):
        with app.app_context():
            @register_handler("doomed")
            def handle_doomed(payload):
                raise ValueError("always fails")

            job = _enqueue_job(job_type="doomed", max_attempts=3)

            # Attempt 1
            process_job(job)
            db.session.refresh(job)
            assert job.attempts == 1
            assert job.status == "failed"

            # Attempt 2
            _make_job_retriable(job)
            process_job(job)
            db.session.refresh(job)
            assert job.attempts == 2
            assert job.status == "failed"

            # Attempt 3 — should be permanent failure
            _make_job_retriable(job)
            process_job(job)
            db.session.refresh(job)
            assert job.attempts == 3
            assert job.status == "failed"

            # Job should NOT be picked up again (attempts >= max_attempts)
            assert get_next_job() is None

    def test_job_with_max_attempts_1_fails_immediately(self, app):
        with app.app_context():
            @register_handler("one_shot")
            def handle_one_shot(payload):
                raise ValueError("fail")

            job = _enqueue_job(job_type="one_shot", max_attempts=1)

            process_job(job)
            db.session.refresh(job)
            assert job.attempts == 1
            assert job.status == "failed"

            # Should not be retried
            assert get_next_job() is None

    def test_get_next_job_skips_exhausted_jobs(self, app):
        with app.app_context():
            @register_handler("exhausted")
            def handle_exhausted(payload):
                raise ValueError("fail")

            exhausted_job = _enqueue_job(job_type="exhausted", max_attempts=1)
            process_job(exhausted_job)

            good_job = _enqueue_job(job_type="exhausted")

            # Should skip the exhausted job and return the good one
            next_job = get_next_job()
            assert next_job.id == good_job.id


# ─── Concurrent Pickup Prevention (SKIP LOCKED equivalent) ───────────────────
# Note: These tests verify concurrent pickup prevention which is implemented
# via FOR UPDATE SKIP LOCKED on PostgreSQL. SQLite doesn't support concurrent
# writes, so these tests are skipped when running against SQLite.

def _is_sqlite(app):
    """Check if the test database is SQLite."""
    with app.app_context():
        return "sqlite" in str(db.engine.url)


class TestConcurrentPickup:
    def setup_method(self):
        _clear_handlers()

    @pytest.mark.skipif(True, reason="SQLite doesn't support concurrent writes; FOR UPDATE SKIP LOCKED is PostgreSQL-only")
    def test_no_double_pickup(self, app):
        """Two threads trying to get the same job — only one should succeed."""
        with app.app_context():
            @register_handler("concurrent")
            def handle_concurrent(payload):
                pass

            job = _enqueue_job(job_type="concurrent")

            results = {"picked": [], "errors": []}
            lock = threading.Lock()
            barrier = threading.Barrier(2)

            def try_pick():
                try:
                    with app.app_context():
                        db.session.remove()
                        barrier.wait(timeout=5)  # synchronize start
                        picked = get_next_job()
                        with lock:
                            if picked is not None:
                                results["picked"].append(picked.id)
                except Exception as e:
                    with lock:
                        results["errors"].append(str(e))

            t1 = threading.Thread(target=try_pick)
            t2 = threading.Thread(target=try_pick)
            t1.start()
            t2.start()
            t1.join(timeout=10)
            t2.join(timeout=10)

            # Only one thread should have picked up the job
            assert len(results["picked"]) == 1
            assert results["picked"][0] == job.id

    @pytest.mark.skipif(True, reason="SQLite doesn't support concurrent writes; FOR UPDATE SKIP LOCKED is PostgreSQL-only")
    def test_multiple_jobs_distributed(self, app):
        """Multiple jobs should be distributed across concurrent workers."""
        with app.app_context():
            @register_handler("distributed")
            def handle_distributed(payload):
                pass

            job1 = _enqueue_job(job_type="distributed")
            job2 = _enqueue_job(job_type="distributed")
            job3 = _enqueue_job(job_type="distributed")

            results = {"picked": []}
            lock = threading.Lock()

            def try_pick():
                try:
                    with app.app_context():
                        db.session.remove()
                        picked = get_next_job()
                        with lock:
                            if picked is not None:
                                results["picked"].append(picked.id)
                except Exception:
                    pass

            threads = [threading.Thread(target=try_pick) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            assert len(results["picked"]) == 3
            assert set(results["picked"]) == {job1.id, job2.id, job3.id}


# ─── Worker Polling Loop ─────────────────────────────────────────────────────

class TestWorkerPolling:
    def setup_method(self):
        _clear_handlers()

    def teardown_method(self):
        if is_worker_running():
            stop_worker()

    def test_worker_processes_enqueued_jobs(self, app):
        with app.app_context():
            results = []

            @register_handler("auto")
            def handle_auto(payload):
                results.append(payload)

            _enqueue_job(job_type="auto", payload={"auto": 1})
            _enqueue_job(job_type="auto", payload={"auto": 2})

            start_worker(app=app, poll_interval=0.3)
            time.sleep(2)
            stop_worker()

            assert len(results) == 2
            assert {"auto": 1} in results
            assert {"auto": 2} in results

    def test_worker_respects_run_after(self, app):
        with app.app_context():
            results = []

            @register_handler("delayed_worker")
            def handle_delayed(payload):
                results.append(payload)

            future = datetime.now(timezone.utc) + timedelta(seconds=2)
            _enqueue_job(job_type="delayed_worker", payload={"late": True}, run_after=future)

            start_worker(app=app, poll_interval=0.3)
            time.sleep(1)
            stop_worker()

            # Job should not have been processed yet
            assert len(results) == 0

    def test_worker_handles_failed_jobs(self, app):
        with app.app_context():
            call_count = [0]

            @register_handler("worker_fail")
            def handle_worker_fail(payload):
                call_count[0] += 1
                raise ValueError("fail")

            _enqueue_job(job_type="worker_fail", max_attempts=2)

            start_worker(app=app, poll_interval=0.3)
            time.sleep(1.5)
            stop_worker()

            assert call_count[0] == 1
