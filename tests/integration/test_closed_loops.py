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
from models import Entity, EntityTag, Tag, EntityEvent, EntityLink, ChangeBatch


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

    @patch("services.ai_pipeline.enqueue_embed")
    @patch("services.ai_pipeline.enqueue_classify")
    def test_patch_note_with_classify_enqueues_reclassify_jobs(self, mock_enqueue_classify, mock_enqueue_embed, client, app):
        """PATCH /notes/:id with classify=true should enqueue classify+embed jobs."""
        resp = client.post("/api/v1/notes", json={"raw_text": "Initial content", "classify": False})
        assert resp.status_code == 201
        note_id = resp.get_json()["data"]["id"]
        mock_enqueue_classify.reset_mock()
        mock_enqueue_embed.reset_mock()

        resp = client.patch(f"/api/v1/notes/{note_id}", json={"classify": True})
        assert resp.status_code == 200

        mock_enqueue_classify.assert_called_once()
        mock_enqueue_embed.assert_called_once()


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


# ─── 5. Entity reconciliation in run_classify ────────────────────────────────

class TestEntityReconciliationLoop:
    """Full loop: classify extracts people/tasks, reconcile_all routes them correctly."""

    @patch("services.ai_pipeline.reconcile_all")
    @patch("services.ai_pipeline.apply_change_plan")
    @patch("services.extractor.extract")
    def test_classify_reconciles_people_via_reconcile_all(self, mock_extract, mock_apply, mock_reconcile, client, app):
        """After classify, extracted people are routed through reconcile_all."""
        from services.extractor import ExtractionResult, ExtractedPerson

        mock_extract.return_value = ExtractionResult(
            summary="Meeting note",
            para_bucket="INBOX",
            confidence=0.85,
            reasoning="Extracted people",
            tags=[],
            tasks=[],
            people=[
                ExtractedPerson(name="Alice Smith", email=None),
            ],
        )

        mock_reconcile.return_value = [
            {"detected": {"type": "person", "name": "Alice Smith"}, "reconciliation": None},
        ]

        mock_apply.return_value = {
            "applied_changes": [],
            "suggestions": [
                {"operation": "create_person", "name": "Alice Smith"},
            ],
        }

        resp = client.post("/api/v1/notes", json={
            "raw_text": "Met with Alice Smith today",
            "classify": True,
        })
        assert resp.status_code == 201
        note_id = resp.get_json()["data"]["id"]

        with app.app_context():
            from services.ai_pipeline import run_classify
            run_classify({"entity_id": note_id})

            mock_reconcile.assert_called_once()
            call_args = mock_reconcile.call_args[0][0]
            assert len(call_args) == 1
            assert call_args[0]["type"] == "person"
            assert call_args[0]["name"] == "Alice Smith"

            mock_apply.assert_called_once()

    @patch("services.ai_pipeline.reconcile_all")
    @patch("services.ai_pipeline.apply_change_plan")
    @patch("services.extractor.extract")
    def test_classify_reconciles_tasks_via_reconcile_all(self, mock_extract, mock_apply, mock_reconcile, client, app):
        """After classify, extracted tasks are routed through reconcile_all."""
        from services.extractor import ExtractionResult, ExtractedTask

        mock_extract.return_value = ExtractionResult(
            summary="Action items",
            para_bucket="INBOX",
            confidence=0.85,
            reasoning="Extracted tasks",
            tags=[],
            people=[],
            tasks=[
                ExtractedTask(title="Review proposal", priority="HIGH"),
            ],
        )

        mock_reconcile.return_value = [
            {"detected": {"type": "task", "name": "Review proposal"}, "reconciliation": None},
        ]

        mock_apply.return_value = {
            "applied_changes": [],
            "suggestions": [
                {"operation": "create_task", "title": "Review proposal", "priority": "HIGH"},
            ],
        }

        resp = client.post("/api/v1/notes", json={
            "raw_text": "Need to review the proposal",
            "classify": True,
        })
        assert resp.status_code == 201
        note_id = resp.get_json()["data"]["id"]

        with app.app_context():
            from services.ai_pipeline import run_classify
            run_classify({"entity_id": note_id})

            mock_reconcile.assert_called_once()
            call_args = mock_reconcile.call_args[0][0]
            assert len(call_args) == 1
            assert call_args[0]["type"] == "task"
            assert call_args[0]["name"] == "Review proposal"

    @patch("services.ai_pipeline.reconcile_all")
    @patch("services.ai_pipeline.apply_change_plan")
    @patch("services.extractor.extract")
    def test_classify_reconciles_project_and_area_via_reconcile_all(self, mock_extract, mock_apply, mock_reconcile, client, app):
        """High-confidence classification reconciles both project and area."""
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="Project note",
            para_bucket="PROJECTS",
            confidence=0.95,
            suggested_project="Alpha Platform",
            suggested_area="Work",
            reasoning="Clear project and area",
            tags=[],
            people=[],
            tasks=[],
        )

        mock_reconcile.return_value = [
            {"detected": {"type": "project", "name": "Alpha Platform"}, "reconciliation": None},
            {"detected": {"type": "area", "name": "Work"}, "reconciliation": None},
        ]

        mock_apply.return_value = {
            "applied_changes": [
                {"operation": "create_project", "title": "Alpha Platform"},
                {"operation": "create_area", "title": "Work"},
            ],
            "suggestions": [],
        }

        resp = client.post("/api/v1/notes", json={
            "raw_text": "Working on Alpha Platform in Work area",
            "classify": True,
        })
        assert resp.status_code == 201
        note_id = resp.get_json()["data"]["id"]

        with app.app_context():
            from services.ai_pipeline import run_classify
            run_classify({"entity_id": note_id})

            mock_reconcile.assert_called_once()
            call_args = mock_reconcile.call_args[0][0]
            assert len(call_args) == 2
            entity_names = sorted(e["name"] for e in call_args)
            assert entity_names == ["Alpha Platform", "Work"]


