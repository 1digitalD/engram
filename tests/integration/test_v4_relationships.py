"""Cycle 3 tests for the v4 EntityLink relationship API."""

from models import EntityEvent, EntityLink


def _create_entity(client, entity_type, title):
    response = client.post("/api/v4/entities", json={"type": entity_type, "title": title})
    assert response.status_code == 201
    return response.get_json()["data"]


def _create_relationship(client, source_id, target_id, relationship_type):
    return client.post(
        f"/api/v4/entities/{source_id}/relationships",
        json={"target_entity_id": target_id, "relationship_type": relationship_type},
    )


def test_task_parent_project(client):
    task = _create_entity(client, "task", "Follow up")
    project = _create_entity(client, "project", "Memory Lookup")

    response = _create_relationship(client, task["id"], project["id"], "parent")

    assert response.status_code == 201
    link = response.get_json()["data"]
    assert link["source_entity_id"] == task["id"]
    assert link["target_entity_id"] == project["id"]
    assert link["relationship_type"] == "parent"
    assert {"src_id", "dst_id", "link_type"}.isdisjoint(link)


def test_project_parent_area(client):
    project = _create_entity(client, "project", "Memory Lookup")
    area = _create_entity(client, "area", "Agent Platform")

    response = _create_relationship(client, project["id"], area["id"], "parent")

    assert response.status_code == 201
    assert response.get_json()["data"]["relationship_type"] == "parent"


def test_note_mentions_person(client):
    note = _create_entity(client, "note", "Talked to Henry")
    person = _create_entity(client, "person", "Henry")

    response = _create_relationship(client, note["id"], person["id"], "mentions")

    assert response.status_code == 201
    assert response.get_json()["data"]["relationship_type"] == "mentions"


def test_task_derived_from_note(client):
    task = _create_entity(client, "task", "Ask Henry")
    note = _create_entity(client, "note", "Talked to Henry")

    response = _create_relationship(client, task["id"], note["id"], "derived_from")

    assert response.status_code == 201
    assert response.get_json()["data"]["relationship_type"] == "derived_from"


def test_relationship_create_writes_event(client, app):
    note = _create_entity(client, "note", "Talked to Henry")
    person = _create_entity(client, "person", "Henry")

    response = _create_relationship(client, note["id"], person["id"], "mentions")

    assert response.status_code == 201
    with app.app_context():
        event = EntityEvent.query.filter_by(
            entity_id=note["id"], event_type="relationship_added"
        ).one()
        assert event.new_value["relationship_type"] == "mentions"
        assert event.new_value["target_entity_id"] == person["id"]


def test_duplicate_relationship_rejected(client):
    task = _create_entity(client, "task", "Follow up")
    project = _create_entity(client, "project", "Memory Lookup")

    first = _create_relationship(client, task["id"], project["id"], "parent")
    second = _create_relationship(client, task["id"], project["id"], "parent")

    assert first.status_code == 201
    assert second.status_code == 409
    assert "duplicate" in second.get_json()["error"]


def test_self_link_rejected(client):
    task = _create_entity(client, "task", "Follow up")

    response = _create_relationship(client, task["id"], task["id"], "related")

    assert response.status_code == 400
    assert "self-link" in response.get_json()["error"]


def test_blocks_cycle_rejected(client):
    task_a = _create_entity(client, "task", "Write spec")
    task_b = _create_entity(client, "task", "Implement spec")

    first = _create_relationship(client, task_a["id"], task_b["id"], "blocks")
    second = _create_relationship(client, task_b["id"], task_a["id"], "blocks")

    assert first.status_code == 201
    assert second.status_code == 409
    assert "cycle" in second.get_json()["error"]


def test_blocks_cycle_rejected_via_update(client, app):
    task_a = _create_entity(client, "task", "Write spec")
    task_b = _create_entity(client, "task", "Implement spec")
    task_c = _create_entity(client, "task", "Ship feature")

    assert _create_relationship(client, task_a["id"], task_b["id"], "blocks").status_code == 201
    assert _create_relationship(client, task_b["id"], task_c["id"], "blocks").status_code == 201

    # c->a as "related" is fine, but turning it into "blocks" would close the
    # cycle a->b->c->a.
    third = _create_relationship(client, task_c["id"], task_a["id"], "related")
    assert third.status_code == 201
    third_id = third.get_json()["data"]["id"]

    update_response = client.patch(
        f"/api/v4/relationships/{third_id}",
        json={"relationship_type": "blocks"},
    )
    assert update_response.status_code == 409
    assert "cycle" in update_response.get_json()["error"]


def test_relationship_delete_writes_event(client, app):
    task = _create_entity(client, "task", "Ask Henry")
    note = _create_entity(client, "note", "Talked to Henry")
    created = _create_relationship(client, task["id"], note["id"], "derived_from").get_json()["data"]

    response = client.delete(f"/api/v4/relationships/{created['id']}")

    assert response.status_code == 200
    assert response.get_json()["data"]["deleted"] is True
    with app.app_context():
        assert EntityLink.query.count() == 0
        event = EntityEvent.query.filter_by(
            entity_id=task["id"], event_type="relationship_removed"
        ).one()
        assert event.old_value["relationship_type"] == "derived_from"


def test_relationship_update_writes_update_event(client, app):
    task = _create_entity(client, "task", "Ask Henry")
    note = _create_entity(client, "note", "Talked to Henry")
    created = _create_relationship(client, task["id"], note["id"], "related").get_json()["data"]

    response = client.patch(
        f"/api/v4/relationships/{created['id']}",
        json={"relationship_type": "derived_from", "evidence": "explicit follow-up source"},
    )

    assert response.status_code == 200
    updated = response.get_json()["data"]
    assert updated["relationship_type"] == "derived_from"
    assert updated["evidence"] == "explicit follow-up source"

    with app.app_context():
        event = EntityEvent.query.filter_by(
            entity_id=task["id"], event_type="relationship_updated"
        ).one()
        assert event.old_value["relationship_type"] == "related"
        assert event.new_value["relationship_type"] == "derived_from"


def test_get_relationships_returns_incoming_and_outgoing(client):
    task = _create_entity(client, "task", "Ask Henry")
    note = _create_entity(client, "note", "Talked to Henry")
    person = _create_entity(client, "person", "Henry")
    _create_relationship(client, task["id"], note["id"], "derived_from")
    _create_relationship(client, note["id"], person["id"], "mentions")

    response = client.get(f"/api/v4/entities/{note['id']}/relationships")

    assert response.status_code == 200
    data = response.get_json()
    assert len(data["incoming"]) == 1
    assert len(data["outgoing"]) == 1
