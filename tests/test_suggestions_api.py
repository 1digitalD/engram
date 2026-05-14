"""Tests for V2 AI Suggestions API (api/proposals.py)."""

import json
from datetime import datetime, timezone

from extensions import db
from models import Entity, AiSuggestion
from services.entity_service import create_entity


def _create_entity(**kwargs):
    entity = create_entity(
        entity_type=kwargs.pop("entity_type", "note"),
        title=kwargs.pop("title", "Test"),
        actor="user",
        **kwargs,
    )
    db.session.commit()
    return str(entity.id)


def _create_suggestion(source_entity_id, **overrides):
    defaults = dict(
        source_entity_id=source_entity_id,
        suggestion_type="link",
        operation_type="create_new_entity",
        payload={"src_id": source_entity_id, "dst_id": "target-id", "link_type": "related"},
        confidence=0.88,
        reason="Test suggestion",
        status="pending",
    )
    defaults.update(overrides)
    s = AiSuggestion(**defaults)
    db.session.add(s)
    db.session.commit()
    return str(s.id)


class TestSuggestionsListAPI:
    def test_list_suggestions_empty(self, client, app):
        res = client.get("/api/v2/suggestions")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["data"] == []

    def test_list_suggestions_with_entity_filter(self, client, app):
        with app.app_context():
            eid = _create_entity(title="Source")
            sid = _create_suggestion(eid)
            other_sid = _create_suggestion(eid)
            _create_suggestion(_create_entity(title="Other"))

        res = client.get(f"/api/v2/suggestions?entity_id={eid}")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert len(data["data"]) == 2
        ids = [s["id"] for s in data["data"]]
        assert sid in ids
        assert other_sid in ids

    def test_list_suggestions_with_status_filter(self, client, app):
        with app.app_context():
            eid = _create_entity(title="Source")
            _create_suggestion(eid, status="pending")
            _create_suggestion(eid, status="accepted")
            _create_suggestion(eid, status="dismissed")

        res = client.get("/api/v2/suggestions?status=accepted")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert len(data["data"]) == 1
        assert data["data"][0]["status"] == "accepted"

    def test_list_suggestions_combined_filters(self, client, app):
        with app.app_context():
            eid = _create_entity(title="Source")
            _create_suggestion(eid, status="pending")
            _create_suggestion(eid, status="accepted")

            other_eid = _create_entity(title="Other")
            _create_suggestion(other_eid, status="pending")

        res = client.get(f"/api/v2/suggestions?entity_id={eid}&status=accepted")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert len(data["data"]) == 1
        assert data["data"][0]["status"] == "accepted"

    def test_list_suggestions_limits(self, client, app):
        with app.app_context():
            eid = _create_entity(title="Source")
            for _ in range(5):
                _create_suggestion(eid)

        res = client.get(f"/api/v2/suggestions?entity_id={eid}&limit=2")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert len(data["data"]) == 2


