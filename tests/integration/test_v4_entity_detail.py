"""Integration tests for entity detail / events surface."""


def _create_entity(client, entity_type, title, **extra):
    payload = {"type": entity_type, "title": title, "content": f"{title} content"}
    payload.update(extra)
    response = client.post("/api/v4/entities", json=payload)
    assert response.status_code == 201
    return response.get_json()["data"]["id"]


def _link(client, source_id, target_id, relationship_type):
    response = client.post(
        f"/api/v4/entities/{source_id}/relationships",
        json={"target_entity_id": target_id, "relationship_type": relationship_type},
    )
    assert response.status_code == 201
    return response.get_json()["data"]["id"]


def test_events_endpoint_includes_narration_for_each_event(client):
    task_id = _create_entity(client, "task", "Narration smoke task")
    project_id = _create_entity(client, "project", "Narration smoke project")

    _link(client, task_id, project_id, "parent")
    response = client.patch(
        f"/api/v4/entities/{task_id}",
        json={"status": "in_progress"},
    )
    assert response.status_code == 200

    response = client.patch(
        f"/api/v4/entities/{task_id}",
        json={"title": "Narration smoke task updated"},
    )
    assert response.status_code == 200

    response = client.get(f"/api/v4/entities/{task_id}/events")
    assert response.status_code == 200
    events = response.get_json()["data"]
    assert len(events) >= 5, f"expected 5+ events, got {len(events)}"
    for event in events:
        assert "narration" in event, f"event {event['event_type']} missing narration"
        assert event["narration"], f"event {event['event_type']} has empty narration"


def test_events_narration_for_created_event(client):
    task_id = _create_entity(client, "task", "Cache smoke task")

    response = client.get(f"/api/v4/entities/{task_id}/events")
    events = response.get_json()["data"]
    created_event = next(e for e in events if e["event_type"] == "created")
    assert created_event["narration"].startswith("Created") or created_event["narration"].startswith("I created")


def test_project_detail_open_tasks_include_assignee_context(client):
    project_id = _create_entity(client, "project", "Owner context project")
    task_id = _create_entity(client, "task", "Delegated task")
    person_id = _create_entity(client, "person", "Delegated Person")

    _link(client, task_id, project_id, "parent")
    _link(client, task_id, person_id, "assigned_to")

    response = client.get(f"/api/v4/entities/{project_id}/detail")
    assert response.status_code == 200
    sections = {section["key"]: section for section in response.get_json()["sections"]}
    open_tasks = sections["open_tasks"]["items"]
    assert len(open_tasks) == 1
    entity = open_tasks[0]["entity"]
    assert entity["people"] == [{"id": person_id, "title": "Delegated Person"}]
