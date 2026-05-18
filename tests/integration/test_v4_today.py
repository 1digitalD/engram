"""Cycle 14 tests for the v4 today cockpit endpoint."""

from datetime import datetime, timedelta, timezone

from extensions import db
from models import AiSuggestion, Entity


def _create_entity(client, entity_type, title, **extra):
    payload = {
        "type": entity_type,
        "title": title,
        "content": f"{title} content",
        **extra,
    }
    response = client.post("/api/v4/entities", json=payload)
    assert response.status_code == 201
    return response.get_json()["data"]


def _link(client, source_id, target_id, relationship_type):
    response = client.post(
        f"/api/v4/entities/{source_id}/relationships",
        json={"target_entity_id": target_id, "relationship_type": relationship_type},
    )
    assert response.status_code == 201


def test_v4_today_returns_execution_sections(client, app):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    today = datetime.now(timezone.utc).isoformat()
    overdue_task = _create_entity(client, "task", "Overdue follow-up", follow_up_at=yesterday)
    today_note = _create_entity(client, "note", "Today note", follow_up_at=today)
    waiting_task = _create_entity(client, "task", "Waiting task", status="waiting")
    blocked_task = _create_entity(client, "task", "Blocked task", status="blocked")
    project_without_tasks = _create_entity(client, "project", "Needs next task")
    project_with_task = _create_entity(client, "project", "Has task")
    open_task = _create_entity(client, "task", "Open project task")
    recent_note = _create_entity(client, "note", "Recent note")
    _link(client, open_task["id"], project_with_task["id"], "parent")

    with app.app_context():
        note = db.session.get(Entity, recent_note["id"])
        suggestion = AiSuggestion(
            source_entity_id=note.id,
            suggestion_type="create_task",
            operation_type="create_entity",
            payload={"title": "Suggested task", "type": "task", "source_entity_id": note.id},
            status="pending",
        )
        db.session.add(suggestion)
        db.session.commit()

    response = client.get("/api/v4/today")

    assert response.status_code == 200
    data = response.get_json()
    assert {item["id"] for item in data["follow_ups"]} == {overdue_task["id"], today_note["id"]}
    assert {item["id"] for item in data["blocked_or_waiting_tasks"]} == {waiting_task["id"], blocked_task["id"]}
    assert [item["id"] for item in data["projects_without_open_tasks"]] == [project_without_tasks["id"]]
    assert recent_note["id"] in {item["id"] for item in data["recent_notes"]}
    assert data["pending_suggestions"][0]["payload"]["title"] == "Suggested task"
