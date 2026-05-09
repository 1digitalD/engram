import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from extensions import db
from models import (
    Area,
    BucketType,
    Link,
    LinkProposal,
    LinkProposalStatus,
    Note,
    Priority,
    Project,
    Summary,
    SummaryGranularity,
    Tag,
    Task,
    TaskStatus,
)


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


def test_link_proposals_generate_list_accept_and_idempotent_generate(client, app):
    with app.app_context():
        tag = Tag(name="proposal-api-shared")
        note_a = Note(
            raw_text="quarterly planning themes and roadmap draft for proposal-api-shared",
            bucket=BucketType.INBOX,
        )
        note_b = Note(
            raw_text="follow up on quarterly planning themes for proposal-api-shared next week",
            bucket=BucketType.INBOX,
        )
        note_a.tags.append(tag)
        note_b.tags.append(tag)
        db.session.add_all([tag, note_a, note_b])
        db.session.commit()

        gen = client.post(
            "/api/v1/proposals/generate",
            data=json.dumps({"note_ids": [note_a.id, note_b.id], "min_confidence": 0.35}),
            content_type="application/json",
        )
        assert gen.status_code == 200, gen.data
        created = json.loads(gen.data)["data"]["created"]
        assert created >= 1

        lst = client.get("/api/v1/proposals")
        assert lst.status_code == 200
        items = json.loads(lst.data)["data"]
        assert len(items) >= 1
        pending = [x for x in items if x["status"] == "pending"]
        assert pending
        pid = pending[0]["id"]

        acc = client.post(f"/api/v1/proposals/{pid}/accept")
        assert acc.status_code == 200, acc.data
        body = json.loads(acc.data)["data"]
        assert body["proposal"]["status"] == "accepted"
        assert body["link"] is not None
        assert body["link"]["source"] == "llm"

        link_rows = Link.query.count()
        assert link_rows == 1

        gen2 = client.post(
            "/api/v1/proposals/generate",
            data=json.dumps({"note_ids": [note_a.id, note_b.id], "min_confidence": 0.35}),
            content_type="application/json",
        )
        assert gen2.status_code == 200
        assert json.loads(gen2.data)["data"]["created"] == 0


def test_link_proposals_dismiss(client, app):
    with app.app_context():
        tag = Tag(name="dismiss-tag")
        a = Note(raw_text="alpha one two three four five six", bucket=BucketType.INBOX)
        b = Note(raw_text="beta one two three four five seven", bucket=BucketType.INBOX)
        a.tags.append(tag)
        b.tags.append(tag)
        db.session.add_all([tag, a, b])
        db.session.commit()

        client.post(
            "/api/v1/proposals/generate",
            data=json.dumps({"note_ids": [a.id, b.id], "min_confidence": 0.32}),
            content_type="application/json",
        )
        items = json.loads(client.get("/api/v1/proposals").data)["data"]
        pid = items[0]["id"]

        res = client.post(f"/api/v1/proposals/{pid}/dismiss")
        assert res.status_code == 200
        assert json.loads(res.data)["data"]["status"] == "dismissed"

        prop = db.session.get(LinkProposal, pid)
        assert prop.status == LinkProposalStatus.DISMISSED

        gen = client.post(
            "/api/v1/proposals/generate",
            data=json.dumps({"note_ids": [a.id, b.id], "min_confidence": 0.32}),
            content_type="application/json",
        )
        assert json.loads(gen.data)["data"]["created"] == 0


def test_link_proposals_list_status_filter_and_invalid(client, app):
    with app.app_context():
        res = client.get("/api/v1/proposals?status=not-a-real-status")
        assert res.status_code == 400

        res = client.get("/api/v1/proposals?status=all")
        assert res.status_code == 200
        assert json.loads(res.data)["data"] == []


