import pathlib
import re
import threading
import time

import pytest
from unittest.mock import patch

from app import create_app
from extensions import db
from sqlalchemy import text

SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[1] / "docs" / "SCHEMA.sql"

# Session-level lock to prevent concurrent schema apply / truncate
_schema_lock = threading.Lock()


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


def _apply_schema(app):
    """Apply docs/SCHEMA.sql to the test database via raw connection."""
    import psycopg2
    import os
    sql = SCHEMA_PATH.read_text()
    url = os.environ.get("TEST_DATABASE_URL")
    _assert_not_production_db(url)
    with _schema_lock:
        conn = psycopg2.connect(url)
        conn.autocommit = True
        # Drop all existing tables first to avoid conflicts
        conn.cursor().execute("""
            DO $$ DECLARE
                r RECORD;
            BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                END LOOP;
            END $$;
        """)
        conn.cursor().execute(sql)
        conn.close()


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


@pytest.fixture(scope="session")
def _db(app):
    """Session-scoped database handle. Keeps the app context alive."""
    yield db


@pytest.fixture(autouse=True)
def reset_db(app, _db):
    """Truncate all tables before each test for isolation."""
    import psycopg2
    import os
    url = os.environ.get("TEST_DATABASE_URL")
    _assert_not_production_db(url)
    with _schema_lock:
        conn = psycopg2.connect(url)
        conn.autocommit = True
        try:
            conn.cursor().execute("SELECT truncate_all_tables()")
        except psycopg2.errors.DeadlockDetected:
            # Retry once on deadlock
            time.sleep(0.5)
            conn.cursor().execute("SELECT truncate_all_tables()")
        conn.close()


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
