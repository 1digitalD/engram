import pathlib
import pytest
from unittest.mock import patch, MagicMock

from app import create_app
from extensions import db
from sqlalchemy import text

# Optional MCP server stack (fastmcp) is not installed in minimal test venvs.
collect_ignore = ["test_mcp_server.py"]

SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[1] / "docs" / "SCHEMA.sql"


@pytest.fixture(scope="session")
def app():
    """Session-scoped Flask app. Schema is applied once at session start."""
    app = create_app("testing")
    with app.app_context():
        _apply_schema(app)
    yield app


def _apply_schema(app):
    """Apply docs/SCHEMA.sql to the test database via raw connection.

    Uses the underlying psycopg2 connection so that PL/pgSQL dollar-quoted
    strings ($$ … $$) are handled correctly — splitting on ';' would break
    function bodies.
    """
    sql = SCHEMA_PATH.read_text()
    with db.engine.connect() as conn:
        conn.connection.cursor().execute(sql)
        conn.commit()


@pytest.fixture(scope="session")
def _db(app):
    """Session-scoped database handle. Keeps the app context alive."""
    yield db


@pytest.fixture(autouse=True)
def reset_db(_db):
    """Truncate all tables before each test for isolation."""
    with _db.engine.connect() as conn:
        conn.execute(text("SELECT truncate_all_tables()"))
        conn.commit()


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
