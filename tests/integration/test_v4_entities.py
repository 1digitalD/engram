"""Cycle 2 tests for the v4 canonical entity API."""

from datetime import datetime, timezone

from app import create_app
from extensions import db
from models import Entity, EntityEvent, Job, Tag
from services import runtime_health


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


def test_v4_health_reports_backend_unavailable_when_db_probe_fails(client, monkeypatch):
    monkeypatch.setattr(
        runtime_health,
        "probe_database_connection",
        lambda: (False, "psycopg2.OperationalError: connection refused"),
    )

    response = client.get("/api/v4/health")

    assert response.status_code == 503
    body = response.get_json()
    assert body["status"] == "error"
    assert body["dependency"] == "postgres"
    assert body["message"] == "Engram backend unavailable"
    assert "connection refused" in body["reason"]


def test_app_health_reports_backend_unavailable_when_db_probe_fails(client, monkeypatch):
    monkeypatch.setattr(
        runtime_health,
        "probe_database_connection",
        lambda: (False, "psycopg2.OperationalError: connection refused"),
    )

    response = client.get("/health")

    assert response.status_code == 503
    body = response.get_json()
    assert body["status"] == "error"
    assert body["dependency"] == "postgres"
    assert body["message"] == "Engram backend unavailable"
    assert body["db"] == "error"


def test_create_app_marks_backend_unavailable_when_db_probe_fails(monkeypatch):
    monkeypatch.setattr(
        runtime_health,
        "probe_database_connection",
        lambda: (False, "database unavailable for startup"),
    )

    app = create_app("testing")

    assert app.config["DATABASE_READY"] is False
    assert app.config["DATABASE_UNAVAILABLE_REASON"] == "database unavailable for startup"


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


def test_list_people_includes_note_task_project_link_counts(client, app):
    person = client.post(
        "/api/v4/entities",
        json={"type": "person", "title": "Akash"},
    ).get_json()["data"]
    note = client.post(
        "/api/v4/entities",
        json={"type": "note", "title": "Akash sync note"},
    ).get_json()["data"]
    note_wrong_direction = client.post(
        "/api/v4/entities",
        json={"type": "note", "title": "Akash related note"},
    ).get_json()["data"]
    task = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Follow up with Akash"},
    ).get_json()["data"]
    task_wrong_direction = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Akash shadow task"},
    ).get_json()["data"]
    project = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "Platform coordination"},
    ).get_json()["data"]
    outgoing_project = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "People systems"},
    ).get_json()["data"]

    for source_id, relationship_type in (
        (note["id"], "mentions"),
        (task["id"], "assigned_to"),
        (project["id"], "assigned_to"),
    ):
        response = client.post(
            f"/api/v4/entities/{source_id}/relationships",
            json={"target_entity_id": person["id"], "relationship_type": relationship_type},
        )
        assert response.status_code == 201

    response = client.post(
        f"/api/v4/entities/{person['id']}/relationships",
        json={"target_entity_id": note_wrong_direction["id"], "relationship_type": "related"},
    )
    assert response.status_code == 201
    response = client.post(
        f"/api/v4/entities/{person['id']}/relationships",
        json={"target_entity_id": task_wrong_direction["id"], "relationship_type": "related"},
    )
    assert response.status_code == 201
    response = client.post(
        f"/api/v4/entities/{person['id']}/relationships",
        json={"target_entity_id": outgoing_project["id"], "relationship_type": "related"},
    )
    assert response.status_code == 201

    list_response = client.get("/api/v4/entities?type=person")

    assert list_response.status_code == 200
    row = list_response.get_json()["data"][0]
    assert row["id"] == person["id"]
    assert row["linked_counts"] == {
        "notes": 1,
        "tasks": 1,
        "projects": 2,
    }


