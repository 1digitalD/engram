"""Integration tests for typed inline affordance flows."""

from datetime import datetime, timezone

from extensions import db
from models import ChangeBatch, Entity, EntityEvent, EntityLink


def _create_entity(client, entity_type, title, **extra):
    payload = {"type": entity_type, "title": title, **extra}
    response = client.post("/api/v4/entities", json=payload)
    assert response.status_code == 201
    return response.get_json()["data"]


def _link(client, source_id, target_id, relationship_type):
    response = client.post(
        f"/api/v4/entities/{source_id}/relationships",
        json={"target_entity_id": target_id, "relationship_type": relationship_type},
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def test_tc33_move_to_space_replaces_parent_in_single_change_batch(client, app):
    task = _create_entity(client, "task", "Ship the launch")
    old_space = _create_entity(client, "project", "Old space")
    new_space = _create_entity(client, "project", "New space")
    original_link = _link(client, task["id"], old_space["id"], "parent")

    response = client.post(
        f"/api/v4/entities/{task['id']}/links",
        json={
            "target_id": new_space["id"],
            "relationship_type": "parent",
            "replace_existing": True,
            "batch_summary": "move commitment to new space",
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["data"]["target_entity_id"] == new_space["id"]
    assert body["removed"][0]["id"] == original_link["id"]
    assert body["change_batch"]["actor"] == "user"

    batch_id = body["change_batch"]["id"]
    assert batch_id

    with app.app_context():
        links = EntityLink.query.filter_by(
            source_entity_id=task["id"],
            relationship_type="parent",
        ).all()
        assert [(link.target_entity_id, link.id) for link in links] == [(new_space["id"], body["data"]["id"])]

        batch = db.session.get(ChangeBatch, batch_id)
        assert batch is not None
        assert batch.actor == "user"
        assert batch.summary == "move commitment to new space"

        events = (
            EntityEvent.query.filter_by(entity_id=task["id"], change_batch_id=batch_id)
            .order_by(EntityEvent.created_at.asc())
            .all()
        )
        event_types = [event.event_type for event in events]
        assert event_types.count("relationship_removed") == 1
        assert event_types.count("relationship_added") == 1


def test_inline_status_and_due_edits_pin_fields_on_human_write(client, app):
    task = _create_entity(client, "task", "Prep roadmap", status="open")
    due_at = datetime(2026, 7, 18, 16, 0, tzinfo=timezone.utc).isoformat()

    response = client.patch(
        f"/api/v4/entities/{task['id']}",
        json={"status": "in_progress", "due_at": due_at},
    )

    assert response.status_code == 200

    with app.app_context():
        updated = db.session.get(Entity, task["id"])
        assert updated.status == "in_progress"
        assert updated.due_at.isoformat() == due_at
        assert sorted(updated.pinned_fields) == ["due_at", "status"]

        pin_event = (
            EntityEvent.query.filter_by(entity_id=task["id"], event_type="updated")
            .order_by(EntityEvent.created_at.desc())
            .first()
        )
        assert pin_event is not None


def test_fast_paths_write_ledger_events_with_user_actor(client, app):
    space = _create_entity(client, "project", "Apollo")
    task = _create_entity(client, "task", "Close open loop", status="open")
    _link(client, task["id"], space["id"], "parent")

    create_response = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Add new commitment", "status": "open"},
    )
    assert create_response.status_code == 201
    created_task = create_response.get_json()["data"]

    attach_response = client.post(
        f"/api/v4/entities/{created_task['id']}/links",
        json={"target_id": space["id"], "relationship_type": "parent"},
    )
    assert attach_response.status_code == 201

    update_response = client.post(
        f"/api/v4/entities/{task['id']}/activity_updates",
        json={"content": "Sent the revised draft to legal."},
    )
    assert update_response.status_code == 201

    done_response = client.patch(
        f"/api/v4/entities/{task['id']}",
        json={"status": "done"},
    )
    assert done_response.status_code == 200

    with app.app_context():
        created_event = (
            EntityEvent.query.filter_by(entity_id=created_task["id"], event_type="created")
            .order_by(EntityEvent.created_at.asc())
            .first()
        )
        assert created_event is not None
        assert created_event.actor == "user"

        link_event = (
            EntityEvent.query.filter_by(entity_id=created_task["id"], event_type="relationship_added")
            .order_by(EntityEvent.created_at.desc())
            .first()
        )
        assert link_event is not None
        assert link_event.actor == "user"

        update_event = (
            EntityEvent.query.filter_by(entity_id=task["id"], event_type="activity_update_added")
            .order_by(EntityEvent.created_at.desc())
            .first()
        )
        assert update_event is not None
        assert update_event.actor == "user"

        done_event = (
            EntityEvent.query.filter_by(entity_id=task["id"], event_type="updated")
            .order_by(EntityEvent.created_at.desc())
            .first()
        )
        assert done_event is not None
        assert done_event.actor == "user"