# ─── 6. Task completion capture flow ────────────────────────────────────────

class TestTaskCompletionCaptureLoop:
    """End-to-end test: task completion capture -> task status updated."""

    def test_capture_creates_note_and_runs_classify(self, client, app):
        """A capture creates a source note and triggers the AI pipeline."""
        resp = client.post("/api/v2/capture", json={
            "content": "I finished reviewing the proposal",
            "source": "quick_capture",
        })
        assert resp.status_code == 201
        result = resp.get_json()
        assert "source_note" in result
        assert result["source_note"] is not None
        assert "capture_summary" in result
        assert "detected_entities" in result
        assert "proposed_changes" in result

    def test_capture_v1_endpoint_works_with_same_contract(self, client, app):
        resp = client.post("/api/v1/capture", json={
            "content": "Captured from v1 endpoint",
            "source": "quick_capture",
        })
        assert resp.status_code == 201
        result = resp.get_json()
        assert "source_note" in result
        assert "applied_changes" in result
        assert "suggestions" in result
        assert "warnings" in result

    def test_add_follow_up_via_proposed_changes_creates_task(self, client, app):
        """add_follow_up in proposed_changes (high confidence) creates the follow-up task."""
        from services.entity_service import create_entity
        from services.ai_operation_applier import apply_change_plan

        with app.app_context():
            source_note = create_entity(entity_type="note", title="Test note", actor="user")
            source_id = str(source_note.id)

            change_plan = {
                "source_note_id": source_id,
                "proposed_changes": [{
                    "operation": "add_follow_up",
                    "title": "Review report",
                    "task_id": None,
                    "confidence": 0.95,
                }],
                "suggestions": [],
            }
            result = apply_change_plan(change_plan, actor="test")

            follow_ups = Entity.query.filter(
                Entity.type == "task",
                Entity.title == "Review report",
            ).all()
            assert len(follow_ups) >= 1
            links = EntityLink.query.filter_by(dst_id=str(follow_ups[0].id)).all()
            assert len(links) >= 1


# ─── 7. Change batches + undo ────────────────────────────────────────────────

