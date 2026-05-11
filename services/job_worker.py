"""Job worker — polling loop with FOR UPDATE SKIP LOCKED and exponential backoff.

Runs as a background thread. Polls the jobs table, picks up pending/failed jobs,
executes registered handlers, and marks them done or schedules retries.

Usage:
    from services.job_worker import start_worker, stop_worker, register_handler

    @register_handler('my_job_type')
    def handle_my_job(payload):
        ...

    start_worker(app)  # starts background thread
    ...
    stop_worker()   # graceful shutdown
"""

import logging
import threading
import time
from datetime import datetime, timezone, timedelta

from extensions import db
from models import Job

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────

POLL_INTERVAL = 5  # seconds between queue polls
BACKOFF_BASE = 10  # base seconds for exponential backoff

# ─── Handler Registry ────────────────────────────────────────────────────────

_HANDLERS = {}


def register_handler(job_type):
    """Decorator to register a function as a handler for a job type.

    Example:
        @register_handler('classify')
        def handle_classify(payload):
            ...
    """
    def decorator(func):
        _HANDLERS[job_type] = func
        return func
    return decorator


def get_handler(job_type):
    """Get the registered handler for a job type, or None."""
    return _HANDLERS.get(job_type)


# ─── Job Queue Operations ────────────────────────────────────────────────────

def _is_postgres():
    """Check if the current database is PostgreSQL."""
    return "postgresql" in str(db.engine.url) or "postgres" in str(db.engine.url)


def get_next_job():
    """Fetch the next available job, locking it to prevent double-pickup.

    Uses FOR UPDATE SKIP LOCKED on PostgreSQL for true concurrent safety.
    Falls back to atomic status update on SQLite (test mode).

    Returns the Job model instance, or None if no jobs are available.
    """
    now = datetime.now(timezone.utc)

    if _is_postgres():
        return _get_next_job_postgres(now)
    else:
        return _get_next_job_sqlite(now)


def _get_next_job_postgres(now):
    """PostgreSQL implementation using FOR UPDATE SKIP LOCKED."""
    result = db.session.execute(
        db.text("""
            SELECT id FROM jobs
            WHERE status IN ('pending', 'failed')
              AND attempts < max_attempts
              AND run_after <= :now
            ORDER BY run_after ASC, created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """),
        {"now": now},
    )
    row = result.fetchone()
    if row is None:
        return None

    job = Job.query.get(row.id)
    if job is None:
        return None

    job.status = "running"
    db.session.commit()
    return job


def _get_next_job_sqlite(now):
    """SQLite fallback — atomic UPDATE with subquery to prevent double-pickup.

    Uses a single UPDATE statement that both selects and claims the job,
    making it atomic even under SQLite's single-writer model.
    """
    with db.engine.begin() as conn:
        # Single atomic statement: find and claim in one operation
        result = conn.execute(
            db.text("""
                UPDATE jobs SET status = 'running'
                WHERE id = (
                    SELECT id FROM jobs
                    WHERE status IN ('pending', 'failed')
                      AND attempts < max_attempts
                      AND run_after <= :now
                    ORDER BY run_after ASC, created_at ASC
                    LIMIT 1
                )
            """),
            {"now": now},
        )

        if result.rowcount == 0:
            return None

        # Fetch the claimed job id
        claimed = conn.execute(
            db.text("""
                SELECT id FROM jobs WHERE status = 'running'
                ORDER BY updated_at DESC LIMIT 1
            """),
        )
        row = claimed.fetchone()
        if row is None:
            return None

        job_id = row.id

    return db.session.get(Job, job_id)


# ─── Job Processing ──────────────────────────────────────────────────────────

def process_job(job):
    """Execute a job by looking up its handler and running it.

    On success: marks the job as 'done'.
    On failure: increments attempts, sets error, schedules retry with
    exponential backoff, or marks as 'failed' if past max_attempts.
    """
    handler = get_handler(job.job_type)

    if handler is None:
        job.status = "failed"
        job.error = f"No handler registered for job type: {job.job_type}"
        job.attempts += 1
        db.session.commit()
        logger.warning("Job %s: %s", job.id, job.error)
        return

    try:
        handler(job.payload)
        job.status = "done"
        job.error = None
        db.session.commit()
        logger.info("Job %s (%s) completed successfully", job.id, job.job_type)

    except Exception as e:
        job.attempts += 1
        job.error = str(e)

        if job.attempts >= job.max_attempts:
            job.status = "failed"
            logger.error(
                "Job %s (%s) failed permanently after %d attempts: %s",
                job.id, job.job_type, job.attempts, job.error,
            )
        else:
            job.status = "failed"
            backoff_seconds = (2 ** job.attempts) * BACKOFF_BASE
            job.run_after = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
            logger.warning(
                "Job %s (%s) failed (attempt %d/%d), retrying in %ds: %s",
                job.id, job.job_type, job.attempts, job.max_attempts,
                backoff_seconds, job.error,
            )

        db.session.commit()


# ─── Polling Loop ────────────────────────────────────────────────────────────

_worker_thread = None
_stop_event = threading.Event()
_worker_app = None


def _poll_loop(poll_interval=None):
    """Main polling loop — runs in a background thread."""
    interval = poll_interval if poll_interval is not None else POLL_INTERVAL
    logger.info("Job worker started (poll interval: %ds)", interval)

    while not _stop_event.is_set():
        try:
            # Background threads need their own app context
            with _worker_app.app_context():
                job = get_next_job()

                if job is None:
                    _stop_event.wait(interval)
                    continue

                process_job(job)

        except Exception:
            logger.exception("Job worker error in poll loop")
            _stop_event.wait(1)

    logger.info("Job worker stopped")


def start_worker(app=None, poll_interval=None, blocking=False):
    """Start the job worker background thread.

    Args:
        app: Flask app instance (required for background mode).
        poll_interval: Override default poll interval in seconds.
        blocking: If True, run the poll loop in the current thread (for testing).
    """
    global _worker_thread, _stop_event, _worker_app

    if app is not None:
        _worker_app = app
    elif _worker_app is None:
        from flask import current_app
        _worker_app = current_app._get_current_object()

    _stop_event.clear()

    if blocking:
        _poll_loop(poll_interval=poll_interval)
    else:
        _worker_thread = threading.Thread(
            target=_poll_loop,
            kwargs={"poll_interval": poll_interval},
            daemon=True,
            name="job-worker",
        )
        _worker_thread.start()


def stop_worker(timeout=10):
    """Signal the job worker to stop and wait for it to finish."""
    _stop_event.set()
    if _worker_thread is not None:
        _worker_thread.join(timeout=timeout)


def is_worker_running():
    """Check if the worker thread is alive."""
    return _worker_thread is not None and _worker_thread.is_alive()