def test_link_proposals_list_filter_by_note_id(client, app):
    with app.app_context():
        tag = Tag(name="note-filter-prop")
        a = Note(raw_text="note filter alpha proposal shared tag x9", bucket=BucketType.INBOX)
        b = Note(raw_text="note filter beta proposal shared tag x9", bucket=BucketType.INBOX)
        c = Note(raw_text="note filter gamma unrelated lone", bucket=BucketType.INBOX)
        a.tags.append(tag)
        b.tags.append(tag)
        db.session.add_all([tag, a, b, c])
        db.session.commit()

        client.post(
            "/api/v1/proposals/generate",
            data=json.dumps({"note_ids": [a.id, b.id, c.id], "min_confidence": 0.28}),
            content_type="application/json",
        )
        all_pending = json.loads(client.get("/api/v1/proposals?status=pending").data)["data"]
        assert len(all_pending) >= 1

        for_a = json.loads(
            client.get(f"/api/v1/proposals?status=pending&note_id={a.id}").data
        )["data"]
        assert for_a
        assert all(
            x["src_id"] == a.id or x["dst_id"] == a.id for x in for_a
        )
        for_c = json.loads(
            client.get(f"/api/v1/proposals?status=pending&note_id={c.id}").data
        )["data"]
        assert all(
            x["src_id"] == c.id or x["dst_id"] == c.id for x in for_c
        )


def test_link_proposals_accept_not_found(client, app):
    with app.app_context():
        res = client.post("/api/v1/proposals/00000000-0000-0000-0000-000000000000/accept")
        assert res.status_code == 404


def test_weekly_digest_empty(client, app):
    res = client.get("/api/v1/review/weekly-digest")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["days"] == 7
    assert data["notes_captured"] == 0
    assert data["tasks_created"] == 0
    assert data["projects_completed"] == 0
    assert data["connections_made"] == 0
    assert "date_from" in data and "date_to" in data


def test_weekly_digest_counts_rolling_window(client, app):
    with app.app_context():
        now = datetime.utcnow()
        recent = now - timedelta(days=2)
        stale = now - timedelta(days=30)

        n_in = Note(raw_text="# in window", bucket=BucketType.INBOX)
        n_in.created_at = recent
        n_out = Note(raw_text="# too old", bucket=BucketType.INBOX)
        n_out.created_at = stale
        db.session.add_all([n_in, n_out])

        a = Note(raw_text="link a", bucket=BucketType.INBOX)
        b = Note(raw_text="link b", bucket=BucketType.INBOX)
        c = Note(raw_text="link c", bucket=BucketType.INBOX)
        d = Note(raw_text="link d", bucket=BucketType.INBOX)
        for x in (a, b, c, d):
            x.created_at = recent
        db.session.add_all([a, b, c, d])
        db.session.flush()

        link_in = Link(src_id=a.id, dst_id=b.id)
        link_in.created_at = recent
        link_out = Link(src_id=c.id, dst_id=d.id)
        link_out.created_at = stale
        db.session.add_all([link_in, link_out])

        t_in = Task(title="recent task", priority=Priority.MEDIUM)
        t_in.created_at = recent
        t_out = Task(title="old task", priority=Priority.MEDIUM)
        t_out.created_at = stale
        db.session.add_all([t_in, t_out])

        archived_recent = Project(name="Done recently", is_archived=True, priority=Priority.MEDIUM)
        archived_recent.created_at = stale
        archived_recent.modified_at = recent

        archived_old = Project(name="Done ages ago", is_archived=True, priority=Priority.MEDIUM)
        archived_old.created_at = stale
        archived_old.modified_at = stale

        active = Project(name="Still active", is_archived=False, priority=Priority.MEDIUM)
        active.created_at = recent
        active.modified_at = recent
        db.session.add_all([archived_recent, archived_old, active])

        db.session.commit()

    res = client.get("/api/v1/review/weekly-digest")
    assert res.status_code == 200
    data = json.loads(res.data)
    # n_in, a, b, c, d = 5 notes in window (tagged created_at recent)
    assert data["notes_captured"] == 5
    assert data["tasks_created"] == 1
    assert data["connections_made"] == 1
    assert data["projects_completed"] == 1