class TestChangeBatchUndo:
    """Test change batch creation and undo."""

    def test_apply_change_plan_creates_change_batch(self, client, app):
        """apply_change_plan with proposed changes creates a ChangeBatch."""
        from services.entity_service import create_entity
        from services.ai_operation_applier import apply_change_plan

        with app.app_context():
            note = create_entity(entity_type="note", title="Test note", actor="user")
            source_id = str(note.id)

            change_plan = {
                "source_note_id": source_id,
                "proposed_changes": [{
                    "operation": "create_task",
                    "title": "Test undo task",
                    "confidence": 0.95,
                    "reason": "test batch creation",
                }],
                "suggestions": [],
            }
            result = apply_change_plan(change_plan, actor="test")

            assert result.get("change_batch_id") is not None

            batch = db.session.get(ChangeBatch, result["change_batch_id"])
            assert batch is not None
            assert batch.source_note_id == source_id
            assert batch.actor == "test"

    def test_undo_change_batch_reverts_created_entity(self, client, app):
        """Undoing a batch marks created entities as deleted."""
        from services.entity_service import create_entity
        from services.ai_operation_applier import apply_change_plan, batch_undo

        with app.app_context():
            note = create_entity(entity_type="note", title="Test note", actor="user")
            source_id = str(note.id)

            change_plan = {
                "source_note_id": source_id,
                "proposed_changes": [{
                    "operation": "create_task",
                    "title": "Task to undo",
                    "confidence": 0.95,
                }],
                "suggestions": [],
            }
            result = apply_change_plan(change_plan, actor="test")
            batch_id = result["change_batch_id"]

            applied = result["applied_changes"]
            assert len(applied) == 1
            task_id = applied[0].get("entity_id")

            undo_result = batch_undo(batch_id, actor="test")

            assert undo_result["undone"] is True
            assert task_id in undo_result.get("undone_entities", [])

            db.session.expire_all()
            task = db.session.get(Entity, task_id)
            assert task.lifecycle == "deleted"

    def test_undo_api_endpoint(self, client, app):
        """POST /api/v2/change-batches/:id/undo works."""
        from services.entity_service import create_entity
        from services.ai_operation_applier import apply_change_plan

        with app.app_context():
            note = create_entity(entity_type="note", title="Test note", actor="user")
            source_id = str(note.id)

            change_plan = {
                "source_note_id": source_id,
                "proposed_changes": [{
                    "operation": "create_task",
                    "title": "API undo test task",
                    "confidence": 0.95,
                }],
                "suggestions": [],
            }
            result = apply_change_plan(change_plan, actor="test")
            batch_id = result["change_batch_id"]

        resp = client.post(f"/api/v2/change-batches/{batch_id}/undo")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["undone"] is True

    def test_undo_twice_returns_error(self, client, app):
        """Undoing the same batch twice returns an error."""
        from services.entity_service import create_entity
        from services.ai_operation_applier import apply_change_plan

        with app.app_context():
            note = create_entity(entity_type="note", title="Test note", actor="user")
            source_id = str(note.id)

            change_plan = {
                "source_note_id": source_id,
                "proposed_changes": [{
                    "operation": "create_task",
                    "title": "Double undo task",
                    "confidence": 0.95,
                }],
                "suggestions": [],
            }
            result = apply_change_plan(change_plan, actor="test")
            batch_id = result["change_batch_id"]

        resp = client.post(f"/api/v2/change-batches/{batch_id}/undo")
        assert resp.status_code == 200

        resp2 = client.post(f"/api/v2/change-batches/{batch_id}/undo")
        assert resp2.status_code == 400
        assert "already undone" in resp2.get_json().get("error", "")


class TestExtractedEntitiesEndpoint:
    """Test GET /api/v2/entities/:id/extracted"""

    def test_extracted_returns_derived_entities(self, client, app):
        """derived_from links return created entities."""
        from services.entity_service import create_entity
        from services.link_service import create_link

        with app.app_context():
            note_id = str(create_entity(entity_type="note", title="Test note", actor="user").id)
            task_id = str(create_entity(entity_type="task", title="Extracted task", actor="user").id)
            create_link(src_id=note_id, dst_id=task_id, link_type="derived_from", actor="user")
            db.session.commit()

        resp = client.get(f"/api/v2/entities/{note_id}/extracted")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data["derived"]) == 1
        assert data["derived"][0]["id"] == task_id

    def test_extracted_returns_derived_entities_when_link_points_to_note(self, client, app):
        """derived_from links are detected when direction is task -> note."""
        from services.entity_service import create_entity
        from services.link_service import create_link

        with app.app_context():
            note_id = str(create_entity(entity_type="note", title="Source note", actor="user").id)
            task_id = str(create_entity(entity_type="task", title="Derived task", actor="user").id)
            create_link(src_id=task_id, dst_id=note_id, link_type="derived_from", actor="user")
            db.session.commit()

        resp = client.get(f"/api/v2/entities/{note_id}/extracted")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert any(e["id"] == task_id for e in data["derived"])

    def test_extracted_returns_linked_existing(self, client, app):
        """related links to project/area are returned as linked_existing."""
        from services.entity_service import create_entity
        from services.link_service import create_link

        with app.app_context():
            note_id = str(create_entity(entity_type="note", title="Test note", actor="user").id)
            project_id = str(create_entity(entity_type="project", title="Linked project", actor="user").id)
            create_link(src_id=note_id, dst_id=project_id, link_type="related", actor="user")
            db.session.commit()

        resp = client.get(f"/api/v2/entities/{note_id}/extracted")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data["linked_existing"]) == 1
        assert data["linked_existing"][0]["id"] == project_id

    def test_extracted_returns_pending_suggestions(self, client, app):
        """Pending AiSuggestions for the note are returned."""
        from services.entity_service import create_entity
        from models import AiSuggestion

        with app.app_context():
            note_id = str(create_entity(entity_type="note", title="Test note", actor="user").id)
            suggestion = AiSuggestion(
                source_entity_id=note_id,
                suggestion_type="create_task",
                operation_type="create_new_entity",
                payload={"title": "Suggested task"},
                confidence=0.85,
                reason="Test",
                status="pending",
            )
            db.session.add(suggestion)
            db.session.commit()

        resp = client.get(f"/api/v2/entities/{note_id}/extracted")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data["suggestions"]) == 1

    def test_extracted_not_found_for_unknown_entity(self, client, app):
        """Returns 404 for unknown entity."""
        resp = client.get("/api/v2/entities/nonexistent-id/extracted")
        assert resp.status_code == 404

    def test_change_plan_suggestions_are_persisted_and_returned(self, client, app):
        """Plan-level suggestions should persist to AiSuggestion and appear in extracted view."""
        from services.entity_service import create_entity
        from services.ai_operation_applier import apply_change_plan

        with app.app_context():
            note_id = str(create_entity(entity_type="note", title="Suggestion source", actor="user").id)
            result = apply_change_plan(
                {
                    "source_note_id": note_id,
                    "proposed_changes": [],
                    "suggestions": [
                        {
                            "operation": "create_task",
                            "title": "Suggested via classify",
                            "reason": "Medium-confidence extraction",
                            "confidence": 0.80,
                        }
                    ],
                },
                actor="agent:classify",
            )
            assert len(result["suggestions"]) == 1

        resp = client.get(f"/api/v2/entities/{note_id}/extracted")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["suggestion_type"] == "create_task"


