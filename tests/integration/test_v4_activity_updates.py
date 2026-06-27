"""Tests for the v4 activity update API."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from extensions import db
from models import Entity, EntityEvent, EntityLink


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


def test_max_30_activity_updates_returns_409(client, app):
    project = _create_entity(client, "project", "Epsilon")

    for i in range(30):
        response = client.post(
            f"/api/v4/entities/{project['id']}/activity_updates",
            json={"content": f"Update number {i}"},
        )
        assert response.status_code == 201, f"Failed at update {i}"

    response = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "This should fail"},
    )
    assert response.status_code == 409
    assert "30" in response.get_json()["error"]


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


def test_activity_update_exact_title_match_does_not_duplicate_task(client, app):
    """An activity update that extracts an already-existing exact-title task
    should link to the existing task instead of minting a duplicate."""
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

    extracted = data["extracted"]["tasks"]
    assert len(extracted) == 1
    assert extracted[0]["entity_id"] == existing_task["id"]
    assert extracted[0]["auto_created"] is False

    with app.app_context():
        assert EntityEvent.query.filter_by(
            entity_id=existing_task["id"], event_type="created"
        ).count() == 1
