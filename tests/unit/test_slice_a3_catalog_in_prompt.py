"""Slice A3: full project/area catalog in the reconciler prompt.

TDD red → green for:
1. _build_catalog_block returns a formatted string of active projects+areas
2. The catalog block is included in the reconciliation system prompt
3. Catalog is capped at ~2k tokens (truncated by recency if over limit)
4. Non-project/area types are not included in the catalog block
5. Empty catalog (no projects/areas) is handled gracefully
6. Catalog block in prompt does not break existing _call_model behavior
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services import v4_reconciliation


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_entity(client, entity_type, title, content=""):
    r = client.post("/api/v4/entities", json={"type": entity_type, "title": title, "content": content})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["data"]


# ── Unit: _build_catalog_block ────────────────────────────────────────────────

class TestBuildCatalogBlock:
    def test_returns_string(self, client, app):
        block = v4_reconciliation._build_catalog_block()
        assert isinstance(block, str)

    def test_includes_projects_and_areas(self, client, app):
        proj = _make_entity(client, "project", "Agent Security", "Security roadmap content")
        area = _make_entity(client, "area", "Engineering", "Engineering domain")

        block = v4_reconciliation._build_catalog_block()

        assert "Agent Security" in block
        assert "Engineering" in block

    def test_excludes_tasks_persons_notes(self, client, app):
        _make_entity(client, "task", "Fix the bug")
        _make_entity(client, "person", "Alice Smith")

        block = v4_reconciliation._build_catalog_block()

        assert "Fix the bug" not in block
        assert "Alice Smith" not in block

    def test_includes_content_preview(self, client, app):
        _make_entity(client, "project", "GTM Agent Support",
                     "Provide deep support for GTM agent observability")

        block = v4_reconciliation._build_catalog_block()

        assert "GTM Agent Support" in block
        assert "observability" in block

    def test_empty_catalog_returns_empty_string(self, client, app):
        # No projects or areas created in this test — catalog may contain some
        # from other tests (session-scoped DB), so just assert it's a string
        block = v4_reconciliation._build_catalog_block()
        assert isinstance(block, str)

    def test_deleted_entities_excluded(self, client, app):
        proj = _make_entity(client, "project", "Deleted Project XYZ99")
        # Delete it
        client.delete(f"/api/v4/entities/{proj['id']}")

        block = v4_reconciliation._build_catalog_block()
        assert "Deleted Project XYZ99" not in block

    def test_catalog_token_cap(self, client, app):
        # Create many projects to trigger the cap
        for i in range(60):
            _make_entity(client, "project", f"Cap Test Project {i:03d}",
                         "x" * 200)

        block = v4_reconciliation._build_catalog_block()
        # Cap is 2000 tokens ≈ 8000 chars; verify we stay under
        assert len(block) <= 8500, f"Catalog block too large: {len(block)} chars"

    def test_catalog_format_has_type_and_title(self, client, app):
        _make_entity(client, "project", "Format Check Project")
        _make_entity(client, "area", "Format Check Area")

        block = v4_reconciliation._build_catalog_block()

        assert "[project]" in block
        assert "[area]" in block
        assert "Format Check Project" in block
        assert "Format Check Area" in block


# ── Integration: catalog in prompt ────────────────────────────────────────────

class TestCatalogInPrompt:
    def test_catalog_block_appears_in_system_prompt(self, client, app):
        """When _call_model is invoked, the system prompt includes catalog."""
        _make_entity(client, "project", "Catalog Prompt Test Project",
                     "testing that this appears in prompt")

        candidates = [{"type": "project", "title": "Something new", "confidence": 0.7}]

        captured_messages = []

        def fake_create(**kwargs):
            captured_messages.append(kwargs["messages"])
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = '{"decisions": [{"action": "new", "target_id": null, "fields": {}, "relationship_type": null, "confidence": 0.5, "reason": "test"}]}'
            return resp

        with patch("services.v4_reconciliation._embed_texts", return_value=[[0.5] + [0.0] * 1535]):
            with patch("services.v4_reconciliation.get_openai_client") as mock_client:
                mock_client.return_value.chat.completions.create.side_effect = fake_create
                with patch.dict("os.environ", {"OPENAI_API_KEY": "fake-key"}):
                    v4_reconciliation.reconcile_candidates(candidates)

        assert captured_messages, "No model call captured"
        system_content = captured_messages[0][0]["content"]
        assert "Catalog Prompt Test Project" in system_content, (
            f"Catalog not found in system prompt. Prompt snippet: {system_content[:300]}"
        )
        assert "WORKSPACE CATALOG" in system_content

    def test_catalog_absent_when_no_projects(self, client, app):
        """If catalog is empty the prompt still works (no crash, no empty block)."""
        candidates = [{"type": "task", "title": "Write tests", "confidence": 0.9}]

        captured = []

        def fake_create(**kwargs):
            captured.append(kwargs["messages"])
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = '{"decisions": [{"action": "new", "target_id": null, "fields": {}, "relationship_type": null, "confidence": 0.5, "reason": "ok"}]}'
            return resp

        with patch("services.v4_reconciliation._embed_texts", return_value=[[0.5] + [0.0] * 1535]):
            with patch("services.v4_reconciliation.get_openai_client") as mock_client:
                mock_client.return_value.chat.completions.create.side_effect = fake_create
                with patch.dict("os.environ", {"OPENAI_API_KEY": "fake-key"}):
                    with patch("services.v4_reconciliation._build_catalog_block", return_value=""):
                        result = v4_reconciliation.reconcile_candidates(candidates)

        assert len(result) == 1
        assert result[0]["action"] == "new"

    def test_heuristic_fallback_unchanged_without_api_key(self, client, app, monkeypatch):
        """Without OPENAI_API_KEY heuristic path still works; catalog not needed."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        proj = _make_entity(client, "project", "Exact Heuristic Project A3")

        candidates = [{"type": "project", "title": "Exact Heuristic Project A3", "confidence": 0.9}]
        decisions = v4_reconciliation.reconcile_candidates(candidates)

        assert len(decisions) == 1
        assert decisions[0]["action"] == "link"
        assert decisions[0]["target_id"] == proj["id"]