def test_list_areas_includes_note_task_project_link_counts(client, app):
    area = client.post(
        "/api/v4/entities",
        json={"type": "area", "title": "Execution"},
    ).get_json()["data"]
    note = client.post(
        "/api/v4/entities",
        json={"type": "note", "title": "Execution note"},
    ).get_json()["data"]
    outgoing_note = client.post(
        "/api/v4/entities",
        json={"type": "note", "title": "Execution retrospective"},
    ).get_json()["data"]
    task = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Execution task"},
    ).get_json()["data"]
    outgoing_task = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Execution follow-up"},
    ).get_json()["data"]
    project = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "Execution project"},
    ).get_json()["data"]
    outgoing_project = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "Execution orbit"},
    ).get_json()["data"]

    for source_id, relationship_type in (
        (note["id"], "mentions"),
        (task["id"], "parent"),
        (project["id"], "parent"),
    ):
        response = client.post(
            f"/api/v4/entities/{source_id}/relationships",
            json={"target_entity_id": area["id"], "relationship_type": relationship_type},
        )
        assert response.status_code == 201

    response = client.post(
        f"/api/v4/entities/{area['id']}/relationships",
        json={"target_entity_id": outgoing_note["id"], "relationship_type": "related"},
    )
    assert response.status_code == 201
    response = client.post(
        f"/api/v4/entities/{area['id']}/relationships",
        json={"target_entity_id": outgoing_task["id"], "relationship_type": "related"},
    )
    assert response.status_code == 201
    response = client.post(
        f"/api/v4/entities/{area['id']}/relationships",
        json={"target_entity_id": outgoing_project["id"], "relationship_type": "related"},
    )
    assert response.status_code == 201

    list_response = client.get("/api/v4/entities?type=area")

    assert list_response.status_code == 200
    row = list_response.get_json()["data"][0]
    assert row["id"] == area["id"]
    assert row["linked_counts"] == {
        "notes": 2,
        "tasks": 1,
        "projects": 1,
    }


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


def test_project_updated_at_advances_when_task_is_linked_via_parent(client, app):
    """A project's updated_at should advance when a task is parent-linked to it."""
    project = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "Propagation Test Project"},
    ).get_json()["data"]
    task = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Propagation Test Task"},
    ).get_json()["data"]

    import time
    time.sleep(0.1)  # Ensure timestamps differ

    old_updated = project["updated_at"]

    # Link task → project (parent)
    link_resp = client.post(
        f"/api/v4/entities/{task['id']}/relationships",
        json={"target_entity_id": project["id"], "relationship_type": "parent"},
    )
    assert link_resp.status_code == 201

    # Project's updated_at should have advanced
    project_after = client.get(f"/api/v4/entities/{project['id']}").get_json()["data"]
    assert project_after["updated_at"] > old_updated, (
        f"project updated_at should advance after task parent link: "
        f"{project_after['updated_at']} <= {old_updated}"
    )


def test_project_updated_at_advances_when_child_task_is_updated(client, app):
    """A project's updated_at should advance when a child task's status changes."""
    project = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "Task Update Project"},
    ).get_json()["data"]
    task = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Child Task", "status": "open"},
    ).get_json()["data"]

    # Link task → project
    client.post(
        f"/api/v4/entities/{task['id']}/relationships",
        json={"target_entity_id": project["id"], "relationship_type": "parent"},
    )

    import time
    time.sleep(0.1)

    old_updated = client.get(f"/api/v4/entities/{project['id']}").get_json()["data"]["updated_at"]

    # Update task status
    client.patch(
        f"/api/v4/entities/{task['id']}",
        json={"status": "done"},
    )

    # Project's updated_at should have advanced
    project_after = client.get(f"/api/v4/entities/{project['id']}").get_json()["data"]
    assert project_after["updated_at"] > old_updated, (
        f"project updated_at should advance after child task update: "
        f"{project_after['updated_at']} <= {old_updated}"
    )


def test_task_rows_carry_parent_context_entities(client, app):
    """Task list rows include parent project/area refs and assignee refs."""
    from extensions import db
    from models import EntityLink

    project = client.post("/api/v4/entities", json={"type": "project", "title": "Memory Lookup"}).get_json()["data"]
    area = client.post("/api/v4/entities", json={"type": "area", "title": "Execution"}).get_json()["data"]
    person = client.post("/api/v4/entities", json={"type": "person", "title": "Priya"}).get_json()["data"]
    task = client.post("/api/v4/entities", json={"type": "task", "title": "Ship rollout"}).get_json()["data"]
    with app.app_context():
        db.session.add(EntityLink(
            source_entity_id=task["id"],
            target_entity_id=project["id"],
            relationship_type="parent",
        ))
        db.session.add(EntityLink(
            source_entity_id=task["id"],
            target_entity_id=area["id"],
            relationship_type="parent",
        ))
        db.session.add(EntityLink(
            source_entity_id=task["id"],
            target_entity_id=person["id"],
            relationship_type="assigned_to",
        ))
        db.session.commit()

    rows = client.get("/api/v4/entities?type=task").get_json()["data"]
    row = next(r for r in rows if r["id"] == task["id"])
    assert row["projects"] == [{"id": project["id"], "title": "Memory Lookup"}]
    assert row["areas"] == [{"id": area["id"], "title": "Execution"}]
    assert row["people"] == [{"id": person["id"], "title": "Priya"}]

    # Projects themselves don't get the field populated
    project_rows = client.get("/api/v4/entities?type=project").get_json()["data"]
    assert all(r["projects"] == [] for r in project_rows)
    assert all(r["areas"] == [] for r in project_rows)
    assert all(r["people"] == [] for r in project_rows)
