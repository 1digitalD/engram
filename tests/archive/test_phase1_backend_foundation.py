import json
from datetime import datetime

from extensions import db
from models import Area, Note, Priority, Project, Task, TaskStatus


def test_project_and_task_relationship_serialization(app):
    with app.app_context():
        area = Area(name="Ops", color="#112233")
        project = Project(name="Launch", area=area, priority=Priority.HIGH)
        note = Note(raw_text="Source note", area=area)
        task = Task(
            title="Follow up",
            project=project,
            area=area,
            source_note=note,
            status=TaskStatus.PENDING,
        )
        db.session.add_all([area, project, note, task])
        db.session.commit()

        project_dict = project.to_dict()
        area_dict = area.to_dict()
        note_dict = note.to_dict(include_relations=False)
        task_dict = task.to_dict()

        assert project_dict["area_id"] == area.id
        assert project_dict["area_name"] == "Ops"
        assert area_dict["project_count"] == 1
        assert area_dict["task_count"] == 1
        assert note_dict["task_count"] == 1
        assert task_dict["area_id"] == area.id
        assert task_dict["area_name"] == "Ops"
        assert task_dict["note_id"] == note.id


def test_list_projects_can_filter_by_area(client, app):
    with app.app_context():
        area_a = Area(name="Area A")
        area_b = Area(name="Area B")
        db.session.add_all([
            area_a,
            area_b,
            Project(name="Project A", area=area_a),
            Project(name="Project B", area=area_b),
        ])
        db.session.commit()

        res = client.get(f"/api/v1/projects?area_id={area_a.id}")
        assert res.status_code == 200
        data = json.loads(res.data)["data"]
        assert [item["name"] for item in data] == ["Project A"]


def test_task_api_supports_area_and_note_filters_and_fields(client, app):
    with app.app_context():
        area_a = Area(name="Area A")
        area_b = Area(name="Area B")
        note = Note(raw_text="Anchor note", area=area_a)
        project = Project(name="Project A", area=area_a)
        db.session.add_all([area_a, area_b, note, project])
        db.session.commit()

        create_res = client.post(
            "/api/v1/tasks",
            data=json.dumps({
                "title": "Task A",
                "project_id": project.id,
                "area_id": area_a.id,
                "note_id": note.id,
                "priority": "high",
            }),
            content_type="application/json",
        )
        assert create_res.status_code == 201
        task_id = json.loads(create_res.data)["data"]["id"]

        res = client.get(f"/api/v1/tasks?area_id={area_a.id}&note_id={note.id}")
        assert res.status_code == 200
        task_data = json.loads(res.data)["data"]
        assert len(task_data) == 1
        assert task_data[0]["id"] == task_id
        assert task_data[0]["area_id"] == area_a.id
        assert task_data[0]["note_id"] == note.id

        patch_res = client.patch(
            f"/api/v1/tasks/{task_id}",
            data=json.dumps({"area_id": area_b.id, "note_id": None}),
            content_type="application/json",
        )
        assert patch_res.status_code == 200
        patched = json.loads(patch_res.data)["data"]
        assert patched["area_id"] == area_b.id
        assert patched["note_id"] is None


def test_project_api_persists_area_id(client, app):
    with app.app_context():
        area = Area(name="Planning")
        db.session.add(area)
        db.session.commit()

        res = client.post(
            "/api/v1/projects",
            data=json.dumps({"name": "Roadmap", "area_id": area.id}),
            content_type="application/json",
        )
        assert res.status_code == 201
        data = json.loads(res.data)["data"]
        assert data["area_id"] == area.id

        project_id = data["id"]
        patch_res = client.patch(
            f"/api/v1/projects/{project_id}",
            data=json.dumps({"area_id": None}),
            content_type="application/json",
        )
        assert patch_res.status_code == 200
        assert json.loads(patch_res.data)["data"]["area_id"] is None