def test_api_v1_metrics_health_empty(client, app):
    res = client.get("/api/v1/metrics/health")
    assert res.status_code == 200
    data = json.loads(res.data)
    expected_keys = (
        "total_notes",
        "orphan_rate",
        "avg_links_per_note",
        "inbox_count",
        "archive_ratio",
        "tag_coverage",
        "active_projects",
        "stale_projects",
        "weekly_capture_rate",
        "weekly_capture_counts",
        "link_proposals_pending",
    )
    for k in expected_keys:
        assert k in data
    assert data["total_notes"] == 0
    assert data["orphan_rate"] == 0.0
    assert data["avg_links_per_note"] == 0.0
    assert data["inbox_count"] == 0
    assert data["archive_ratio"] == 0.0
    assert data["tag_coverage"] == 0.0
    assert data["active_projects"] == 0
    assert data["stale_projects"] == 0
    assert data["weekly_capture_rate"] == 0
    assert data["weekly_capture_counts"] == [0, 0, 0, 0]
    assert data["link_proposals_pending"] == 0


def test_api_v1_metrics_health_creates_system_weekly_snapshot(client, app):
    res = client.get("/api/v1/metrics/health")
    assert res.status_code == 200
    with app.app_context():
        row = Summary.query.filter_by(entity_type="system").first()
        assert row is not None
        assert row.granularity == SummaryGranularity.WEEKLY
        assert isinstance(row.key_themes, dict)
        assert abs(row.key_themes.get("orphan_rate", -1) - 0.0) < 1e-9


def test_api_v1_metrics_health_history_returns_twelve_weeks(client, app):
    client.get("/api/v1/metrics/health")
    res = client.get("/api/v1/metrics/health/history?weeks=12")
    assert res.status_code == 200
    body = json.loads(res.data)
    assert len(body["data"]) == 12
    assert any(w.get("orphan_rate") is not None for w in body["data"])


def test_api_v1_summaries_hides_system_health_by_default(client, app):
    client.get("/api/v1/metrics/health")
    res = client.get("/api/v1/summaries")
    assert res.status_code == 200
    body = json.loads(res.data)
    assert all(s.get("entity_type") != "system" for s in body["data"])


def test_api_v1_summaries_lists_system_when_filtered(client, app):
    client.get("/api/v1/metrics/health")
    res = client.get("/api/v1/summaries?entity_type=system")
    assert res.status_code == 200
    body = json.loads(res.data)
    assert len(body["data"]) >= 1
    assert body["data"][0]["entity_type"] == "system"


def test_api_v1_metrics_health_from_db(client, app):
    with app.app_context():
        now = datetime.utcnow()
        old = now - timedelta(days=40)
        recent = now - timedelta(days=2)

        stale_proj = Project(name="Stale proj", is_archived=False, priority=Priority.MEDIUM)
        stale_proj.modified_at = old
        fresh_proj = Project(name="Fresh proj", is_archived=False, priority=Priority.MEDIUM)
        archived_proj = Project(name="Archived proj", is_archived=True, priority=Priority.MEDIUM)
        db.session.add_all([stale_proj, fresh_proj, archived_proj])

        inbox1 = Note(raw_text="inbox one", bucket=BucketType.INBOX)
        inbox2 = Note(raw_text="inbox two", bucket=BucketType.INBOX)
        orphan = Note(raw_text="orphan body", bucket=BucketType.PROJECTS)
        linked_a = Note(raw_text="link a", bucket=BucketType.PROJECTS)
        linked_b = Note(raw_text="link b", bucket=BucketType.PROJECTS)
        archived_n = Note(raw_text="gone", bucket=BucketType.AREAS, is_archived=True)
        recent_cap = Note(raw_text="this week", bucket=BucketType.INBOX)
        ancient = Note(raw_text="yesteryear", bucket=BucketType.INBOX)

        db.session.add_all(
            [inbox1, inbox2, orphan, linked_a, linked_b, archived_n, recent_cap, ancient]
        )
        db.session.flush()

        tag = Tag(name="metric-tag")
        db.session.add(tag)
        orphan.tags.append(tag)

        db.session.add(Link(src_id=linked_a.id, dst_id=linked_b.id))

        prop = LinkProposal(
            src_id=inbox1.id,
            dst_id=inbox2.id,
            confidence=0.85,
            reason="metrics",
            status=LinkProposalStatus.PENDING,
        )
        db.session.add(prop)

        for n in (inbox1, inbox2, orphan, linked_a, linked_b, archived_n, ancient):
            n.created_at = old
        recent_cap.created_at = recent

        db.session.commit()

    res = client.get("/api/v1/metrics/health")
    assert res.status_code == 200
    data = json.loads(res.data)

    assert data["total_notes"] == 8
    assert data["inbox_count"] == 4
    assert data["orphan_rate"] == 1 / 8
    assert data["avg_links_per_note"] == 2 / 8
    assert data["archive_ratio"] == 1 / 8
    assert data["tag_coverage"] == 1 / 8
    assert data["active_projects"] == 2
    assert data["stale_projects"] == 1
    assert data["weekly_capture_rate"] == 1
    assert data["weekly_capture_counts"] == [0, 0, 0, 1]
    assert data["link_proposals_pending"] == 1


