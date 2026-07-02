"""Tests for the v4 activity update API."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from extensions import db
from models import Entity, EntityEvent, EntityLink, Job


def _create_entity(client, entity_type, title):
    response = client.post("/api/v4/entities", json={"type": entity_type, "title": title})
    assert response.status_code == 201
    return response.get_json()["data"]


def test_create_activity_update(client, app):
    project = _create_entity(client, "project", "Build v4")

    response = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "Started the migration today."},
    )

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["type"] == "note"
    assert data["source"] == "activity_update"
    assert data["content"] == "Started the migration today."
    # Title is deterministic: target + date, not the truncated first sentence.
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert data["title"] == f"Update: Build v4 ({today})"


def test_activity_update_note_ai_status_is_done_after_creation(client, app):
    project = _create_entity(client, "project", "Build v4")

    response = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "Lightweight extraction already ran."},
    )

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["source"] == "activity_update"
    assert data["ai"]["status"] == "done"

    with app.app_context():
        note = db.session.get(Entity, data["id"])
        assert note.ai_status == "done"


def test_create_activity_update_writes_event(client, app):
    task = _create_entity(client, "task", "Ship the feature")

    response = client.post(
        f"/api/v4/entities/{task['id']}/activity_updates",
        json={"content": "Code review passed."},
    )
    assert response.status_code == 201

    with app.app_context():
        events = EntityEvent.query.filter_by(entity_id=task["id"]).all()
        event_types = {e.event_type for e in events}
        assert "activity_update_added" in event_types
        update_event = next(e for e in events if e.event_type == "activity_update_added")
        assert update_event.new_value["note_id"] == response.get_json()["data"]["id"]


def test_create_activity_update_creates_relationship(client, app):
    area = _create_entity(client, "area", "Backend")

    response = client.post(
        f"/api/v4/entities/{area['id']}/activity_updates",
        json={"content": "Deployed to production."},
    )
    assert response.status_code == 201
    note_id = response.get_json()["data"]["id"]

    with app.app_context():
        link = EntityLink.query.filter_by(
            source_entity_id=note_id,
            target_entity_id=area["id"],
            relationship_type="activity_update",
        ).first()
        assert link is not None
        assert link.source == "activity_update"


def test_create_activity_update_touches_updated_at(client, app):
    project = _create_entity(client, "project", "Alpha")

    with app.app_context():
        entity = db.session.get(Entity, project["id"])
        old_updated = entity.updated_at

    import time
    time.sleep(0.01)

    response = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "Updated scope."},
    )
    assert response.status_code == 201

    with app.app_context():
        entity = db.session.get(Entity, project["id"])
        assert entity.updated_at > old_updated


def test_get_activity_updates(client):
    project = _create_entity(client, "project", "Beta")

    for content in ["First update", "Second update", "Third update"]:
        response = client.post(
            f"/api/v4/entities/{project['id']}/activity_updates",
            json={"content": content},
        )
        assert response.status_code == 201

    response = client.get(f"/api/v4/entities/{project['id']}/activity_updates")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert len(data) == 3
    assert all(item["source"] == "activity_update" for item in data)
    assert all(item["type"] == "note" for item in data)
    assert [item["content"] for item in data] == ["Third update", "Second update", "First update"]


def test_duplicate_content_within_24h_is_skipped(client):
    project = _create_entity(client, "project", "Gamma")

    response1 = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "Same content"},
    )
    assert response1.status_code == 201
    note1_id = response1.get_json()["data"]["id"]

    response2 = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "Same content"},
    )
    assert response2.status_code == 200
    assert response2.get_json()["skipped"] is True
    assert response2.get_json()["data"]["id"] == note1_id


def test_different_content_within_24h_is_allowed(client):
    project = _create_entity(client, "project", "Delta")

    response1 = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "First message"},
    )
    assert response1.status_code == 201

    response2 = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "Different message"},
    )
    assert response2.status_code == 201
    assert response2.get_json().get("skipped") is not True


def test_long_lived_entity_allows_more_than_30_activity_updates(client, app):
    project = _create_entity(client, "project", "Long lived")

    for i in range(31):
        response = client.post(
            f"/api/v4/entities/{project['id']}/activity_updates",
            json={"content": f"Update number {i}"},
        )
        assert response.status_code == 201, f"Failed at update {i}"

    with app.app_context():
        count = (
            Entity.query.join(
                EntityLink,
                (EntityLink.source_entity_id == Entity.id) & (EntityLink.target_entity_id == project["id"]),
            )
            .filter(
                Entity.type == "note",
                Entity.source == "activity_update",
                EntityLink.relationship_type == "activity_update",
            )
            .count()
        )
        assert count == 31


def test_get_activity_updates_supports_pagination(client):
    project = _create_entity(client, "project", "Paged")

    for i in range(5):
        response = client.post(
            f"/api/v4/entities/{project['id']}/activity_updates",
            json={"content": f"Paged update {i}"},
        )
        assert response.status_code == 201

    response = client.get(
        f"/api/v4/entities/{project['id']}/activity_updates",
        query_string={"limit": 2, "offset": 0},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 5
    assert body["meta"]["limit"] == 2
    assert body["meta"]["offset"] == 0


def test_entity_detail_activity_section_includes_total_meta(client):
    project = _create_entity(client, "project", "Meta project")

    for i in range(6):
        response = client.post(
            f"/api/v4/entities/{project['id']}/activity_updates",
            json={"content": f"Detail meta update {i}"},
        )
        assert response.status_code == 201

    detail = client.get(f"/api/v4/entities/{project['id']}/detail").get_json()
    section = next(item for item in detail["sections"] if item["key"] == "activity_updates")

    assert section["meta"]["total"] == 6
    assert section["meta"]["limit"] == 5
    assert len(section["items"]) == 5


def test_near_duplicate_activity_update_within_24h_is_skipped(client):
    project = _create_entity(client, "project", "Near dup")

    response1 = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "Shipped parser fix to design partners today."},
    )
    assert response1.status_code == 201

    response2 = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "Shipped the parser fix to design partners today!"},
    )
    assert response2.status_code == 200
    body = response2.get_json()
    assert body["skipped"] is True
    assert body["reason"] == "near_duplicate"
    assert body["data"]["id"] == response1.get_json()["data"]["id"]


def test_archive_target_cascades_to_incoming_activity_updates(client, app):
    task = _create_entity(client, "task", "Archive test task")

    response = client.post(
        f"/api/v4/entities/{task['id']}/activity_updates",
        json={"content": "Update to be archived"},
    )
    assert response.status_code == 201
    note_id = response.get_json()["data"]["id"]

    response = client.patch(
        f"/api/v4/entities/{task['id']}",
        json={"lifecycle": "archived"},
    )
    assert response.status_code == 200

    with app.app_context():
        note = db.session.get(Entity, note_id)
        assert note.lifecycle == "archived"


def test_delete_target_removes_incoming_activity_updates(client, app):
    area = _create_entity(client, "area", "Delete cascade area")

    response = client.post(
        f"/api/v4/entities/{area['id']}/activity_updates",
        json={"content": "Will be deleted"},
    )
    assert response.status_code == 201
    note_id = response.get_json()["data"]["id"]

    response = client.delete(f"/api/v4/entities/{area['id']}")
    assert response.status_code == 200

    with app.app_context():
        note = db.session.get(Entity, note_id)
        assert note is None


def test_activity_update_requires_content(client):
    project = _create_entity(client, "project", "Empty test")
    response = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": ""},
    )
    assert response.status_code == 400


def test_activity_update_nonexistent_target_returns_404(client):
    response = client.post(
        "/api/v4/entities/nonexistent-id/activity_updates",
        json={"content": "Should fail"},
    )
    assert response.status_code == 404


def test_get_activity_updates_nonexistent_target_returns_404(client):
    response = client.get("/api/v4/entities/nonexistent-id/activity_updates")
    assert response.status_code == 404

def test_activity_note_detail_links_back_to_target(client, app):
    """An activity-update note's detail page surfaces the entity it updates."""
    project = _create_entity(client, "project", "Build v4")
    note = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "Shipped the first slice."},
    ).get_json()["data"]

    detail = client.get(f"/api/v4/entities/{note['id']}/detail").get_json()
    sections = {s["key"]: s for s in detail["sections"]}
    assert "update_on" in sections
    items = sections["update_on"]["items"]
    assert len(items) == 1
    assert items[0]["entity"]["id"] == project["id"]
    assert items[0]["entity"]["title"] == "Build v4"
    assert items[0]["relationship"]["relationship_type"] == "activity_update"


