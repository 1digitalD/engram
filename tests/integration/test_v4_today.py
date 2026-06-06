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
    overdue_followup_task = _create_entity(client, "task", "Overdue follow-up", follow_up_at=yesterday)
    today_followup_note = _create_entity(client, "note", "Today note", follow_up_at=today)
    upcoming_followup_task = _create_entity(
        client, "task", "Upcoming follow-up",
        follow_up_at=(datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
    )
    overdue_due_task = _create_entity(client, "task", "Overdue by due", due_at=yesterday)
    due_today_task = _create_entity(client, "task", "Due today", due_at=today)
    done_with_followup = _create_entity(client, "task", "Done w/ followup", follow_up_at=yesterday, status="done")
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
    assert {item["id"] for item in data["overdue_follow_ups"]} == {overdue_followup_task["id"]}
    assert {item["id"] for item in data["follow_ups"]} == {today_followup_note["id"]}
    assert {item["id"] for item in data["upcoming_follow_ups"]} == {upcoming_followup_task["id"]}
    # done_with_followup should NOT appear in either follow-up bucket (status filter).
    assert done_with_followup["id"] not in {i["id"] for i in data["overdue_follow_ups"]}
    assert done_with_followup["id"] not in {i["id"] for i in data["follow_ups"]}
    assert {item["id"] for item in data["overdue"]} == {overdue_due_task["id"]}
    assert {item["id"] for item in data["due_today"]} == {due_today_task["id"]}
    assert {item["id"] for item in data["blocked_tasks"]} == {blocked_task["id"]}
    assert {item["id"] for item in data["waiting_tasks"]} == {waiting_task["id"]}
    assert {item["id"] for item in data["blocked_or_waiting_tasks"]} == {waiting_task["id"], blocked_task["id"]}
    assert [item["id"] for item in data["projects_without_open_tasks"]] == [project_without_tasks["id"]]
    assert [item["id"] for item in data["recent_notes"]] == [recent_note["id"], today_followup_note["id"]]
    assert data["pending_suggestions"][0]["payload"]["title"] == "Suggested task"


def test_v4_inbox_separates_needs_review_from_recent(client, app):
    needs_pending = _create_entity(client, "note", "Needs review (pending)")
    processed = _create_entity(client, "note", "Already processed")
    with_suggestion = _create_entity(client, "note", "Has open suggestion")

    with app.app_context():
        note = db.session.get(Entity, processed["id"])
        note.ai_status = "done"
        db.session.add(AiSuggestion(
            source_entity_id=with_suggestion["id"],
            suggestion_type="create_task",
            operation_type="create_entity",
            payload={"title": "Suggested task"},
            status="pending",
        ))
        db.session.commit()

    response = client.get("/api/v4/inbox")
    assert response.status_code == 200
    data = response.get_json()

    needs_ids = {n["id"] for n in data["needs_review"]}
    recent_ids = {n["id"] for n in data["recent"]}

    assert needs_pending["id"] in needs_ids  # ai_status defaults to "pending"
    assert with_suggestion["id"] in needs_ids  # has pending AiSuggestion
    assert processed["id"] in recent_ids
    assert processed["id"] not in needs_ids

    # pending_suggestion_count annotation
    by_id = {n["id"]: n for n in data["needs_review"] + data["recent"]}
    assert by_id[with_suggestion["id"]]["pending_suggestion_count"] == 1
    assert by_id[processed["id"]]["pending_suggestion_count"] == 0