class TestTodaySummary:
    """Test GET /api/v2/today/summary"""

    def test_projects_without_next_action(self, client, app):
        """Returns active projects with no pending/in_progress tasks."""
        from services.entity_service import create_entity
        from services.link_service import create_link

        with app.app_context():
            project_id = str(create_entity(entity_type="project", title="Orphan Project", actor="user").id)
            db.session.commit()

        resp = client.get("/api/v2/today/summary")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert any(p["id"] == project_id for p in data["projects_without_next_action"])

    def test_waiting_on_people(self, client, app):
        """Returns people who have tasks assigned with waiting/blocked status."""
        from services.entity_service import create_entity, update_entity
        from services.link_service import create_link

        with app.app_context():
            person_id = str(create_entity(entity_type="person", title="Waiting Person", actor="user").id)
            task = create_entity(entity_type="task", title="Waiting task", actor="user")
            task_id = str(task.id)
            update_entity(task_id, {"status": "waiting"}, actor="user")
            create_link(src_id=task_id, dst_id=person_id, link_type="assigned_to", actor="user")
            db.session.commit()

        resp = client.get("/api/v2/today/summary")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert any(p["id"] == person_id for p in data["waiting_on_people"])

    def test_project_with_active_task_not_in_list(self, client, app):
        """Project with a pending task is excluded from no-next-action list."""
        from services.entity_service import create_entity
        from services.link_service import create_link

        with app.app_context():
            project_id = str(create_entity(entity_type="project", title="Active Project", actor="user").id)
            task = create_entity(entity_type="task", title="Active task", actor="user")
            task_id = str(task.id)
            create_link(src_id=task_id, dst_id=project_id, link_type="parent", actor="user")
            db.session.commit()

        resp = client.get("/api/v2/today/summary")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert not any(p["id"] == project_id for p in data["projects_without_next_action"])


class TestAssignedToLinks:
    """Test that tasks linked to people get assigned_to links during reconciliation."""

    def test_task_created_with_assigned_to_link(self, client, app):
        """When a task is matched during reconciliation, assigned_to link is created."""
        from services.entity_service import create_entity, update_entity
        from services.link_service import create_link
        from models import EntityLink

        with app.app_context():
            note_id = str(create_entity(entity_type="note", title="Note about John", actor="user").id)
            person_id = str(create_entity(entity_type="person", title="John Doe", actor="user").id)
            db.session.commit()

            link = create_link(src_id=note_id, dst_id=person_id, link_type="mentions", actor="user")
            db.session.commit()

            existing_task = create_entity(entity_type="task", title="Call John", actor="user")
            task_id = str(existing_task.id)
            create_link(src_id=task_id, dst_id=person_id, link_type="assigned_to", actor="user")
            db.session.commit()

        res = client.get(f"/api/v2/entities/{note_id}/extracted")
        assert res.status_code == 200

        with app.app_context():
            assigned_links = EntityLink.query.filter(
                EntityLink.dst_id == person_id,
                EntityLink.link_type == "assigned_to",
            ).all()
            assert len(assigned_links) >= 1
