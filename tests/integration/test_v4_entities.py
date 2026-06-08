"""Cycle 2 tests for the v4 canonical entity API."""

from datetime import datetime, timezone

from extensions import db
from models import Entity, EntityEvent, Job, Tag


FORBIDDEN_DTO_FIELDS = {
    "raw_text",
    "name",
    "is_archived",
    "project_id",
    "project_ids",
    "area_id",
    "person_id",
    "note_id",
    "parent_id",
    "due_date",
}


def test_v4_health(client):
    response = client.get("/api/v4/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_create_all_v4_entity_types(client):
    expected_status = {
        "note": "active",
        "task": "open",
        "project": "active",
        "area": "active",
        "resource": "active",
        "person": "active",
    }

    for entity_type in ("note", "task", "project", "area", "resource", "person"):
        response = client.post(
            "/api/v4/entities",
            json={
                "type": entity_type,
                "title": f"Test {entity_type}",
                "content": "Body",
                "source": "manual",
            },
        )

        assert response.status_code == 201
        entity = response.get_json()["data"]
        assert entity["type"] == entity_type
        assert entity["status"] == expected_status[entity_type]
        assert entity["lifecycle"] == "active"
        assert FORBIDDEN_DTO_FIELDS.isdisjoint(entity)


def test_create_entity_with_tags_and_event(client, app):
    response = client.post(
        "/api/v4/entities",
        json={
            "type": "task",
            "title": "Follow up with Henry",
            "content": "Ask for rollout stages.",
            "status": "waiting",
            "due_at": "2026-05-19T17:00:00+00:00",
            "follow_up_at": "2026-05-20T10:00:00+00:00",
            "properties": {"priority": "high"},
            "tags": ["memory", "rollout"],
        },
    )

    assert response.status_code == 201
    entity = response.get_json()["data"]
    assert entity["due_at"] == "2026-05-19T17:00:00+00:00"
    assert entity["properties"] == {"priority": "high"}
    assert {tag["name"] for tag in entity["tags"]} == {"memory", "rollout"}
    assert entity["ai"]["status"] == "pending"

    with app.app_context():
        stored = db.session.get(Entity, entity["id"])
        assert stored is not None
        assert Tag.query.count() == 2
        event = EntityEvent.query.filter_by(entity_id=entity["id"], event_type="created").one()
        assert event.actor == "user"
        assert event.new_value["type"] == "task"
        job = Job.query.filter_by(entity_id=entity["id"], job_type="embed").one()
        assert job.payload["reason"] == "entity_create"


def test_get_and_list_entities(client):
    created = client.post(
        "/api/v4/entities",
        json={"type": "note", "title": "Source note", "content": "Original"},
    ).get_json()["data"]

    get_response = client.get(f"/api/v4/entities/{created['id']}")
    list_response = client.get("/api/v4/entities?type=note")

    assert get_response.status_code == 200
    assert get_response.get_json()["data"]["id"] == created["id"]
    assert list_response.status_code == 200
    assert [row["id"] for row in list_response.get_json()["data"]] == [created["id"]]


def test_update_entity_fields_tags_and_event(client):
    created = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Old", "tags": ["old"]},
    ).get_json()["data"]

    response = client.patch(
        f"/api/v4/entities/{created['id']}",
        json={
            "title": "New",
            "content": "Updated body",
            "status": "in_progress",
            "due_at": "2026-05-21T17:00:00+00:00",
            "follow_up_at": "2026-05-21T09:30:00+00:00",
            "properties": {"priority": "medium"},
            "tags": ["new", "work"],
        },
    )

    assert response.status_code == 200
    entity = response.get_json()["data"]
    assert entity["title"] == "New"
    assert entity["content"] == "Updated body"
    assert entity["status"] == "in_progress"
    assert entity["due_at"] == "2026-05-21T17:00:00+00:00"
    assert entity["properties"] == {"priority": "medium"}
    assert {tag["name"] for tag in entity["tags"]} == {"new", "work"}

    events = client.get(f"/api/v4/entities/{created['id']}/events").get_json()["data"]
    assert {"status_changed", "updated"}.issubset({event["event_type"] for event in events})

    with client.application.app_context():
        jobs = Job.query.filter_by(entity_id=created["id"], job_type="embed").all()
        assert len(jobs) == 2
        assert jobs[-1].payload["reason"] == "entity_update"


