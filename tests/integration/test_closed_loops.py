"""Integration tests for V3-5.5: Test coverage for closed loops.

Tests critical end-to-end paths to prevent regressions:
1. Full note create -> classify -> tag visible in AI sidebar
2. Task status update via PATCH API (drag-and-drop backend path)
3. AI selection -> Extract Task -> task appears in tasks list
4. Delete preview -> cascade delete end-to-end API flow
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from extensions import db
from models import Entity, EntityTag, Tag, EntityEvent


# ─── 1. Note create -> classify -> tag visible in AI sidebar ──────────────────

class TestNoteCreateClassifyTagLoop:
    """Full loop: create note, run classify, verify tags visible."""

    @patch("services.extractor.extract")
    def test_create_note_classify_tags_visible_in_response(self, mock_extract, client, app):
        """After classification, tags appear in the note's entity_tags."""
        from services.extractor import ExtractionResult
        from services.ai_pipeline import run_classify

        mock_extract.return_value = ExtractionResult(
            summary="Meeting notes about planning",
            para_bucket="PROJECTS",
            confidence=0.95,
            suggested_project="Planning Project",
            reasoning="Clear project mention",
            tags=["Planning", "Meeting"],
        )

        resp = client.post("/api/v1/notes", json={
            "raw_text": "We discussed the planning timeline for Q2",
            "classify": True,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        note_id = data["data"]["id"]

        with app.app_context():
            run_classify({"entity_id": note_id})

            entity_tags = EntityTag.query.filter_by(entity_id=note_id).all()
            assert len(entity_tags) == 2

            tag_names = sorted(et.tag.name for et in entity_tags)
            assert tag_names == ["meeting", "planning"]

    @patch("services.extractor.extract")
    def test_create_note_classify_tags_reused_not_duplicated(self, mock_extract, client, app):
        """Existing tags are reused, not duplicated."""
        from services.extractor import ExtractionResult
        from services.ai_pipeline import run_classify

        with app.app_context():
            existing_tag = Tag(name="planning")
            db.session.add(existing_tag)
            db.session.commit()
            existing_tag_id = existing_tag.id

        mock_extract.return_value = ExtractionResult(
            summary="Planning notes",
            para_bucket="INBOX",
            confidence=0.90,
            reasoning="Found planning tag",
            tags=["Planning"],
        )

        resp = client.post("/api/v1/notes", json={
            "raw_text": "Planning session notes",
            "classify": True,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        note_id = data["data"]["id"]

        with app.app_context():
            run_classify({"entity_id": note_id})

            entity_tags = EntityTag.query.filter_by(entity_id=note_id).all()
            assert len(entity_tags) == 1
            assert entity_tags[0].tag_id == existing_tag_id

            tags = Tag.query.filter_by(name="planning").all()
            assert len(tags) == 1

    @patch("services.extractor.extract")
    def test_get_note_after_classify_shows_tag_ids(self, mock_extract, client, app):
        """GET /notes/:id returns tag_ids populated from EntityTag records."""
        from services.extractor import ExtractionResult
        from services.ai_pipeline import run_classify

        mock_extract.return_value = ExtractionResult(
            summary="Test note",
            para_bucket="INBOX",
            confidence=0.90,
            reasoning="Test",
            tags=["Urgent", "Follow-up"],
        )

        resp = client.post("/api/v1/notes", json={
            "raw_text": "Need urgent follow-up",
            "classify": True,
        })
        assert resp.status_code == 201
        note_id = resp.get_json()["data"]["id"]

        with app.app_context():
            run_classify({"entity_id": note_id})

        resp = client.get(f"/api/v1/notes/{note_id}")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert "tag_ids" in data
        assert len(data["tag_ids"]) == 2


# ─── 2. Task drag-and-drop updates status via updateTask (backend API) ────────

class TestTaskStatusUpdateLoop:
    """Backend path for task drag-and-drop: PATCH /tasks/:id with status."""

    def test_update_task_status_pending_to_in_progress(self, client, app):
        """Drag from Pending to In Progress column updates status."""
        with app.app_context():
            from services.entity_service import create_entity
            task = create_entity(entity_type="task", title="Test task", actor="user")
            task_id = str(task.id)
            assert task.status == "pending"

        resp = client.patch(f"/api/v1/tasks/{task_id}", json={
            "status": "in_progress",
        })
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["status"] == "in_progress"

        with app.app_context():
            updated = db.session.get(Entity, task_id)
            assert updated.status == "in_progress"

    def test_update_task_status_in_progress_to_done(self, client, app):
        """Drag from In Progress to Done column updates status."""
        with app.app_context():
            from services.entity_service import create_entity, transition_status
            task = create_entity(entity_type="task", title="Test task", actor="user")
            task_id = str(task.id)
            transition_status(task_id, "in_progress", actor="user")
            db.session.commit()

        resp = client.patch(f"/api/v1/tasks/{task_id}", json={
            "status": "done",
        })
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["status"] == "done"

    def test_update_task_status_writes_event(self, client, app):
        """Status change via API writes a status_changed event."""
        with app.app_context():
            from services.entity_service import create_entity
            task = create_entity(entity_type="task", title="Test task", actor="user")
            task_id = str(task.id)

        client.patch(f"/api/v1/tasks/{task_id}", json={
            "status": "in_progress",
        })

        with app.app_context():
            events = EntityEvent.query.filter_by(
                entity_id=task_id, event_type="status_changed"
            ).all()
            assert len(events) == 1
            assert events[0].old_value["status"] == "pending"
            assert events[0].new_value["status"] == "in_progress"

    def test_list_tasks_reflects_status_change(self, client, app):
        """After status update, GET /tasks shows the new status."""
        with app.app_context():
            from services.entity_service import create_entity
            task = create_entity(entity_type="task", title="Test task", actor="user")
            task_id = str(task.id)

        client.patch(f"/api/v1/tasks/{task_id}", json={
            "status": "done",
        })

        resp = client.get("/api/v1/tasks?status=done")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert any(t["id"] == task_id for t in data)


# ─── 3. AI selection -> Extract Task -> task appears in Tasks view ────────────

class TestExtractTaskLoop:
    """Full loop: AI selection -> Extract Task -> task visible in tasks list."""

    @patch("services.extractor.extract")
    def test_extract_task_via_api_then_list_shows_task(self, mock_extract, client, app):
        """Extract task via AI API, then verify it appears in GET /tasks."""
        from services.extractor import ExtractionResult, ExtractedTask

        mock_extract.return_value = ExtractionResult(
            summary="Action items",
            para_bucket="PROJECTS",
            confidence=0.90,
            reasoning="Task extraction",
            tasks=[ExtractedTask(
                title="Review the design mockups",
                priority="HIGH",
                due_date="2026-05-20",
            )],
        )

        with app.app_context():
            initial_count = Entity.query.filter_by(type="task").count()

        resp = client.post("/api/v2/ai/propose-from-selection", json={
            "action": "extract_task",
            "selected_text": "Remember to review the design mockups by Friday",
        })
        assert resp.status_code == 201
        result = resp.get_json()
        assert "tasks" in result["result"]
        assert len(result["result"]["tasks"]) >= 1

        with app.app_context():
            task_count = Entity.query.filter_by(type="task").count()
            assert task_count > initial_count

        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        tasks = resp.get_json()["data"]
        assert any("review" in t.get("title", "").lower() for t in tasks)

    @patch("services.extractor.extract")
    def test_extract_task_creates_task_with_correct_properties(self, mock_extract, client, app):
        """Extracted task has priority and title set correctly."""
        from services.extractor import ExtractionResult, ExtractedTask

        mock_extract.return_value = ExtractionResult(
            summary="Notes",
            para_bucket="INBOX",
            confidence=0.85,
            reasoning="Found task",
            tasks=[ExtractedTask(
                title="Fix the login bug",
                priority="URGENT",
            )],
        )

        resp = client.post("/api/v2/ai/propose-from-selection", json={
            "action": "extract_task",
            "selected_text": "URGENT: Fix the login bug ASAP",
        })
        assert resp.status_code == 201

        task_data = resp.get_json()["result"]["tasks"][0]
        assert "fix" in task_data["title"].lower()
        assert task_data.get("priority") == "URGENT"


# ─── 4. Delete preview modal -> cascade delete end-to-end ─────────────────────

class TestDeletePreviewCascadeLoop:
    """Full loop: delete preview -> cascade delete via API."""

    def test_preview_then_cascade_delete_note(self, client, app):
        """Get delete preview, then cascade delete the note."""
        from services.entity_service import create_entity
        from services.link_service import create_link

        with app.app_context():
            parent = create_entity(entity_type="note", title="Parent note", actor="user")
            child = create_entity(entity_type="note", title="Child note", actor="user")
            create_link(parent.id, child.id, link_type="related", actor="user")
            parent_id = str(parent.id)
            child_id = str(child.id)

        resp = client.get(f"/api/v2/entities/{parent_id}/delete-preview")
        assert resp.status_code == 200
        data = resp.get_json()
        assert child_id in data["safe_to_cascade"]

        resp = client.delete(f"/api/v1/notes/{parent_id}?cascade=true")
        assert resp.status_code == 200
        data = resp.get_json()
        assert parent_id in data["deleted"]
        assert child_id in data["deleted"]

        with app.app_context():
            assert db.session.get(Entity, parent_id) is None
            assert db.session.get(Entity, child_id) is None

    def test_preview_then_delete_without_cascade_keeps_entity(self, client, app):
        """Preview then delete without cascade keeps the entity."""
        from services.entity_service import create_entity

        with app.app_context():
            entity = create_entity(entity_type="note", title="Test note", actor="user")
            entity_id = str(entity.id)

        resp = client.get(f"/api/v2/entities/{entity_id}/delete-preview")
        assert resp.status_code == 200

        resp = client.delete(f"/api/v1/notes/{entity_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "safe_to_cascade" in data

        with app.app_context():
            assert db.session.get(Entity, entity_id) is not None
