"""Integration tests for the additive POST /api/v4/entities/:id/links endpoint."""

from models import EntityEvent, EntityLink


def _create_entity(client, entity_type, title):
    response = client.post("/api/v4/entities", json={"type": entity_type, "title": title})
    assert response.status_code == 201
    return response.get_json()["data"]


def _create_link(client, source_id, target_id, relationship_type):
    return client.post(
        f"/api/v4/entities/{source_id}/links",
        json={"target_id": target_id, "relationship_type": relationship_type},
    )


def test_create_link_creates_entity_link_row(client):
    task = _create_entity(client, "task", "Write docs")
    project = _create_entity(client, "project", "Docs project")

    response = _create_link(client, task["id"], project["id"], "parent")

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["source_entity_id"] == task["id"]
    assert data["target_entity_id"] == project["id"]
    assert data["relationship_type"] == "parent"
    assert data["source"] == "manual"
    assert EntityLink.query.filter_by(
        source_entity_id=task["id"],
        target_entity_id=project["id"],
        relationship_type="parent",
    ).first() is not None


def test_invalid_relationship_type_rejected(client):
    task = _create_entity(client, "task", "Write docs")
    project = _create_entity(client, "project", "Docs project")

    response = _create_link(client, task["id"], project["id"], "invalid_type")

    assert response.status_code == 400
    assert "relationship_type" in response.get_json()["error"].lower()


def test_blocks_cycle_rejected(client):
    task_a = _create_entity(client, "task", "Task A")
    task_b = _create_entity(client, "task", "Task B")

    assert _create_link(client, task_a["id"], task_b["id"], "blocks").status_code == 201
    response = _create_link(client, task_b["id"], task_a["id"], "blocks")

    assert response.status_code == 409
    assert "cycle" in response.get_json()["error"].lower()


def test_entity_type_compatibility_rejected(client):
    task = _create_entity(client, "task", "Write docs")
    person = _create_entity(client, "person", "Henry")

    response = _create_link(client, task["id"], person["id"], "parent")

    assert response.status_code == 400
    assert "not allowed" in response.get_json()["error"].lower()


def test_link_records_manual_actor_and_source(client, app):
    note = _create_entity(client, "note", "Source note")
    person = _create_entity(client, "person", "Henry")

    response = _create_link(client, note["id"], person["id"], "mentions")

    assert response.status_code == 201
    link = response.get_json()["data"]
    assert link["source"] == "manual"
    with app.app_context():
        event = EntityEvent.query.filter_by(
            entity_id=note["id"], event_type="relationship_added"
        ).one()
        assert event.actor == "user"
        assert event.new_value["relationship_type"] == "mentions"


def test_duplicate_link_rejected(client):
    task = _create_entity(client, "task", "Write docs")
    project = _create_entity(client, "project", "Docs project")

    first = _create_link(client, task["id"], project["id"], "parent")
    second = _create_link(client, task["id"], project["id"], "parent")

    assert first.status_code == 201
    assert second.status_code == 409
    assert "duplicate" in second.get_json()["error"].lower()


def test_self_link_rejected(client):
    task = _create_entity(client, "task", "Write docs")

    response = _create_link(client, task["id"], task["id"], "related")

    assert response.status_code == 400
    assert "self-link" in response.get_json()["error"].lower()


def test_missing_target_id_rejected(client):
    task = _create_entity(client, "task", "Write docs")

    response = client.post(f"/api/v4/entities/{task['id']}/links", json={"relationship_type": "parent"})

    assert response.status_code == 400
    assert "target_id" in response.get_json()["error"].lower()


def test_create_link_does_not_affect_existing_relationships_endpoint(client):
    """The existing /relationships endpoint continues to work unchanged."""
    task = _create_entity(client, "task", "Write docs")
    project = _create_entity(client, "project", "Docs project")

    response = client.post(
        f"/api/v4/entities/{task['id']}/relationships",
        json={"target_entity_id": project["id"], "relationship_type": "parent"},
    )

    assert response.status_code == 201
    assert response.get_json()["data"]["relationship_type"] == "parent"
