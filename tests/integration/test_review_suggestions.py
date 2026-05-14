"""Integration tests for the Review AI Suggestions tab.

Tests GET /api/v2/suggestions endpoint and accept/dismiss actions.
"""

import json
import pytest
from unittest.mock import patch

from extensions import db
from models import Entity, EntityEvent, AiSuggestion, ChangeBatch
from services.entity_service import create_entity


def _create_note(title="Test note", actor="user"):
    entity = create_entity(entity_type="note", title=title, actor=actor)
    db.session.commit()
    return entity


def _create_suggestion(entity_id, suggestion_type="create_task", operation_type="create_task",
                       confidence=0.85, status="pending", reason="Test reason", payload=None):
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
    return suggestion


class TestListSuggestions:
    def test_list_suggestions_returns_pending(self, client, app):
        note = _create_note("Review test note")
        with app.app_context():
            _create_suggestion(note.id, confidence=0.85, status="pending")

        res = client.get("/api/v2/suggestions?status=pending")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert len(data["data"]) >= 1

    def test_list_suggestions_filters_by_entity_id(self, client, app):
        note1 = _create_note("Note one")
        note2 = _create_note("Note two")
        with app.app_context():
            _create_suggestion(note1.id, confidence=0.85)
            _create_suggestion(note2.id, confidence=0.90)

        res = client.get(f"/api/v2/suggestions?entity_id={note1.id}")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert all(s["source_entity_id"] == note1.id for s in data["data"])

    def test_list_suggestions_respects_limit(self, client, app):
        note = _create_note()
        with app.app_context():
            for _ in range(5):
                _create_suggestion(note.id, confidence=0.85)

        res = client.get("/api/v2/suggestions?status=pending&limit=2")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert len(data["data"]) == 2


class TestAcceptSuggestion:
    def test_accept_suggestion_returns_200(self, client, app):
        note = _create_note()
        suggestion = _create_suggestion(
            note.id, confidence=0.95, status="pending",
            suggestion_type="create_task", operation_type="create_task",
            payload={"title": "Test task", "source_note_id": str(note.id)},
        )

        res = client.post(f"/api/v2/suggestions/{suggestion.id}/accept")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["data"]["suggestion"]["status"] == "accepted"

    def test_accept_nonexistent_returns_404(self, client):
        res = client.post("/api/v2/suggestions/99999/accept")
        assert res.status_code == 404


class TestDismissSuggestion:
    def test_dismiss_suggestion_returns_200(self, client, app):
        note = _create_note()
        suggestion = _create_suggestion(note.id, confidence=0.85, status="pending")

        res = client.post(f"/api/v2/suggestions/{suggestion.id}/dismiss")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["data"]["status"] == "dismissed"

    def test_dismiss_nonexistent_returns_404(self, client):
        res = client.post("/api/v2/suggestions/99999/dismiss")
        assert res.status_code == 404