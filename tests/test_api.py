import json

from extensions import db
from models import BucketType, Note, Task, TaskStatus


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


def test_get_daily_note_creates_with_template(client, app):
    with app.app_context():
        res = client.get("/api/v1/daily?date=2026-05-08")
        assert res.status_code == 200
        data = json.loads(res.data)["data"]

        assert data["bucket"] == "INBOX"
        assert data["raw_text"] == (
            "# Daily — 2026-05-08\n\n"
            "## Focus\n\n"
            "## Notes\n\n"
            "## Tasks\n"
        )
        assert Note.query.count() == 1


def test_get_daily_note_fetches_existing_inbox_daily_note(client, app):
    with app.app_context():
        existing = Note(
            raw_text=(
                "# Daily — 2026-05-08\n\n"
                "## Focus\n\n"
                "Keep going\n\n"
                "## Notes\n\n"
                "Already here\n\n"
                "## Tasks\n"
            ),
            bucket=BucketType.INBOX,
        )
        non_daily = Note(raw_text="Loose note", bucket=BucketType.INBOX)
        archived_daily = Note(raw_text="# Daily — 2026-05-08\n", bucket=BucketType.ARCHIVES)
        db.session.add_all([existing, non_daily, archived_daily])
        db.session.commit()

        res = client.get("/api/v1/daily?date=2026-05-08")
        assert res.status_code == 200
        data = json.loads(res.data)["data"]

        assert data["id"] == existing.id
        assert data["raw_text"] == existing.raw_text
        assert Note.query.count() == 3


def test_append_daily_note_adds_content_to_notes_section(client, app):
    with app.app_context():
        res = client.post(
            "/api/v1/daily/append",
            data=json.dumps({"date": "2026-05-08", "content": "Captured update."}),
            content_type="application/json",
        )
        assert res.status_code == 200
        data = json.loads(res.data)["data"]

        assert data["raw_text"] == (
            "# Daily — 2026-05-08\n\n"
            "## Focus\n\n"
            "## Notes\n\n"
            "Captured update.\n\n"
            "## Tasks\n"
        )

        res = client.post(
            "/api/v1/daily/append",
            data=json.dumps({"date": "2026-05-08", "content": "Second update."}),
            content_type="application/json",
        )
        data = json.loads(res.data)["data"]

        assert data["raw_text"] == (
            "# Daily — 2026-05-08\n\n"
            "## Focus\n\n"
            "## Notes\n\n"
            "Captured update.\n\n"
            "Second update.\n\n"
            "## Tasks\n"
        )


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


def test_inline_checkbox_tasks_on_note_create(client, app):
    with app.app_context():
        body = "Shopping list\n\n- [ ] buy milk\n- [x] eggs\n"
        res = client.post(
            "/api/v1/notes",
            data=json.dumps({"raw_text": body, "classify": False}),
            content_type="application/json",
        )
        assert res.status_code == 201
        note_id = json.loads(res.data)["data"]["id"]
        tasks = Task.query.filter_by(note_id=note_id).order_by(Task.title).all()
        assert len(tasks) == 2
        statuses = {t.title: t.status for t in tasks}
        assert statuses["buy milk"] == TaskStatus.PENDING
        assert statuses["eggs"] == TaskStatus.DONE
        assert all(t.inline_title_hash for t in tasks)


def test_inline_checkbox_update_toggles_and_removes(client, app):
    with app.app_context():
        res = client.post(
            "/api/v1/notes",
            data=json.dumps(
                {
                    "raw_text": "- [ ] one\n- [ ] two\n",
                    "classify": False,
                }
            ),
            content_type="application/json",
        )
        note_id = json.loads(res.data)["data"]["id"]
        t_one = Task.query.filter_by(note_id=note_id, title="one").one()
        t_two = Task.query.filter_by(note_id=note_id, title="two").one()

        client.patch(
            f"/api/v1/notes/{note_id}",
            data=json.dumps({"raw_text": "- [x] one\n- [ ] two\n"}),
            content_type="application/json",
        )
        db.session.expire_all()
        assert db.session.get(Task, t_one.id).status == TaskStatus.DONE
        assert db.session.get(Task, t_two.id).status == TaskStatus.PENDING

        client.patch(
            f"/api/v1/notes/{note_id}",
            data=json.dumps({"raw_text": "- [ ] two\n"}),
            content_type="application/json",
        )
        db.session.expire_all()
        assert db.session.get(Task, t_one.id).status == TaskStatus.CANCELLED
        assert db.session.get(Task, t_two.id).status == TaskStatus.PENDING


def test_manual_task_without_hash_not_cancelled_on_checkbox_removal(client, app):
    with app.app_context():
        res = client.post(
            "/api/v1/notes",
            data=json.dumps({"raw_text": "- [ ] inline only\n", "classify": False}),
            content_type="application/json",
        )
        note_id = json.loads(res.data)["data"]["id"]
        manual = Task(title="manual reminder", note_id=note_id, inline_title_hash=None)
        db.session.add(manual)
        db.session.commit()
        mid = manual.id

        client.patch(
            f"/api/v1/notes/{note_id}",
            data=json.dumps({"raw_text": "no checkboxes anymore\n"}),
            content_type="application/json",
        )
        db.session.expire_all()
        assert db.session.get(Task, mid).status == TaskStatus.PENDING
        inline_tasks = Task.query.filter(Task.note_id == note_id, Task.inline_title_hash.isnot(None)).all()
        assert len(inline_tasks) == 1
        assert inline_tasks[0].status == TaskStatus.CANCELLED


def test_inline_checkbox_daily_append(client, app):
    with app.app_context():
        res = client.post(
            "/api/v1/daily/append",
            data=json.dumps(
                {
                    "date": "2026-05-10",
                    "content": "- [ ] from daily capture",
                }
            ),
            content_type="application/json",
        )
        assert res.status_code == 200
        note_id = json.loads(res.data)["data"]["id"]
        t = Task.query.filter_by(note_id=note_id).one()
        assert t.title == "from daily capture"
        assert t.status == TaskStatus.PENDING