def test_reject_invalid_follow_up_at_on_create_without_mutation(client, app):
    response = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Bad date", "follow_up_at": "not-a-date"},
    )

    assert response.status_code == 400
    assert "invalid datetime" in response.get_json()["error"]
    with app.app_context():
        assert Entity.query.filter_by(type="task", title="Bad date").count() == 0


def test_reject_invalid_due_at_on_create_without_mutation(client, app):
    response = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Bad due date", "due_at": "not-a-date"},
    )

    assert response.status_code == 400
    assert "invalid datetime" in response.get_json()["error"]
    with app.app_context():
        assert Entity.query.filter_by(type="task", title="Bad due date").count() == 0


def test_reject_invalid_follow_up_at_on_update_without_mutation(client, app):
    created = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Keep date", "follow_up_at": "2026-05-20T10:00:00+00:00"},
    ).get_json()["data"]

    response = client.patch(
        f"/api/v4/entities/{created['id']}",
        json={"follow_up_at": "not-a-date"},
    )

    assert response.status_code == 400
    assert "invalid datetime" in response.get_json()["error"]
    with app.app_context():
        stored = db.session.get(Entity, created["id"])
        assert stored.title == "Keep date"
        assert stored.follow_up_at == datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc)


def test_archive_and_delete_write_events(client, app):
    archived = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "Project"},
    ).get_json()["data"]
    deleted = client.post(
        "/api/v4/entities",
        json={"type": "note", "title": "Note"},
    ).get_json()["data"]

    archive_response = client.patch(
        f"/api/v4/entities/{archived['id']}",
        json={"lifecycle": "archived"},
    )
    delete_response = client.delete(f"/api/v4/entities/{deleted['id']}")

    assert archive_response.status_code == 200
    assert archive_response.get_json()["data"]["lifecycle"] == "archived"
    assert delete_response.status_code == 200
    assert delete_response.get_json()["data"]["lifecycle"] == "deleted"

    with app.app_context():
        archived_event = EntityEvent.query.filter_by(
            entity_id=archived["id"], event_type="archived"
        ).one()
        deleted_event = EntityEvent.query.filter_by(
            entity_id=deleted["id"], event_type="deleted"
        ).one()
        assert archived_event.actor == "user"
        assert deleted_event.actor == "user"


def test_deleted_entities_excluded_from_list_by_default(client):
    active = client.post(
        "/api/v4/entities",
        json={"type": "note", "title": "Active note"},
    ).get_json()["data"]
    to_delete = client.post(
        "/api/v4/entities",
        json={"type": "note", "title": "Deleted note"},
    ).get_json()["data"]

    client.delete(f"/api/v4/entities/{to_delete['id']}")

    list_response = client.get("/api/v4/entities?type=note")
    ids = [e["id"] for e in list_response.get_json()["data"]]

    assert active["id"] in ids
    assert to_delete["id"] not in ids

    # explicitly requesting deleted lifecycle should return it
    deleted_response = client.get("/api/v4/entities?type=note&lifecycle=deleted")
    deleted_ids = [e["id"] for e in deleted_response.get_json()["data"]]
    assert to_delete["id"] in deleted_ids


def test_reject_relationship_ids_in_properties(client):
    for key in ("project_id", "area_id", "person_id", "note_id", "source_note_id", "parent_id"):
        response = client.post(
            "/api/v4/entities",
            json={
                "type": "task",
                "title": "Invalid",
                "properties": {key: "00000000-0000-0000-0000-000000000001"},
            },
        )

        assert response.status_code == 400
        assert "relationship IDs" in response.get_json()["error"]


def test_reject_invalid_status_for_type(client):
    response = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Bad status", "status": "active"},
    )

    assert response.status_code == 400
    assert "invalid status" in response.get_json()["error"]
