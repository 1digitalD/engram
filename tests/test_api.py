import json
import os
from unittest.mock import MagicMock, patch

from extensions import db
from models import BucketType, Note, Task, TaskStatus, Summary, SummaryGranularity


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


def test_note_create_and_patch_project_ids_multi_and_clear(client, app):
    with app.app_context():
        pid_a = json.loads(
            client.post(
                "/api/v1/projects",
                data=json.dumps({"name": "Alpha"}),
                content_type="application/json",
            ).data
        )["data"]["id"]
        pid_b = json.loads(
            client.post(
                "/api/v1/projects",
                data=json.dumps({"name": "Beta"}),
                content_type="application/json",
            ).data
        )["data"]["id"]

        res = client.post(
            "/api/v1/notes",
            data=json.dumps(
                {"raw_text": "two projects", "classify": False, "project_ids": [pid_b, pid_a]}
            ),
            content_type="application/json",
        )
        assert res.status_code == 201
        body = json.loads(res.data)["data"]
        assert body["project_id"] == pid_b
        assert set(body["project_ids"]) == {pid_a, pid_b}
        assert len(body["projects"]) == 2

        note_id = body["id"]

        res = client.patch(
            f"/api/v1/notes/{note_id}",
            data=json.dumps({"project_ids": []}),
            content_type="application/json",
        )
        cleared = json.loads(res.data)["data"]
        assert cleared["project_ids"] == []
        assert cleared["project_id"] is None


def test_note_legacy_project_id_mapped_to_association(client, app):
    with app.app_context():
        pid = json.loads(
            client.post(
                "/api/v1/projects",
                data=json.dumps({"name": "Legacy"}),
                content_type="application/json",
            ).data
        )["data"]["id"]
        res = client.post(
            "/api/v1/notes",
            data=json.dumps({"raw_text": "legacy link", "classify": False, "project_id": pid}),
            content_type="application/json",
        )
        data = json.loads(res.data)["data"]
        assert data["project_id"] == pid
        assert data["project_ids"] == [pid]


def test_notes_list_serializes_project_ids_and_projects(client, app):
    with app.app_context():
        pid = json.loads(
            client.post(
                "/api/v1/projects",
                data=json.dumps({"name": "Listed"}),
                content_type="application/json",
            ).data
        )["data"]["id"]
        client.post(
            "/api/v1/notes",
            data=json.dumps(
                {"raw_text": "on list", "classify": False, "project_ids": [pid]}
            ),
            content_type="application/json",
        )
        res = client.get("/api/v1/notes")
        assert res.status_code == 200
        items = json.loads(res.data)["data"]
        note_row = next(n for n in items if n.get("raw_text") == "on list")
        assert note_row["project_id"] == pid
        assert note_row["project_ids"] == [pid]
        assert len(note_row["projects"]) == 1
        assert note_row["projects"][0]["id"] == pid


def test_notes_list_filter_by_project_ids_or_semantics(client, app):
    with app.app_context():
        pa = json.loads(
            client.post(
                "/api/v1/projects",
                data=json.dumps({"name": "FilterA"}),
                content_type="application/json",
            ).data
        )["data"]["id"]
        pb = json.loads(
            client.post(
                "/api/v1/projects",
                data=json.dumps({"name": "FilterB"}),
                content_type="application/json",
            ).data
        )["data"]["id"]
        client.post(
            "/api/v1/notes",
            data=json.dumps(
                {"raw_text": "only a", "classify": False, "project_ids": [pa]}
            ),
            content_type="application/json",
        )
        client.post(
            "/api/v1/notes",
            data=json.dumps(
                {"raw_text": "a and b", "classify": False, "project_ids": [pa, pb]}
            ),
            content_type="application/json",
        )
        res = client.get(f"/api/v1/notes?project_ids={pa},{pb}")
        texts = {n["raw_text"] for n in json.loads(res.data)["data"]}
        assert "only a" in texts
        assert "a and b" in texts
        res_one = client.get(f"/api/v1/notes?project_ids={pa}")
        texts_one = {n["raw_text"] for n in json.loads(res_one.data)["data"]}
        assert "only a" in texts_one
        assert "a and b" in texts_one


