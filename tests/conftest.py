import pytest
from app import create_app
from extensions import db

# Optional MCP server stack (fastmcp) is not installed in minimal test venvs.
collect_ignore = ["test_mcp_server.py"]


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()
