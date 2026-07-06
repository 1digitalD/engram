"""Integration tests for task parent context on detail and search surfaces."""

from extensions import db
from models import EntityLink
from tests.assertions import parent_context_ref


def _create_entity(client, entity_type, title, **extra):
    payload = {"type": entity_type, "title": title, "content": f"{title} content", **extra}
    response = client.post("/api/v4/entities", json=payload)
    assert response.status_code == 201
    return response.get_json()["data"]


def _link(client, source_id, target_id, relationship_type):
    response = client.post(
        f"/api/v4/entities/{source_id}/relationships",
        json={"target_entity_id": target_id, "relationship_type": relationship_type},
    )
    assert response.status_code == 201


def _attach_parent_links(app, task_id, project_id, area_id):
    with app.app_context():
        db.session.add(EntityLink(
            source_entity_id=task_id,
            target_entity_id=project_id,
            relationship_type="parent",
        ))
        db.session.add(EntityLink(
            source_entity_id=task_id,
            target_entity_id=area_id,
            relationship_type="parent",
        ))
        db.session.commit()


def test_person_detail_current_load_includes_task_parent_context(client, app):
    person = _create_entity(client, "person", "Akash")
    project = _create_entity(client, "project", "Memory Lookup")
    area = _create_entity(client, "area", "Execution")
    task = _create_entity(client, "task", "Ship rollout", status="open")

    _link(client, task["id"], person["id"], "assigned_to")
    _attach_parent_links(app, task["id"], project["id"], area["id"])

    response = client.get(f"/api/v4/entities/{person['id']}/detail")
    assert response.status_code == 200
    data = response.get_json()

    load_item = next(item for item in data["current_load"] if item["task"]["id"] == task["id"])
    assert parent_context_ref(project["id"], "Memory Lookup")(load_item["task"]["projects"])
    assert parent_context_ref(area["id"], "Execution")(load_item["task"]["areas"])


def test_project_detail_pulse_includes_task_parent_context(client, app):
    project = _create_entity(client, "project", "Agent Platform")
    area = _create_entity(client, "area", "Engineering")
    task = _create_entity(client, "task", "Resolve blocker", status="blocked")

    _link(client, task["id"], project["id"], "parent")
    with app.app_context():
        db.session.add(EntityLink(
            source_entity_id=task["id"],
            target_entity_id=area["id"],
            relationship_type="parent",
        ))
        db.session.commit()

    response = client.get(f"/api/v4/entities/{project['id']}/detail")
    assert response.status_code == 200
    data = response.get_json()

    focus = data["project_pulse"]["focus_items"]
    task_item = next(item for item in focus if item["entity"]["id"] == task["id"])
    assert parent_context_ref(project["id"], "Agent Platform")(task_item["entity"]["projects"])
    assert parent_context_ref(area["id"], "Engineering")(task_item["entity"]["areas"])


def test_search_task_results_include_parent_context(client, app):
    project = _create_entity(client, "project", "Memory Lookup")
    area = _create_entity(client, "area", "Execution")
    task = _create_entity(client, "task", "Ship rollout unique", content="memory rollout checklist")

    _attach_parent_links(app, task["id"], project["id"], area["id"])

    response = client.get("/api/v4/search?q=rollout%20unique&mode=keyword")
    assert response.status_code == 200
    data = response.get_json()

    row = next(r for r in data["results"] if r["entity"]["id"] == task["id"])
    assert parent_context_ref(project["id"], "Memory Lookup")(row["entity"]["projects"])
    assert parent_context_ref(area["id"], "Execution")(row["entity"]["areas"])