def test_patch_project_archive_with_area_requires_rollup_confirmation(client, app):
    with app.app_context():
        area = Area(name="Work")
        db.session.add(area)
        db.session.flush()
        proj = Project(name="Ship", area_id=area.id, priority=Priority.MEDIUM)
        db.session.add(proj)
        db.session.commit()
        pid = proj.id

    res = client.patch(
        f"/api/v1/projects/{pid}",
        data=json.dumps({"is_archived": True}),
        content_type="application/json",
    )
    assert res.status_code == 409
    body = json.loads(res.data)
    assert body["code"] == "rollup_confirmation_required"
    assert body["area_id"]

    with app.app_context():
        proj = db.session.get(Project, pid)
        assert proj.is_archived is False


def test_patch_project_archive_with_area_rollup_confirmed(client, app):
    with app.app_context():
        area = Area(name="Home")
        db.session.add(area)
        db.session.flush()
        proj = Project(name="Empty", area_id=area.id, priority=Priority.MEDIUM)
        db.session.add(proj)
        db.session.commit()
        pid = proj.id

    res = client.patch(
        f"/api/v1/projects/{pid}",
        data=json.dumps({"is_archived": True, "rollup_confirmed": True}),
        content_type="application/json",
    )
    assert res.status_code == 200
    out = json.loads(res.data)
    assert out["data"]["is_archived"] is True
    assert out["rollup"]["note_id"]

    with app.app_context():
        proj = db.session.get(Project, pid)
        assert proj.is_archived is True


def test_patch_project_archive_without_area(client, app):
    with app.app_context():
        proj = Project(name="Solo", area_id=None, priority=Priority.MEDIUM)
        db.session.add(proj)
        db.session.commit()
        pid = proj.id

    res = client.patch(
        f"/api/v1/projects/{pid}",
        data=json.dumps({"is_archived": True}),
        content_type="application/json",
    )
    assert res.status_code == 200
    assert json.loads(res.data)["data"]["is_archived"] is True

    with app.app_context():
        proj = db.session.get(Project, pid)
        assert proj.is_archived is True


def test_api_v1_links_list(client, app):
    with app.app_context():
        a = Note(raw_text="a", bucket=BucketType.INBOX)
        b = Note(raw_text="b", bucket=BucketType.INBOX)
        db.session.add_all([a, b])
        db.session.flush()
        db.session.add(
            Link(
                src_id=a.id,
                dst_id=b.id,
                link_type="related",
                weight=0.82,
            )
        )
        db.session.commit()
        aid, bid = a.id, b.id

    res = client.get("/api/v1/links")
    assert res.status_code == 200
    payload = json.loads(res.data)
    assert len(payload["data"]) == 1
    row = payload["data"][0]
    assert row["link_type"] == "related"
    assert row["weight"] == 0.82
    assert row["src_id"] == aid
    assert row["dst_id"] == bid
