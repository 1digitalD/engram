"""Cycle 9 tests for v4 relationship-aware detail payloads."""

from extensions import db
from models import AppSetting


def _create_entity(client, entity_type, title, status=None):
    payload = {
        "type": entity_type,
        "title": title,
        "content": f"{title} content",
    }
    if status:
        payload["status"] = status
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


def _section_map(detail):
    return {section["key"]: section for section in detail["sections"]}


def test_task_detail_has_type_specific_relationship_sections(client):
    task_id = _create_entity(client, "task", "Follow up")
    project_id = _create_entity(client, "project", "Memory Lookup")
    area_id = _create_entity(client, "area", "Agent Platform")
    person_id = _create_entity(client, "person", "Henry")
    source_note_id = _create_entity(client, "note", "Source note")
    resource_id = _create_entity(client, "resource", "Rollout checklist")
    blocker_id = _create_entity(client, "task", "Blocked task", status="blocked")
    _link(client, task_id, project_id, "parent")
    _link(client, task_id, area_id, "parent")
    _link(client, task_id, person_id, "assigned_to")
    _link(client, task_id, source_note_id, "derived_from")
    _link(client, task_id, resource_id, "references")
    _link(client, blocker_id, task_id, "blocks")

    response = client.get(f"/api/v4/entities/{task_id}/detail")

    assert response.status_code == 200
    detail = response.get_json()
    assert detail["entity"]["id"] == task_id
    sections = _section_map(detail)
    assert set(sections) >= {"project", "area", "people", "source_notes", "resources", "blocking"}
    assert [item["entity"]["id"] for item in sections["project"]["items"]] == [project_id]
    assert [item["entity"]["id"] for item in sections["area"]["items"]] == [area_id]
    assert [item["entity"]["id"] for item in sections["people"]["items"]] == [person_id]
    assert [item["entity"]["id"] for item in sections["source_notes"]["items"]] == [source_note_id]
    assert [item["entity"]["id"] for item in sections["resources"]["items"]] == [resource_id]
    assert [item["entity"]["id"] for item in sections["blocking"]["items"]] == [blocker_id]
    assert "links" not in detail


def test_project_detail_has_area_tasks_notes_resources_people_sections(client):
    project_id = _create_entity(client, "project", "Memory Lookup")
    area_id = _create_entity(client, "area", "Agent Platform")
    open_task_id = _create_entity(client, "task", "Open task")
    done_task_id = _create_entity(client, "task", "Done task", status="done")
    note_id = _create_entity(client, "note", "Project note")
    resource_id = _create_entity(client, "resource", "Project resource")
    person_id = _create_entity(client, "person", "Henry")
    _link(client, project_id, area_id, "parent")
    _link(client, open_task_id, project_id, "parent")
    _link(client, done_task_id, project_id, "parent")
    _link(client, note_id, project_id, "related")
    _link(client, resource_id, project_id, "references")
    _link(client, project_id, person_id, "assigned_to")

    response = client.get(f"/api/v4/entities/{project_id}/detail")

    assert response.status_code == 200
    sections = _section_map(response.get_json())
    assert set(sections) >= {"area", "open_tasks", "completed_tasks", "notes", "resources", "people"}
    assert [item["entity"]["id"] for item in sections["area"]["items"]] == [area_id]
    assert [item["entity"]["id"] for item in sections["open_tasks"]["items"]] == [open_task_id]
    assert [item["entity"]["id"] for item in sections["completed_tasks"]["items"]] == [done_task_id]
    assert [item["entity"]["id"] for item in sections["notes"]["items"]] == [note_id]
    assert [item["entity"]["id"] for item in sections["resources"]["items"]] == [resource_id]
    assert [item["entity"]["id"] for item in sections["people"]["items"]] == [person_id]


def test_note_detail_has_projects_areas_people_tasks_resources_sections(client):
    note_id = _create_entity(client, "note", "Source note")
    project_id = _create_entity(client, "project", "Memory Lookup")
    area_id = _create_entity(client, "area", "Agent Platform")
    person_id = _create_entity(client, "person", "Henry")
    task_id = _create_entity(client, "task", "Derived task")
    resource_id = _create_entity(client, "resource", "Runbook")
    _link(client, note_id, project_id, "related")
    _link(client, note_id, area_id, "related")
    _link(client, note_id, person_id, "mentions")
    _link(client, task_id, note_id, "derived_from")
    _link(client, note_id, resource_id, "references")

    response = client.get(f"/api/v4/entities/{note_id}/detail")

    assert response.status_code == 200
    sections = _section_map(response.get_json())
    assert set(sections) >= {"projects", "areas", "people_mentioned", "derived_tasks", "referenced_resources"}
    assert [item["entity"]["id"] for item in sections["projects"]["items"]] == [project_id]
    assert [item["entity"]["id"] for item in sections["areas"]["items"]] == [area_id]
    assert [item["entity"]["id"] for item in sections["people_mentioned"]["items"]] == [person_id]
    assert [item["entity"]["id"] for item in sections["derived_tasks"]["items"]] == [task_id]
    assert [item["entity"]["id"] for item in sections["referenced_resources"]["items"]] == [resource_id]


def test_person_detail_exposes_owner_identity_and_owner_endpoint(client, app):
    person_id = _create_entity(client, "person", "Danish")

    detail_response = client.get(f"/api/v4/entities/{person_id}/detail")
    assert detail_response.status_code == 200
    assert detail_response.get_json()["entity"]["is_owner"] is False

    mark_response = client.post(f"/api/v4/entities/{person_id}/owner")
    assert mark_response.status_code == 200
    assert mark_response.get_json()["data"] == {
        "owner_person_id": person_id,
        "is_owner": True,
    }

    with app.app_context():
        setting = db.session.get(AppSetting, "owner_person_id")
        assert setting is not None
        assert setting.value == person_id

    detail_response = client.get(f"/api/v4/entities/{person_id}/detail")
    assert detail_response.status_code == 200
    assert detail_response.get_json()["entity"]["is_owner"] is True

    clear_response = client.delete(f"/api/v4/entities/{person_id}/owner")
    assert clear_response.status_code == 200
    assert clear_response.get_json()["data"] == {
        "owner_person_id": None,
        "is_owner": False,
    }

    with app.app_context():
        setting = db.session.get(AppSetting, "owner_person_id")
        assert setting is not None
        assert setting.value is None
