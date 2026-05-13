"""Integration tests for POST /api/v2/ai/propose-from-selection.

Tests the 5 AI actions: classify, extract_task, create_link, improve_writing,
find_and_update.
All OpenAI calls are mocked.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from extensions import db
from models import Entity, EntityEvent, EntityLink
from services.entity_service import create_entity


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _create_entity(**kwargs):
    entity = create_entity(
        entity_type=kwargs.pop("entity_type", "note"),
        title=kwargs.pop("title", "Test"),
        actor="user",
        **kwargs,
    )
    db.session.commit()
    return entity


# ─── Invalid action ──────────────────────────────────────────────────────────

class TestInvalidAction:
    def test_invalid_action_returns_400(self, client):
        res = client.post("/api/v2/ai/propose-from-selection", json={
            "action": "unknown_action",
            "selected_text": "some text",
        })
        assert res.status_code == 400
        data = json.loads(res.data)
        assert "error" in data

    def test_missing_action_returns_400(self, client):
        res = client.post("/api/v2/ai/propose-from-selection", json={
            "selected_text": "some text",
        })
        assert res.status_code == 400
        data = json.loads(res.data)
        assert "error" in data

    def test_missing_text_returns_400(self, client):
        res = client.post("/api/v2/ai/propose-from-selection", json={
            "action": "classify",
        })
        assert res.status_code == 400
        data = json.loads(res.data)
        assert "error" in data

    def test_empty_body_returns_400(self, client):
        res = client.post("/api/v2/ai/propose-from-selection", json={})
        assert res.status_code == 400


# ─── Classify action ────────────────────────────────────────────────────────

class TestClassifyAction:
    @patch("services.extractor.extract")
    def test_classify_returns_para_bucket(self, mock_extract, client, app):
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="A project note",
            para_bucket="PROJECTS",
            confidence=0.92,
            reasoning="Clear project mention",
        )

        res = client.post("/api/v2/ai/propose-from-selection", json={
            "action": "classify",
            "selected_text": "We need to finish the rocket launch by Friday",
        })
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["action"] == "classify"
        assert "entity" in data
        assert data["entity"] is None
        assert data["result"]["para_bucket"] == "PROJECTS"
        assert data["result"]["confidence"] == 0.92
        assert data["result"]["summary"] == "A project note"

    @patch("services.extractor.extract")
    def test_classify_includes_suggestions(self, mock_extract, client, app):
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="Health area note",
            para_bucket="AREAS",
            confidence=0.88,
            suggested_area="Health",
            suggested_project=None,
            reasoning="Ongoing responsibility",
        )

        res = client.post("/api/v2/ai/propose-from-selection", json={
            "action": "classify",
            "selected_text": "Weekly gym routine and meal prep",
        })
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["result"]["suggested_area"] == "Health"


# ─── Extract task action ─────────────────────────────────────────────────────

class TestExtractTaskAction:
    @patch("services.extractor.extract")
    def test_extract_task_creates_entity_task(self, mock_extract, client, app):
        from services.extractor import ExtractionResult, ExtractedTask

        mock_extract.return_value = ExtractionResult(
            summary="Meeting notes",
            para_bucket="PROJECTS",
            confidence=0.90,
            reasoning="Project discussion",
            tasks=[ExtractedTask(
                title="Follow up with design team",
                priority="HIGH",
                due_date="2026-05-15",
            )],
        )

        with app.app_context():
            initial_count = Entity.query.filter_by(type="task").count()

        res = client.post("/api/v2/ai/propose-from-selection", json={
            "action": "extract_task",
            "selected_text": "Need to follow up with the design team about the new mockups by Friday",
        })
        assert res.status_code == 201
        data = json.loads(res.data)
        assert data["action"] == "extract_task"
        assert "tasks" in data["result"]
        assert len(data["result"]["tasks"]) >= 1

        with app.app_context():
            task_count = Entity.query.filter_by(type="task").count()
            assert task_count > initial_count

    @patch("services.extractor.extract")
    def test_extract_task_writes_event(self, mock_extract, client, app):
        from services.extractor import ExtractionResult, ExtractedTask

        mock_extract.return_value = ExtractionResult(
            summary="Notes",
            para_bucket="INBOX",
            confidence=0.80,
            reasoning="General notes",
            tasks=[ExtractedTask(title="Review PR", priority="MEDIUM")],
        )

        res = client.post("/api/v2/ai/propose-from-selection", json={
            "action": "extract_task",
            "selected_text": "Remember to review the PR tomorrow",
        })
        assert res.status_code == 201

        data = json.loads(res.data)
        task_id = data["result"]["tasks"][0]["entity_id"]

        with app.app_context():
            events = EntityEvent.query.filter_by(
                entity_id=task_id, event_type="created"
            ).all()
            assert len(events) >= 1


# ─── Create link action (propose-link) ───────────────────────────────────────

class TestCreateLinkAction:
    def test_propose_link_returns_candidates(self, client, app):
        """When entities exist, propose-link returns related candidates."""
        entity_ids = []
        with app.app_context():
            e1 = _create_entity(title="Python Tips", content="Python best practices and tips")
            e2 = _create_entity(title="Django Guide", content="Django web framework guide")
            e3 = _create_entity(title="Cooking Recipes", content="Italian cooking recipes")
            entity_ids = [str(e1.id), str(e2.id), str(e3.id)]

        res = client.post("/api/v2/ai/propose-from-selection", json={
            "action": "create_link",
            "selected_text": "Python best practices and tips",
            "source_entity_id": entity_ids[0],
        })
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["action"] == "create_link"
        assert "candidates" in data["result"]

    def test_propose_link_no_candidates_when_no_entities(self, client):
        res = client.post("/api/v2/ai/propose-from-selection", json={
            "action": "create_link",
            "selected_text": "Some random text",
        })
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["action"] == "create_link"
        assert data["result"]["candidates"] == []


# ─── Find and update action ──────────────────────────────────────────────────

class TestFindAndUpdateAction:
    @patch("api.ai_selection.search")
    def test_find_and_update_returns_top_three_semantic_candidates(self, mock_search, client):
        mock_search.return_value = [
            {"id": "entity-1", "title": "Project Apollo", "type": "project", "content": "Launch planning"},
            {"id": "entity-2", "title": "Launch Checklist", "type": "note", "content": "Checklist"},
            {"id": "entity-3", "title": "Mission Debrief", "type": "note", "content": "Debrief"},
            {"id": "entity-4", "title": "Extra Match", "type": "task", "content": "Extra"},
        ]

        res = client.post("/api/v2/ai/propose-from-selection", json={
            "action": "find_and_update",
            "selected_text": "Add the latest launch blockers and owners",
        })

        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["action"] == "find_and_update"
        assert len(data["result"]["candidates"]) == 3
        assert [item["entity"]["id"] for item in data["result"]["candidates"]] == [
            "entity-1", "entity-2", "entity-3"
        ]
        assert data["result"]["candidates"][0]["proposed_change"] == {
            "content": "Add the latest launch blockers and owners"
        }
        mock_search.assert_called_once_with(
            query="Add the latest launch blockers and owners",
            limit=3,
            mode="semantic",
        )


# ─── Improve writing action ─────────────────────────────────────────────────

class TestImproveWritingAction:
    def test_improve_writing_returns_improved_text(self, client):
        res = client.post("/api/v2/ai/propose-from-selection", json={
            "action": "improve_writing",
            "selected_text": "this is a badly written sentance with erors",
        })
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["action"] == "improve_writing"
        assert "result" in data
        assert "improved_text" in data["result"]