# --- AU0 baseline: current behavior later slices will change ---


def test_direct_activity_update_queues_embed_for_update_note(client, app):
    project = _create_entity(client, "project", "Embed queue")

    response = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "Shipped the parser fix."},
    )
    assert response.status_code == 201
    note_id = response.get_json()["data"]["id"]

    with app.app_context():
        job = Job.query.filter_by(entity_id=note_id, job_type="embed").one()
        assert job.payload["reason"] == "activity_update"


def test_direct_activity_update_queues_target_summarize_job(client, app):
    project = _create_entity(client, "project", "Summary queue")

    response = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "Rolled out to design partners."},
    )
    assert response.status_code == 201

    with app.app_context():
        job = Job.query.filter_by(
            entity_id=project["id"],
            job_type="summarize",
        ).one()
        assert job.payload["entity_id"] == project["id"]


def test_direct_activity_update_event_sets_source_note_id(client, app):
    task = _create_entity(client, "task", "Provenance")

    response = client.post(
        f"/api/v4/entities/{task['id']}/activity_updates",
        json={"content": "Waiting on review."},
    )
    assert response.status_code == 201
    note_id = response.get_json()["data"]["id"]

    with app.app_context():
        update_event = EntityEvent.query.filter_by(
            entity_id=task["id"],
            event_type="activity_update_added",
        ).one()
        assert update_event.source_note_id == note_id
        assert update_event.new_value["note_id"] == note_id