class TestSuggestionsAcceptAPI:
    def test_accept_link_suggestion(self, client, app):
        with app.app_context():
            src_id = _create_entity(entity_type="note", title="Source")
            dst_id = _create_entity(entity_type="project", title="Target")
            sid = _create_suggestion(
                src_id,
                suggestion_type="link",
                payload={
                    "src_id": src_id,
                    "dst_id": dst_id,
                    "link_type": "related",
                    "confidence": 0.95,
                    "evidence": "Test suggestion",
                },
                confidence=0.95,
            )

        res = client.post(f"/api/v2/suggestions/{sid}/accept")
        assert res.status_code == 200
        data = json.loads(res.data)["data"]
        assert len(data["applied_changes"]) == 1
        assert data["applied_changes"][0]["operation"] == "link_entity"

        res2 = client.post(f"/api/v2/suggestions/{sid}/accept")
        assert res2.status_code == 400
        assert "already accepted" in json.loads(res2.data)["error"].lower()

    def test_accept_create_task_suggestion(self, client, app):
        with app.app_context():
            src_id = _create_entity(entity_type="note", title="Source")
            sid = _create_suggestion(
                src_id,
                suggestion_type="create_task",
                payload={"title": "Fix login bug", "source_note_id": src_id},
            )

        res = client.post(f"/api/v2/suggestions/{sid}/accept")
        assert res.status_code == 200
        data = json.loads(res.data)["data"]
        assert "result" in data or "suggestion" in data
        assert data["suggestion"]["status"] == "accepted"

    def test_accept_nonexistent_suggestion(self, client, app):
        res = client.post("/api/v2/suggestions/nonexistent-id/accept")
        assert res.status_code == 404
        assert "not found" in json.loads(res.data)["error"].lower()

    def test_accept_already_accepted(self, client, app):
        with app.app_context():
            eid = _create_entity(title="Source")
            sid = _create_suggestion(eid, status="accepted")

        res = client.post(f"/api/v2/suggestions/{sid}/accept")
        assert res.status_code == 400
        assert "already" in json.loads(res.data)["error"].lower()

    def test_accept_create_task_results_in_task_entity(self, client, app):
        with app.app_context():
            src_id = _create_entity(entity_type="note", title="Source")
            task_count_before = Entity.query.filter_by(type="task").count()
            sid = _create_suggestion(
                src_id,
                suggestion_type="create_task",
                payload={"title": "Test task from suggestion", "source_note_id": src_id},
                confidence=0.95,
            )

        res = client.post(f"/api/v2/suggestions/{sid}/accept")
        assert res.status_code == 200

        with app.app_context():
            task_count_after = Entity.query.filter_by(type="task").count()
            assert task_count_after == task_count_before + 1


class TestSuggestionsDismissAPI:
    def test_dismiss_suggestion(self, client, app):
        with app.app_context():
            eid = _create_entity(title="Source")
            sid = _create_suggestion(eid)

        res = client.post(f"/api/v2/suggestions/{sid}/dismiss")
        assert res.status_code == 200
        data = json.loads(res.data)["data"]
        assert data["status"] == "dismissed"

    def test_dismiss_nonexistent(self, client, app):
        res = client.post("/api/v2/suggestions/nonexistent/dismiss")
        assert res.status_code == 404

    def test_dismiss_non_pending(self, client, app):
        with app.app_context():
            eid = _create_entity(title="Source")
            sid = _create_suggestion(eid, status="accepted")

        res = client.post(f"/api/v2/suggestions/{sid}/dismiss")
        assert res.status_code == 400


class TestSuggestionsEditAPI:
    def test_edit_suggestion_payload(self, client, app):
        with app.app_context():
            eid = _create_entity(title="Source")
            sid = _create_suggestion(
                eid,
                payload={"src_id": eid, "dst_id": "old-target", "link_type": "related"},
            )

        res = client.post(
            f"/api/v2/suggestions/{sid}/edit",
            json={"payload": {"src_id": eid, "dst_id": "new-target", "link_type": "related"}},
        )
        assert res.status_code == 200
        data = json.loads(res.data)["data"]
        assert data["status"] == "edited"
        assert data["payload"]["dst_id"] == "new-target"

    def test_edit_nonexistent(self, client, app):
        res = client.post("/api/v2/suggestions/nonexistent/edit", json={"payload": {}})
        assert res.status_code == 404

    def test_edit_non_pending(self, client, app):
        with app.app_context():
            eid = _create_entity(title="Source")
            sid = _create_suggestion(eid, status="dismissed")

        res = client.post(f"/api/v2/suggestions/{sid}/edit", json={"payload": {}})
        assert res.status_code == 400

    def test_edit_operation_type(self, client, app):
        with app.app_context():
            eid = _create_entity(title="Source")
            sid = _create_suggestion(eid)

        res = client.post(
            f"/api/v2/suggestions/{sid}/edit",
            json={"operation_type": "link_existing"},
        )
        assert res.status_code == 200
        data = json.loads(res.data)["data"]
        assert data["operation_type"] == "link_existing"
