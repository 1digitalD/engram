from datetime import datetime, timedelta, timezone

from extensions import db
from models import Entity, EntityLink


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
    return response.get_json()["data"]


def _task_board(client, **params):
    return client.get("/api/v4/task-board", query_string=params)


def _items_by_title(payload):
    return {
        item["title"]: item
        for group in payload["data"]["groups"]
        for item in group["items"]
    }


def test_task_board_groups_by_project_and_filters_status(client):
    project = _create_entity(client, "project", "Apollo")
    area = _create_entity(client, "area", "Operations")
    person = _create_entity(client, "person", "Sam")
    open_task = _create_entity(client, "task", "Open item", status="open")
    done_task = _create_entity(client, "task", "Done item", status="done")
    area_task = _create_entity(client, "task", "Area only", status="open")

    _link(client, open_task["id"], project["id"], "parent")
    _link(client, open_task["id"], person["id"], "assigned_to")
    _link(client, done_task["id"], project["id"], "parent")
    _link(client, area_task["id"], area["id"], "parent")

    default_response = _task_board(client)
    assert default_response.status_code == 200
    default_payload = default_response.get_json()
    assert default_payload["meta"]["total"] == 2
    titles = set(_items_by_title(default_payload))
    assert titles == {"Open item", "Area only"}

    groups = {group["label"]: group for group in default_payload["data"]["groups"]}
    assert "Apollo" in groups
    assert "Operations" in groups
    assert groups["Apollo"]["kind"] == "project"
    assert groups["Operations"]["kind"] == "area"
    assert groups["Apollo"]["items"][0]["owner"]["title"] == "Sam"

    with_done = _task_board(client, status="open,done")
    assert with_done.get_json()["meta"]["total"] == 3
    assert default_payload["meta"]["counts"]["by_status"]["done"] == 1


def test_task_board_filters_assignee_and_sorts_follow_up(client, app):
    project = _create_entity(client, "project", "Beta")
    sam = _create_entity(client, "person", "Sam")
    alex = _create_entity(client, "person", "Alex")
    soon = _create_entity(
        client,
        "task",
        "Soon follow-up",
        status="open",
        follow_up_at=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
    )
    later = _create_entity(
        client,
        "task",
        "Later follow-up",
        status="open",
        follow_up_at=(datetime.now(timezone.utc) + timedelta(days=9)).isoformat(),
    )
    unassigned = _create_entity(client, "task", "Nobody", status="open")

    for task in (soon, later, unassigned):
        _link(client, task["id"], project["id"], "parent")
    _link(client, soon["id"], sam["id"], "assigned_to")
    _link(client, later["id"], alex["id"], "assigned_to")

    sam_response = _task_board(client, assignee=sam["id"])
    assert sam_response.get_json()["meta"]["total"] == 1
    assert _items_by_title(sam_response.get_json())["Soon follow-up"]["owner"]["id"] == sam["id"]

    unassigned_response = _task_board(client, assignee="unassigned")
    assert unassigned_response.get_json()["meta"]["total"] == 1
    assert "Nobody" in _items_by_title(unassigned_response.get_json())

    sorted_response = _task_board(client, sort="follow_up_at", order="asc")
    items = sorted_response.get_json()["data"]["groups"][0]["items"]
    assert [item["title"] for item in items] == ["Soon follow-up", "Later follow-up", "Nobody"]


def test_task_board_excludes_archived_project_parent(client, app):
    project = _create_entity(client, "project", "Archived")
    task = _create_entity(client, "task", "Hidden", status="open")
    _link(client, task["id"], project["id"], "parent")

    with app.app_context():
        entity = db.session.get(Entity, project["id"])
        entity.lifecycle = "archived"
        db.session.commit()

    response = _task_board(client)
    assert response.get_json()["meta"]["total"] == 0


def test_task_board_prefers_project_parent_over_area(client):
    project = _create_entity(client, "project", "Apollo")
    area = _create_entity(client, "area", "Ops")
    task = _create_entity(client, "task", "Dual parent", status="open")
    _link(client, task["id"], project["id"], "parent")
    _link(client, task["id"], area["id"], "parent")

    response = _task_board(client)
    groups = {group["label"]: group for group in response.get_json()["data"]["groups"]}
    assert list(groups) == ["Apollo"]
    assert groups["Apollo"]["items"][0]["space"]["type"] == "project"


def test_task_board_orphan_tasks_bucket(client):
    orphan = _create_entity(client, "task", "Orphan", status="open")
    response = _task_board(client)
    groups = response.get_json()["data"]["groups"]
    assert len(groups) == 1
    assert groups[0]["label"] == "No project"
    assert groups[0]["items"][0]["id"] == orphan["id"]