def test_note_post_project_ids_takes_precedence_over_project_id(client, app):
    with app.app_context():
        pa = json.loads(
            client.post(
                "/api/v1/projects",
                data=json.dumps({"name": "PrimaryProj"}),
                content_type="application/json",
            ).data
        )["data"]["id"]
        pb = json.loads(
            client.post(
                "/api/v1/projects",
                data=json.dumps({"name": "IgnoredProj"}),
                content_type="application/json",
            ).data
        )["data"]["id"]
        res = client.post(
            "/api/v1/notes",
            data=json.dumps(
                {
                    "raw_text": "prec",
                    "classify": False,
                    "project_ids": [pa],
                    "project_id": pb,
                }
            ),
            content_type="application/json",
        )
        body = json.loads(res.data)["data"]
        assert body["project_id"] == pa
        assert body["project_ids"] == [pa]


def test_note_patch_legacy_project_id(client, app):
    with app.app_context():
        pa = json.loads(
            client.post(
                "/api/v1/projects",
                data=json.dumps({"name": "PatchA"}),
                content_type="application/json",
            ).data
        )["data"]["id"]
        pb = json.loads(
            client.post(
                "/api/v1/projects",
                data=json.dumps({"name": "PatchB"}),
                content_type="application/json",
            ).data
        )["data"]["id"]
        nid = json.loads(
            client.post(
                "/api/v1/notes",
                data=json.dumps(
                    {
                        "raw_text": "patch legacy",
                        "classify": False,
                        "project_ids": [pa, pb],
                    }
                ),
                content_type="application/json",
            ).data
        )["data"]["id"]
        res = client.patch(
            f"/api/v1/notes/{nid}",
            data=json.dumps({"project_id": pb}),
            content_type="application/json",
        )
        data = json.loads(res.data)["data"]
        assert data["project_id"] == pb
        assert data["project_ids"] == [pb]


def test_resources_crud_and_type_filter(client, app):
    with app.app_context():
        aid = json.loads(
            client.post(
                "/api/v1/areas",
                data=json.dumps({"name": "Reading"}),
                content_type="application/json",
            ).data
        )["data"]["id"]

        tag_res = client.post(
            "/api/v1/notes",
            data=json.dumps(
                {"raw_text": "seed for tag", "classify": False, "tag_names": ["ref"]}
            ),
            content_type="application/json",
        )
        tag_id = json.loads(tag_res.data)["data"]["tag_ids"][0]

        res = client.post(
            "/api/v1/resources",
            data=json.dumps(
                {
                    "title": "Designing Data-Intensive Applications",
                    "resource_type": "BOOK",
                    "url": "https://example.com/ddia",
                    "author": "Kleppmann",
                    "area_id": aid,
                    "rating": 5,
                    "tag_ids": [tag_id],
                }
            ),
            content_type="application/json",
        )
        assert res.status_code == 201
        book = json.loads(res.data)["data"]
        rid = book["id"]
        assert book["resource_type"] == "BOOK"
        assert book["rating"] == 5
        assert book["area_id"] == aid
        assert tag_id in book["tag_ids"]

        client.post(
            "/api/v1/resources",
            data=json.dumps(
                {"title": "Some article", "resource_type": "ARTICLE"}
            ),
            content_type="application/json",
        )

        res = client.get("/api/v1/resources?type=BOOK")
        assert res.status_code == 200
        types = {r["resource_type"] for r in json.loads(res.data)["data"]}
        assert types == {"BOOK"}

        res = client.patch(
            f"/api/v1/resources/{rid}",
            data=json.dumps({"is_read": True, "rating": 4}),
            content_type="application/json",
        )
        body = json.loads(res.data)["data"]
        assert body["is_read"] is True
        assert body["rating"] == 4

        client.delete(f"/api/v1/resources/{rid}")
        res = client.get(f"/api/v1/resources/{rid}")
        assert res.status_code == 404

        area_detail = json.loads(client.get(f"/api/v1/areas/{aid}").data)["data"]
        assert area_detail["resource_count"] == 0


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


