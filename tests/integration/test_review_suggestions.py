"""Integration tests for the Review AI Suggestions tab.

Tests GET /api/v2/suggestions endpoint and accept/dismiss actions.
"""

import json
import pytest
from unittest.mock import patch

from extensions import db
from models import Entity, EntityEvent, AiSuggestion, ChangeBatch
from services.entity_service import create_entity


def _create_note(title="Test note", actor="user", app=None):
    with app.app_context():
        entity = create_entity(entity_type="note", title=title, actor=actor)
        db.session.commit()
        note_id = entity.id
    return note_id


def _create_suggestion(entity_id, suggestion_type="create_task", operation_type="create_task",
                       confidence=0.85, status="pending", reason="Test reason", payload=None, app=None):
    with app.app_context():
        suggestion = AiSuggestion(
            source_entity_id=entity_id,
            suggestion_type=suggestion_type,
            operation_type=operation_type,
            payload=payload or {},
            confidence=confidence,
            reason=reason,
            status=status,
        )
        db.session.add(suggestion)
        db.session.commit()
        sug_id = suggestion.id
    return sug_id


class TestListSuggestions:
    def test_list_suggestions_returns_pending(self, client, app):
        note_id = _create_note("Review test note", app=app)
        _create_suggestion(note_id, confidence=0.85, status="pending", app=app)

        res = client.get("/api/v2/suggestions?status=pending")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert len(data["data"]) >= 1

    def test_list_suggestions_filters_by_entity_id(self, client, app):
        note1_id = _create_note("Note one", app=app)
        note2_id = _create_note("Note two", app=app)
        _create_suggestion(note1_id, confidence=0.85, app=app)
        _create_suggestion(note2_id, confidence=0.90, app=app)

        res = client.get(f"/api/v2/suggestions?entity_id={note1_id}")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert all(s["source_entity_id"] == note1_id for s in data["data"])

    def test_list_suggestions_respects_limit(self, client, app):
        note_id = _create_note(app=app)
        for _ in range(5):
            _create_suggestion(note_id, confidence=0.85, app=app)

        res = client.get("/api/v2/suggestions?status=pending&limit=2")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert len(data["data"]) == 2


class TestAcceptSuggestion:
    def test_accept_suggestion_returns_200(self, client, app):
        note_id = _create_note(app=app)
        sug_id = _create_suggestion(
            note_id, confidence=0.95, status="pending",
            suggestion_type="create_task", operation_type="create_task",
            payload={"title": "Test task", "source_note_id": str(note_id)},
            app=app,
        )

        res = client.post(f"/api/v2/suggestions/{sug_id}/accept")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["data"]["suggestion"]["status"] == "accepted"

    def test_accept_nonexistent_returns_404(self, client):
        res = client.post("/api/v2/suggestions/99999/accept")
        assert res.status_code == 404


class TestDismissSuggestion:
    def test_dismiss_suggestion_returns_200(self, client, app):
        note_id = _create_note(app=app)
        sug_id = _create_suggestion(note_id, confidence=0.85, status="pending", app=app)

        res = client.post(f"/api/v2/suggestions/{sug_id}/dismiss")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["data"]["status"] == "dismissed"

    def test_dismiss_nonexistent_returns_404(self, client):
        res = client.post("/api/v2/suggestions/99999/dismiss")
        assert res.status_code == 404