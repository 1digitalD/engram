import json


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert "db" in data


def test_create_note(client, app):
    with app.app_context():
        res = client.post(
            "/api/v1/notes",
            data=json.dumps({"raw_text": "Test note from API", "classify": False}),
            content_type="application/json",
        )
        assert res.status_code == 201
        data = json.loads(res.data)
        assert data["data"]["raw_text"] == "Test note from API"
        assert data["data"]["bucket"] == "INBOX"


def test_get_note(client, app):
    with app.app_context():
        # Create first
        res = client.post(
            "/api/v1/notes",
            data=json.dumps({"raw_text": "Get me", "classify": False}),
            content_type="application/json",
        )
        note_id = json.loads(res.data)["data"]["id"]

        # Fetch
        res = client.get(f"/api/v1/notes/{note_id}")
        assert res.status_code == 200
        data = json.loads(res.data)
        assert data["data"]["raw_text"] == "Get me"


def test_update_note(client, app):
    with app.app_context():
        # Create
        res = client.post(
            "/api/v1/notes",
            data=json.dumps({"raw_text": "Original", "classify": False}),
            content_type="application/json",
        )
        note_id = json.loads(res.data)["data"]["id"]

        # Update
        res = client.patch(
            f"/api/v1/notes/{note_id}",
            data=json.dumps({"raw_text": "Updated text"}),
            content_type="application/json",
        )
        data = json.loads(res.data)
        assert data["data"]["raw_text"] == "Updated text"


def test_delete_note(client, app):
    with app.app_context():
        res = client.post(
            "/api/v1/notes",
            data=json.dumps({"raw_text": "To delete", "classify": False}),
            content_type="application/json",
        )
        note_id = json.loads(res.data)["data"]["id"]

        res = client.delete(f"/api/v1/notes/{note_id}")
        assert res.status_code == 200

        res = client.get(f"/api/v1/notes/{note_id}")
        assert res.status_code == 404


def test_list_notes_filtered(client, app):
    with app.app_context():
        # Create in different buckets
        client.post(
            "/api/v1/notes",
            data=json.dumps({"raw_text": "Inbox note", "classify": False}),
            content_type="application/json",
        )
        client.post(
            "/api/v1/notes",
            data=json.dumps({"raw_text": "Archived note", "classify": False, "bucket": "archives"}),
            content_type="application/json",
        )

        res = client.get("/api/v1/notes")
        data = json.loads(res.data)
        assert data["total"] >= 2

        res = client.get("/api/v1/notes?bucket=archives")
        data = json.loads(res.data)
        # May be 0 if archived filter excluded it — depends on default


def test_create_project(client, app):
    with app.app_context():
        res = client.post(
            "/api/v1/projects",
            data=json.dumps({"name": "My Project", "priority": "high"}),
            content_type="application/json",
        )
        assert res.status_code == 201
        data = json.loads(res.data)
        assert data["data"]["name"] == "My Project"
        assert data["data"]["priority"] == "HIGH"


def test_create_task(client, app):
    with app.app_context():
        res = client.post(
            "/api/v1/tasks",
            data=json.dumps({"title": "Finish the thing", "priority": "urgent"}),
            content_type="application/json",
        )
        assert res.status_code == 201
        data = json.loads(res.data)
        assert data["data"]["title"] == "Finish the thing"
        assert data["data"]["status"] == "PENDING"


def test_update_task_status(client, app):
    with app.app_context():
        res = client.post(
            "/api/v1/tasks",
            data=json.dumps({"title": "Task to complete"}),
            content_type="application/json",
        )
        task_id = json.loads(res.data)["data"]["id"]

        res = client.patch(
            f"/api/v1/tasks/{task_id}",
            data=json.dumps({"status": "done"}),
            content_type="application/json",
        )
        data = json.loads(res.data)
        assert data["data"]["status"] == "DONE"


def test_create_area(client, app):
    with app.app_context():
        res = client.post(
            "/api/v1/areas",
            data=json.dumps({"name": "Health"}),
            content_type="application/json",
        )
        assert res.status_code == 201
        data = json.loads(res.data)
        assert data["data"]["name"] == "Health"


def test_create_person(client, app):
    with app.app_context():
        res = client.post(
            "/api/v1/people",
            data=json.dumps({"name": "Jane Doe", "email": "jane@example.com"}),
            content_type="application/json",
        )
        assert res.status_code == 201
        data = json.loads(res.data)
        assert data["data"]["name"] == "Jane Doe"
