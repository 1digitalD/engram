import pathlib
import threading
import time
import pytest
from unittest.mock import patch, MagicMock

from app import create_app
from extensions import db
from sqlalchemy import text

# Optional MCP server stack (fastmcp) is not installed in minimal test venvs.
# Legacy v1 model tests — tables no longer exist in v2 Postgres schema.
collect_ignore = [
    "test_mcp_server.py",
    "test_models_legacy.py",
    "test_phase1_backend_foundation.py",
    "test_api.py",  # v1 API tests — v2 schema has no notes/projects/areas/tasks/links tables
    "test_rollup.py",  # Uses v1 Note/Project models, superseded by integration tests
    "test_summaries_api.py",  # v1 summaries table not in v2 schema
    "test_links_api.py",  # v1 links table not in v2 schema
    "test_moc.py",  # v1 moc table not in v2 schema
]

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


# ── OpenAI mock ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_openai():
    """Mock OpenAI API — returns deterministic extraction result."""
    from services.extractor import ExtractionResult
    result = ExtractionResult(
        summary="Test note summary",
        para_bucket="PROJECTS",
        confidence=0.95,
        suggested_project="Test Project",
        suggested_area=None,
        tasks=[],
        people=[],
        tags=["test"],
        reasoning="High confidence project note",
    )
    with patch("services.extractor._get_client") as mock:
        mock_response = MagicMock()
        mock_response.choices[0].message.parsed = result
        mock.return_value.beta.chat.completions.parse.return_value = mock_response
        yield result


@pytest.fixture
def mock_embed():
    """Mock OpenAI embeddings — returns zero vector."""
    with patch("services.embeddings._embed_texts") as mock:
        mock.return_value = [[0.0] * 1536]
        yield mock
