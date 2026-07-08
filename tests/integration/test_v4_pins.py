from pathlib import Path
from unittest.mock import patch

from extensions import db
from models import AiSuggestion, Entity, EntityEvent


def _create_note(app, title="Source note"):
    with app.app_context():
        note = Entity(
            type="note",
            title=title,
            content="Captured source",
            status="active",
            lifecycle="active",
            source="test",
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        db.session.add(note)
        db.session.flush()
        note_id = note.id
        db.session.commit()
        return note_id


def _create_suggestion(app, source_entity_id, payload):
    with app.app_context():
        suggestion = AiSuggestion(
            source_entity_id=source_entity_id,
            suggestion_type="update_task",
            operation_type="update_entity",
            payload=payload,
            confidence=0.91,
            reason=payload.get("evidence"),
            status="pending",
        )
        db.session.add(suggestion)
        db.session.flush()
        suggestion_id = suggestion.id
        db.session.commit()
        return suggestion_id


def test_migration_008_applies_cleanly(app):
    migration_path = Path(__file__).resolve().parents[2] / "scripts" / "migrations" / "008_pinned_fields.sql"
    assert migration_path.exists()

    with app.app_context():
        db.session.execute(db.text(migration_path.read_text()))
        db.session.commit()
        has_column = db.session.execute(
            db.text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'entities' AND column_name = 'pinned_fields')"
            )
        ).scalar()
        assert has_column is True


def test_accepting_pinned_field_suggestion_updates_value_and_keeps_pin(client, app):
    task = client.post("/api/v4/entities", json={"type": "task", "title": "Follow up", "status": "open"}).get_json()["data"]
    note_id = _create_note(app)

    pin_response = client.post(f"/api/v4/entities/{task['id']}/pin", json={"field": "status"})
    assert pin_response.status_code == 200

    suggestion_id = _create_suggestion(
        app,
        note_id,
        {
            "target_entity_id": task["id"],
            "target_type": "task",
            "title": task["title"],
            "fields": {"status": "blocked"},
            "relationship_type": "derived_from",
            "evidence": "blocked pending reply",
        },
    )

    response = client.post(f"/api/v4/suggestions/{suggestion_id}/accept")
    assert response.status_code == 200
    assert response.get_json()["created_entity"]["status"] == "blocked"

    with app.app_context():
        updated = db.session.get(Entity, task["id"])
        assert updated.status == "blocked"
        assert updated.pinned_fields == ["status"]


def test_unpin_allows_next_ai_annotate_write_and_pin_events_are_recorded(client, app):
    task = client.post("/api/v4/entities", json={"type": "task", "title": "Rollout", "status": "open"}).get_json()["data"]

    pin_response = client.post(f"/api/v4/entities/{task['id']}/pin", json={"field": "status"})
    assert pin_response.status_code == 200

    extraction = {
        "title": "Status note",
        "summary": "Task completed",
        "intent": "task_signal",
        "intent_confidence": 0.95,
        "confidence": 0.95,
        "links": [],
        "entities": [{"type": "task", "title": task["title"], "confidence": 0.95, "evidence": "finished"}],
    }
    decisions = [
        {
            "action": "update",
            "target_id": task["id"],
            "relationship_type": "derived_from",
            "confidence": 0.95,
            "fields": {"status": "done"},
            "reason": "finished",
        }
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": "Rollout is done", "mode": "auto"})
    assert response.status_code == 201
    suggestions = response.get_json()["suggestions"]
    assert len(suggestions) == 1
    assert suggestions[0]["operation_type"] == "update_entity"
    assert "pin" in (suggestions[0]["reason"] or "").lower()

    with app.app_context():
        pinned_task = db.session.get(Entity, task["id"])
        assert pinned_task.status == "open"

    unpin_response = client.post(f"/api/v4/entities/{task['id']}/unpin", json={"field": "status"})
    assert unpin_response.status_code == 200

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": "Rollout is done now", "mode": "auto"})
    assert response.status_code == 201
    assert response.get_json()["suggestions"] == []

    with app.app_context():
        updated = db.session.get(Entity, task["id"])
        assert updated.status == "done"
        events = EntityEvent.query.filter_by(entity_id=task["id"]).all()
        reasons = {event.reason for event in events if event.event_type == "updated"}
        assert "pinned status" in reasons
        assert "unpinned status" in reasons