def test_summary_crud_and_list_filters(client, app):
    with app.app_context():
        note_res = client.post(
            "/api/v1/notes",
            data=json.dumps({"raw_text": "Note for summaries", "classify": False}),
            content_type="application/json",
        )
        note_id = json.loads(note_res.data)["data"]["id"]

        other_note = client.post(
            "/api/v1/notes",
            data=json.dumps({"raw_text": "Other note", "classify": False}),
            content_type="application/json",
        )
        other_id = json.loads(other_note.data)["data"]["id"]

        res = client.post(
            "/api/v1/summaries",
            data=json.dumps(
                {
                    "note_id": note_id,
                    "summary_text": "First pass",
                    "summary_type": "manual",
                    "granularity": "WEEKLY",
                    "date_from": "2026-05-01T00:00:00",
                    "date_to": "2026-05-07T23:59:59",
                    "key_themes": ["a", "b"],
                    "action_items": [{"title": "Follow up"}],
                }
            ),
            content_type="application/json",
        )
        assert res.status_code == 201
        row = json.loads(res.data)["data"]
        sid = row["id"]
        assert row["note_id"] == note_id
        assert row["summary_text"] == "First pass"
        assert row["summary_type"] == "manual"
        assert row["granularity"] == "WEEKLY"
        assert row["key_themes"] == ["a", "b"]
        assert row["action_items"] == [{"title": "Follow up"}]

        client.post(
            "/api/v1/summaries",
            data=json.dumps(
                {
                    "note_id": note_id,
                    "summary_text": "Daily rollup",
                    "granularity": "DAILY",
                }
            ),
            content_type="application/json",
        )

        res = client.get(f"/api/v1/summaries?note_id={note_id}")
        assert res.status_code == 200
        items = json.loads(res.data)["data"]
        assert len(items) == 2

        res = client.get("/api/v1/summaries?granularity=DAILY")
        assert res.status_code == 200
        daily_only = json.loads(res.data)["data"]
        assert len(daily_only) == 1
        assert daily_only[0]["granularity"] == "DAILY"

        res = client.get(f"/api/v1/summaries/{sid}")
        assert res.status_code == 200
        assert json.loads(res.data)["data"]["id"] == sid

        res = client.patch(
            f"/api/v1/summaries/{sid}",
            data=json.dumps(
                {
                    "summary_text": "Updated body",
                    "granularity": "MONTHLY",
                    "note_id": other_id,
                }
            ),
            content_type="application/json",
        )
        assert res.status_code == 200
        updated = json.loads(res.data)["data"]
        assert updated["summary_text"] == "Updated body"
        assert updated["granularity"] == "MONTHLY"
        assert updated["note_id"] == other_id

        res = client.delete(f"/api/v1/summaries/{sid}")
        assert res.status_code == 200
        assert db.session.get(Summary, sid) is None

        res = client.get(f"/api/v1/summaries/{sid}")
        assert res.status_code == 404


def test_summary_create_requires_note(client, app):
    with app.app_context():
        res = client.post(
            "/api/v1/summaries",
            data=json.dumps(
                {
                    "note_id": "00000000-0000-0000-0000-000000000000",
                    "summary_text": "orphan",
                }
            ),
            content_type="application/json",
        )
        assert res.status_code == 404


