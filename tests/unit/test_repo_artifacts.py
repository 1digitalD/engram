"""Contract checks for repo-level docs and operational artifacts."""

from pathlib import Path
import plistlib

from mcp_server import server


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_readme_and_mcp_docs_describe_write_enabled_mcp():
    readme = (REPO_ROOT / "README.md").read_text()
    mcp_readme = (REPO_ROOT / "mcp_server" / "README_V4.md").read_text()

    assert "write-enabled MCP server" in readme
    assert "capture" in readme
    assert "append_activity_update" in readme

    assert "**Write:**" in mcp_readme
    assert "submit_candidates" in mcp_readme
    assert "append_activity_update" in mcp_readme


def test_mcp_server_exposes_expected_write_tools():
    assert callable(server.capture)
    assert callable(server.create_entity)
    assert callable(server.update_entity)
    assert callable(server.link_entities)
    assert callable(server.accept_suggestion)
    assert callable(server.dismiss_suggestion)
    assert callable(server.reconcile_suggestions)
    assert callable(server.submit_candidates)
    assert callable(server.append_activity_update)


def test_launchagent_plist_is_valid():
    plist_path = REPO_ROOT / "com.engram.api.plist"
    with plist_path.open("rb") as fh:
        data = plistlib.load(fh)

    assert data["Label"] == "com.engram.api"
    assert data["ProgramArguments"][0].endswith("/venv/bin/python")
    assert data["EnvironmentVariables"]["DATABASE_URL"].endswith("/engram")