def test_activity_update_does_not_write_bookkeeping_updated_event(client, app):
    project = _create_entity(client, "project", "Timeline hygiene")

    response = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "Scope narrowed to two teams."},
    )
    assert response.status_code == 201

    with app.app_context():
        event_types = {
            e.event_type
            for e in EntityEvent.query.filter_by(entity_id=project["id"]).all()
        }
        assert "activity_update_added" in event_types
        assert "updated" not in event_types


def test_task_update_without_explicit_date_does_not_auto_set_follow_up(client, app):
    task = _create_entity(client, "task", "Follow-up policy")
    assert task.get("follow_up_at") is None

    response = client.post(
        f"/api/v4/entities/{task['id']}/activity_updates",
        json={"content": "Made progress on the rollout checklist."},
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["extracted"]["follow_up_auto_set"] is False

    with app.app_context():
        entity = db.session.get(Entity, task["id"])
        assert entity.follow_up_at is None


def test_extracted_task_from_activity_update_becomes_suggestion(client, app):
    project = _create_entity(client, "project", "Task suggestion policy")
    extraction = {
        "follow_up_at": None,
        "tasks": [
            {
                "title": "Ask Mary for rollout notes",
                "content": None,
                "due_at": None,
                "assigned_to": "Mary",
                "confidence": 0.9,
            }
        ],
    }

    with patch(
        "services.v4_extraction.extract_dates_and_tasks_from_update",
        return_value=extraction,
    ):
        response = client.post(
            f"/api/v4/entities/{project['id']}/activity_updates",
            json={"content": "Also ask Mary for rollout notes"},
        )

    assert response.status_code == 201
    data = response.get_json()
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["suggestion_type"] == "create_task"
    assert len(data["extracted"]["tasks"]) == 1
    assert data["extracted"]["tasks"][0]["auto_created"] is False

    with app.app_context():
        assert Entity.query.filter_by(type="task", title="Ask Mary for rollout notes").count() == 0


def test_activity_update_explicit_follow_up_date_is_applied(client, app):
    task = _create_entity(client, "task", "Explicit follow-up")
    extraction = {"follow_up_at": "2026-08-15", "tasks": []}

    with patch(
        "services.v4_extraction.extract_dates_and_tasks_from_update",
        return_value=extraction,
    ):
        response = client.post(
            f"/api/v4/entities/{task['id']}/activity_updates",
            json={"content": "Follow up next Friday on rollout."},
        )

    assert response.status_code == 201
    data = response.get_json()
    assert data["extracted"]["follow_up_at"] == "2026-08-15"

    with app.app_context():
        entity = db.session.get(Entity, task["id"])
        assert entity.follow_up_at is not None


def test_activity_update_extracted_task_becomes_suggestion_not_duplicate(client, app):
    """Matching an existing task title still goes to review — no silent link/create."""
    existing_task = _create_entity(client, "task", "Check due dates")
    project = _create_entity(client, "project", "Billing")

    extraction = {
        "follow_up_at": None,
        "tasks": [
            {
                "title": "Check due dates",
                "content": None,
                "due_at": None,
                "assigned_to": None,
                "confidence": 0.85,
            }
        ],
    }

    with patch(
        "services.v4_extraction.extract_dates_and_tasks_from_update",
        return_value=extraction,
    ):
        response = client.post(
            f"/api/v4/entities/{project['id']}/activity_updates",
            json={"content": "Remember to check due dates"},
        )

    assert response.status_code == 201
    data = response.get_json()

    with app.app_context():
        assert Entity.query.filter_by(type="task", title="Check due dates").count() == 1

    assert len(data["suggestions"]) == 1
    extracted = data["extracted"]["tasks"]
    assert len(extracted) == 1
    assert extracted[0]["auto_created"] is False
    assert "suggestion_id" in extracted[0]

    with app.app_context():
        assert EntityEvent.query.filter_by(
            entity_id=existing_task["id"], event_type="created"
        ).count() == 1
