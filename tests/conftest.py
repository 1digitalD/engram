import os
import pathlib
import random
import threading
import time
from unittest.mock import patch

import pytest

from app import create_app
from extensions import db

SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[1] / "docs" / "SCHEMA.sql"

# Session-level lock to prevent overlapping schema setup/truncate within one
# pytest process.
_schema_lock = threading.Lock()

_TRUNCATE_MAX_RETRIES = 5
_TRUNCATE_BASE_DELAY_SECONDS = 0.1
_TRUNCATE_STATEMENT_TIMEOUT_SECONDS = 5


@pytest.fixture(scope="session")
def app():
    """Session-scoped Flask app with schema applied once at session start."""
    try:
        from services import job_worker

        job_worker._stop_event.set()
        if job_worker._worker_thread is not None:
            job_worker._worker_thread.join(timeout=2)
        job_worker._worker_thread = None
        job_worker._worker_app = None
        job_worker._stop_event = threading.Event()
    except Exception:
        pass

    app = create_app("testing")
    with app.app_context():
        _apply_schema()
        yield app

    try:
        from services.job_worker import stop_worker

        stop_worker(timeout=2)
    except Exception:
        pass


def _assert_not_production_db(url):
    """Fail fast if TEST_DATABASE_URL points at the production database."""
    normalized = (url or "").lower()
    if "5432/engram" in normalized and "engram_test" not in normalized:
        raise RuntimeError(
            "FATAL: TEST_DATABASE_URL points at the production 'engram' database.\n"
            f"URL: {url}\n"
            "This would truncate all production data.\n"
            "Set TEST_DATABASE_URL to the isolated test database.\n"
            "Hint: postgresql://engram:engram@localhost:5433/engram_test"
        )


def _connect_test_db(url):
    """Open a fresh psycopg2 connection to the test database."""
    import psycopg2

    _assert_not_production_db(url)
    conn = psycopg2.connect(url)
    conn.autocommit = True
    return conn


def _set_statement_timeout(cur, seconds):
    """Set a per-statement timeout so lock waits cannot hang forever."""
    cur.execute(f"SET LOCAL statement_timeout = '{int(seconds * 1000)}ms'")


def _reset_public_schema(cur):
    """Drop and recreate public schema so table-owned types also reset."""
    cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
    cur.execute("CREATE SCHEMA public")


def _truncate_all_tables(url):
    """Call truncate_all_tables() with bounded retries."""
    import psycopg2

    last_error = None
    conn = _connect_test_db(url)
    try:
        for attempt in range(1, _TRUNCATE_MAX_RETRIES + 1):
            try:
                with conn.cursor() as cur:
                    _set_statement_timeout(cur, _TRUNCATE_STATEMENT_TIMEOUT_SECONDS)
                    cur.execute("SELECT truncate_all_tables()")
                return
            except (
                psycopg2.errors.DeadlockDetected,
                psycopg2.errors.LockNotAvailable,
            ) as exc:
                last_error = exc
                try:
                    conn.close()
                except Exception:
                    pass
                conn = _connect_test_db(url)
                if attempt < _TRUNCATE_MAX_RETRIES:
                    delay = (_TRUNCATE_BASE_DELAY_SECONDS * (2 ** (attempt - 1))) + random.uniform(0, 0.1)
                    time.sleep(delay)
        raise RuntimeError(
            f"truncate_all_tables() failed after {_TRUNCATE_MAX_RETRIES} attempts: {last_error}"
        ) from last_error
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _apply_schema():
    """Apply docs/SCHEMA.sql to the test database via a raw connection."""
    sql = SCHEMA_PATH.read_text()
    url = os.environ.get("TEST_DATABASE_URL")

    with _schema_lock:
        conn = _connect_test_db(url)
        try:
            with conn.cursor() as cur:
                _set_statement_timeout(cur, 30)
                _reset_public_schema(cur)
                cur.execute(sql)
        finally:
            conn.close()


@pytest.fixture(scope="session")
def _db(app):
    """Session-scoped database handle. Keeps the app context alive."""
    yield db


@pytest.fixture(autouse=True)
def reset_db(app, _db):
    """Truncate all tables for test isolation."""
    url = os.environ.get("TEST_DATABASE_URL")
    with _schema_lock:
        db.session.remove()
        _truncate_all_tables(url)
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def mock_embed():
    """Mock OpenAI embeddings and return a zero vector."""
    with patch("services.embeddings._embed_texts") as mock:
        mock.return_value = [[0.0] * 1536]
        yield mock