def test_summarize_notes_endpoint_persists_summary(client, app):
    with app.app_context():
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        n1 = client.post(
            "/api/v1/notes",
            data=json.dumps({"raw_text": "Alpha note", "classify": False}),
            content_type="application/json",
        )
        n2 = client.post(
            "/api/v1/notes",
            data=json.dumps({"raw_text": "Beta note", "classify": False}),
            content_type="application/json",
        )
        id1 = json.loads(n1.data)["data"]["id"]
        id2 = json.loads(n2.data)["data"]["id"]

        mock_usage = MagicMock(input_tokens=10, output_tokens=5)
        mock_text_block = MagicMock()
        mock_text_block.text = json.dumps(
            {
                "summary_text": "Both notes covered.",
                "key_themes": ["t1"],
                "action_items": ["Do the thing"],
            }
        )
        mock_msg = MagicMock()
        mock_msg.content = [mock_text_block]
        mock_msg.usage = mock_usage

        mock_client_instance = MagicMock()
        mock_client_instance.messages.create = MagicMock(return_value=mock_msg)

        with patch("anthropic.Anthropic", return_value=mock_client_instance):
            res = client.post(
                "/api/v1/summarize",
                data=json.dumps(
                    {
                        "note_ids": [id1, id2],
                        "granularity": "DAILY",
                        "entity_name": "Test Entity",
                    }
                ),
                content_type="application/json",
            )
        assert res.status_code == 201, res.data
        body = json.loads(res.data)["data"]
        assert body["summary_text"] == "Both notes covered."
        assert body["granularity"] == "DAILY"
        assert body["key_themes"] == ["t1"]
        assert body["action_items"] == ["Do the thing"]
        assert body["note_id"] == id1
        assert body["summary_type"] == "progressive_llm"
        assert body["meta"]["token_count"] == 15
        assert body["meta"]["model_used"]


def test_summarize_requires_entity_name(client, app):
    with app.app_context():
        note_res = client.post(
            "/api/v1/notes",
            data=json.dumps({"raw_text": "Lonely", "classify": False}),
            content_type="application/json",
        )
        nid = json.loads(note_res.data)["data"]["id"]
        res = client.post(
            "/api/v1/summarize",
            data=json.dumps({"note_ids": [nid], "granularity": "WEEKLY"}),
            content_type="application/json",
        )
        assert res.status_code == 400


def test_jobs_status_smoke(client, app):
    with app.app_context():
        res = client.get("/api/v1/jobs/status")
        assert res.status_code == 200
        body = json.loads(res.data)["data"]
        assert body["state"] in ("idle", "queued", "running", "completed", "error")


def test_jobs_summarize_creates_weekly_summary_for_area(client, app):
    with app.app_context():
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        area_res = client.post(
            "/api/v1/areas",
            data=json.dumps({"name": "JobTest Area"}),
            content_type="application/json",
        )
        assert area_res.status_code == 201
        aid = json.loads(area_res.data)["data"]["id"]

        note_res = client.post(
            "/api/v1/notes",
            data=json.dumps(
                {
                    "raw_text": "Note in area for job",
                    "classify": False,
                    "area_id": aid,
                }
            ),
            content_type="application/json",
        )
        assert note_res.status_code == 201

        mock_usage = MagicMock(input_tokens=10, output_tokens=5)
        mock_text_block = MagicMock()
        mock_text_block.text = json.dumps(
            {
                "summary_text": "Area rollup.",
                "key_themes": ["k"],
                "action_items": ["a"],
            }
        )
        mock_msg = MagicMock()
        mock_msg.content = [mock_text_block]
        mock_msg.usage = mock_usage
        mock_client_instance = MagicMock()
        mock_client_instance.messages.create = MagicMock(return_value=mock_msg)

        with patch("anthropic.Anthropic", return_value=mock_client_instance):
            res = client.post(
                "/api/v1/jobs/summarize",
                data=json.dumps({"granularity": "WEEKLY"}),
                content_type="application/json",
            )
        assert res.status_code == 200, res.data
        status = json.loads(res.data)["data"]["status"]
        assert status["state"] == "completed"
        assert status["summaries_created"] == 1

        summaries = Summary.query.filter_by(area_id=aid).all()
        assert len(summaries) == 1
        assert summaries[0].granularity == SummaryGranularity.WEEKLY
        assert summaries[0].summary_text == "Area rollup."
        assert summaries[0].summary_type == "scheduled"


def test_jobs_summarize_requires_granularity(client, app):
    with app.app_context():
        res = client.post(
            "/api/v1/jobs/summarize",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert res.status_code == 400
