import pathlib
import random
import re
import threading
import time

import pytest
from unittest.mock import patch

from app import create_app
from extensions import db

SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[1] / "docs" / "SCHEMA.sql"

# Session-level lock to prevent concurrent schema apply / truncate within this process.
# The truncate path also sets a per-statement timeout and retries with bounded
# exponential backoff, so a slow or blocking peer fails fast instead of hanging
# the whole suite.
_schema_lock = threading.Lock()

# Bounded retry settings for the deadlock-prone truncate path.
_TRUNCATE_MAX_RETRIES = 5
_TRUNCATE_BASE_DELAY_SECONDS = 0.1
_TRUNCATE_STATEMENT_TIMEOUT_SECONDS = 5


@pytest.fixture(scope="session")
def app():
    """Session-scoped Flask app. Schema is applied once at session start."""
    # Stop any lingering worker from previous sessions and fully reset state
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
        _apply_schema(app)
    yield app

    # Clean up worker on session teardown
    try:
        from services.job_worker import stop_worker
        stop_worker(timeout=2)
    except Exception:
        pass


def _assert_not_production_db(url):
    """Fail fast if TEST_DATABASE_URL resolves to the production 'engram' database.

    This is a last-resort guard. The test suite should ALWAYS be pointed at a
    dedicated test database (e.g. engram_test on a separate port or instance).
    If the URL contains 'localhost:5432/engram' or '5432/engram' with no test
    indicator, it means we're about to run truncate_all_tables() on production.
    """
    if url is None:
        raise RuntimeError("TEST_DATABASE_URL is not set. Cannot run tests.")
    # Match the production DB path: any host, port 5432, database = engram
    # but NOT engram_test or any other test-variant name
    if re.search(r"://[^/]+:\d*/engram$", url):
        raise RuntimeError(
            f"FATAL: TEST_DATABASE_URL points to the production 'engram' database.\n"
            f"  URL: {url}\n"
            f"This would truncate all production data.\n"
            f"Set TEST_DATABASE_URL to your isolated test database.\n"
            f"Hint: postgresql://engram:engram@localhost:5433/engram_test"
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


def _truncate_all_tables(url):
    """Call truncate_all_tables() with bounded retries.

    The Postgres function acquires ACCESS EXCLUSIVE locks on every table in a
    fixed order; concurrent sessions (leaked pooled connections, xdist workers,
    or overlapping test sessions) can still deadlock. The function now sets its
    own statement timeout, and this wrapper retries with exponential backoff so
    the suite fails fast with a clear error instead of hanging indefinitely.
    """
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
                # Connection may be in an aborted transaction after a lock error;
                # reconnect for the next attempt to guarantee a clean state.
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


def _apply_schema(app):
    """Apply docs/SCHEMA.sql to the test database via raw connection."""
    import psycopg2
    import os

    sql = SCHEMA_PATH.read_text()
    url = os.environ.get("TEST_DATABASE_URL")
    with _schema_lock:
        conn = _connect_test_db(url)
        try:
            cur = conn.cursor()
            _set_statement_timeout(cur, 30)
            # Drop all existing tables first to avoid conflicts
            cur.execute("""
                DO $$ DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                    END LOOP;
                END $$;
            """)
            cur.execute(sql)
            cur.close()
        finally:
            conn.close()


@pytest.fixture(scope="session")
def _db(app):
    """Session-scoped database handle. Keeps the app context alive."""
    yield db


@pytest.fixture(autouse=True)
def reset_db(app, _db):
    """Truncate all tables before each test for isolation."""
    import os

    url = os.environ.get("TEST_DATABASE_URL")
    with _schema_lock:
        _truncate_all_tables(url)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def mock_embed():
    """Mock OpenAI embeddings — returns zero vector."""
    with patch("services.embeddings._embed_texts") as mock:
        mock.return_value = [[0.0] * 1536]
        yield mock
