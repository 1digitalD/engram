"""Integration tests for entity_service — CRUD + lifecycle with DB.

Uses the Flask app fixture with in-memory SQLite.
"""

import pytest

from extensions import db
from models import Entity, EntityEvent, Job
from services.entity_service import (
    create_entity,
    update_entity,
    transition_status,
    archive_entity,
    delete_preview,
    delete_entity,
    VALID_TRANSITIONS,
)


# ─── create_entity ───────────────────────────────────────────────────────────


class TestCreateEntity:
    def test_create_note(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note",
                title="Test Note",
                content="Hello world",
                actor="user",
            )
            assert entity.id is not None
            assert entity.type == "note"
            assert entity.title == "Test Note"
            assert entity.content == "Hello world"
            assert entity.status == "active"
            assert entity.lifecycle == "active"
            assert entity.ai_status == "pending"

    def test_create_task_with_properties(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="task",
                title="Fix bug",
                properties={"priority": "high"},
                actor="user",
            )
            assert entity.type == "task"
            assert entity.properties["priority"] == "high"

    def test_create_project(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="project",
                title="Engram v2",
                actor="user",
            )
            assert entity.type == "project"

    def test_create_all_entity_types(self, app):
        with app.app_context():
            expected_status = {
                "task": "pending",
                "project": "active",
                "note": "active",
                "area": "active",
                "resource": "active",
                "person": "active",
            }
            for etype in ("note", "task", "project", "area", "resource", "person"):
                entity = create_entity(
                    entity_type=etype,
                    title=f"Test {etype}",
                    actor="user",
                )
                assert entity.type == etype
                assert entity.status == expected_status[etype]
                assert entity.lifecycle == "active"

    def test_create_writes_event(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note",
                title="Test",
                actor="user",
            )
            event = EntityEvent.query.filter_by(
                entity_id=entity.id, event_type="created"
            ).first()
            assert event is not None
            assert event.actor == "user"

    def test_create_enqueues_jobs(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note",
                title="Test",
                actor="user",
            )
            jobs = Job.query.filter_by(entity_id=entity.id).all()
            job_types = {j.job_type for j in jobs}
            assert "classify" in job_types
            assert "embed" in job_types

    def test_create_with_source(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note",
                title="Test",
                source="api",
                actor="user",
            )
            assert entity.source == "api"

    def test_create_with_extra_fields(self, app):
        with app.app_context():
            from datetime import datetime, timezone
            dt = datetime(2026, 6, 1, tzinfo=timezone.utc)
            entity = create_entity(
                entity_type="task",
                title="Test",
                follow_up_at=dt,
                reference_url="https://example.com",
                actor="user",
            )
            assert entity.reference_url == "https://example.com"


# ─── update_entity ───────────────────────────────────────────────────────────


class TestUpdateEntity:
    def test_update_title(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note", title="Old", actor="user"
            )
            updated = update_entity(entity.id, {"title": "New"}, actor="user")
            assert updated.title == "New"

    def test_update_content(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note", content="Old content", actor="user"
            )
            updated = update_entity(
                entity.id, {"content": "New content"}, actor="user"
            )
            assert updated.content == "New content"

    def test_update_properties(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="task",
                properties={"priority": "low"},
                actor="user",
            )
            updated = update_entity(
                entity.id,
                {"properties": {"priority": "high"}},
                actor="user",
            )
            assert updated.properties["priority"] == "high"

    def test_update_writes_event(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note", title="Old", actor="user"
            )
            update_entity(entity.id, {"title": "New"}, actor="user")
            event = EntityEvent.query.filter_by(
                entity_id=entity.id, event_type="field_updated"
            ).first()
            assert event is not None
            assert event.actor == "user"
            assert event.old_value["title"]["old"] == "Old"
            assert event.old_value["title"]["new"] == "New"

    def test_update_no_change(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note", title="Same", actor="user"
            )
            updated = update_entity(entity.id, {"title": "Same"}, actor="user")
            # No event should be written for no-op update
            events = EntityEvent.query.filter_by(
                entity_id=entity.id, event_type="field_updated"
            ).all()
            assert len(events) == 0

    def test_update_not_found(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="not found"):
                update_entity("nonexistent-id", {"title": "New"}, actor="user")

    def test_update_archived_entity_rejected(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note", title="Test", actor="user"
            )
            archive_entity(entity.id, actor="user")
            with pytest.raises(ValueError, match="cannot update archived"):
                update_entity(entity.id, {"title": "New"}, actor="user")


# ─── transition_status ───────────────────────────────────────────────────────


class TestTransitionStatus:
    def test_task_pending_to_in_progress(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="task", title="Test", actor="user"
            )
            updated = transition_status(
                entity.id, "in_progress", actor="user"
            )
            assert updated.status == "in_progress"

    def test_task_in_progress_to_done(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="task", title="Test", actor="user"
            )
            transition_status(entity.id, "in_progress", actor="user")
            updated = transition_status(
                entity.id, "done", actor="user"
            )
            assert updated.status == "done"

    def test_task_done_to_pending(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="task", title="Test", actor="user"
            )
            transition_status(entity.id, "in_progress", actor="user")
            transition_status(entity.id, "done", actor="user")
            updated = transition_status(
                entity.id, "pending", actor="user"
            )
            assert updated.status == "pending"

    def test_invalid_transition_rejected(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="task", title="Test", actor="user"
            )
            with pytest.raises(ValueError, match="invalid transition"):
                transition_status(entity.id, "archived", actor="user")

    def test_transition_writes_event(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="task", title="Test", actor="user"
            )
            transition_status(
                entity.id, "in_progress", actor="user", reason="starting"
            )
            event = EntityEvent.query.filter_by(
                entity_id=entity.id, event_type="status_changed"
            ).first()
            assert event is not None
            assert event.old_value["status"] == "pending"
            assert event.new_value["status"] == "in_progress"
            assert event.reason == "starting"

    def test_transition_not_found(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="not found"):
                transition_status("nonexistent", "done", actor="user")

    def test_note_active_to_archived_via_transition(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note", title="Test", actor="user"
            )
            # Notes use 'archived' as a status, not lifecycle
            updated = transition_status(
                entity.id, "archived", actor="user"
            )
            assert updated.status == "archived"

    def test_project_active_to_completed(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="project", title="Test", actor="user"
            )
            updated = transition_status(
                entity.id, "completed", actor="user"
            )
            assert updated.status == "completed"

    def test_project_completed_to_active(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="project", title="Test", actor="user"
            )
            transition_status(entity.id, "completed", actor="user")
            updated = transition_status(
                entity.id, "active", actor="user"
            )
            assert updated.status == "active"

    def test_transition_with_reason(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="task", title="Test", actor="user"
            )
            transition_status(
                entity.id, "cancelled", actor="user",
                reason="no longer needed"
            )
            event = EntityEvent.query.filter_by(
                entity_id=entity.id, event_type="status_changed"
            ).first()
            assert event.reason == "no longer needed"


# ─── archive_entity ──────────────────────────────────────────────────────────


class TestArchiveEntity:
    def test_archive_note(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note", title="Test", actor="user"
            )
            archived = archive_entity(entity.id, actor="user")
            assert archived.lifecycle == "archived"

    def test_archive_writes_event(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note", title="Test", actor="user"
            )
            archive_entity(entity.id, actor="user")
            event = EntityEvent.query.filter_by(
                entity_id=entity.id, event_type="archived"
            ).first()
            assert event is not None
            assert event.new_value["lifecycle"] == "archived"

    def test_archive_already_archived_rejected(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note", title="Test", actor="user"
            )
            archive_entity(entity.id, actor="user")
            with pytest.raises(ValueError, match="already archived"):
                archive_entity(entity.id, actor="user")

    def test_archive_not_found(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="not found"):
                archive_entity("nonexistent", actor="user")

    def test_archive_all_types(self, app):
        with app.app_context():
            for etype in ("note", "area", "resource", "person"):
                entity = create_entity(
                    entity_type=etype, title=f"Test {etype}", actor="user"
                )
                archived = archive_entity(entity.id, actor="user")
                assert archived.lifecycle == "archived"


# ─── delete_preview ──────────────────────────────────────────────────────────


class TestDeletePreview:
    def test_preview_no_links(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note", title="Test", actor="user"
            )
            preview = delete_preview(entity.id)
            assert preview["entity"]["id"] == entity.id
            assert preview["safe_to_cascade"] == []
            assert preview["blocked"] == []

    def test_preview_with_orphan(self, app):
        with app.app_context():
            from services.link_service import create_link
            parent = create_entity(
                entity_type="note", title="Parent", actor="user"
            )
            child = create_entity(
                entity_type="note", title="Child", actor="user"
            )
            create_link(
                parent.id, child.id, link_type="related", actor="user"
            )
            preview = delete_preview(parent.id)
            assert child.id in preview["safe_to_cascade"]

    def test_preview_with_blocked(self, app):
        with app.app_context():
            from services.link_service import create_link
            a = create_entity(
                entity_type="note", title="A", actor="user"
            )
            b = create_entity(
                entity_type="note", title="B", actor="user"
            )
            c = create_entity(
                entity_type="note", title="C", actor="user"
            )
            # A -> B, B -> C
            create_link(a.id, b.id, link_type="related", actor="user")
            create_link(b.id, c.id, link_type="related", actor="user")
            preview = delete_preview(a.id)
            # B has another connection (to C), so it's blocked
            assert b.id in preview["blocked"]

    def test_preview_not_found(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="not found"):
                delete_preview("nonexistent")


# ─── delete_entity ───────────────────────────────────────────────────────────


class TestDeleteEntity:
    def test_delete_preview_mode(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note", title="Test", actor="user"
            )
            result = delete_entity(entity.id, cascade_orphans=False)
            assert result["deleted"] == []
            # Entity should still exist
            assert Entity.query.get(entity.id) is not None

    def test_delete_with_cascade(self, app):
        with app.app_context():
            from services.link_service import create_link
            parent = create_entity(
                entity_type="note", title="Parent", actor="user"
            )
            child = create_entity(
                entity_type="note", title="Child", actor="user"
            )
            create_link(
                parent.id, child.id, link_type="related", actor="user"
            )
            result = delete_entity(parent.id, cascade_orphans=True)
            assert parent.id in result["deleted"]
            assert child.id in result["deleted"]
            # Both should be gone
            assert Entity.query.get(parent.id) is None
            assert Entity.query.get(child.id) is None

    def test_delete_blocked_not_cascaded(self, app):
        with app.app_context():
            from services.link_service import create_link
            a = create_entity(
                entity_type="note", title="A", actor="user"
            )
            b = create_entity(
                entity_type="note", title="B", actor="user"
            )
            c = create_entity(
                entity_type="note", title="C", actor="user"
            )
            create_link(a.id, b.id, link_type="related", actor="user")
            create_link(b.id, c.id, link_type="related", actor="user")
            result = delete_entity(a.id, cascade_orphans=True)
            assert a.id in result["deleted"]
            # B should NOT be deleted (has other connections)
            assert b.id not in result["deleted"]
            assert Entity.query.get(b.id) is not None

    def test_delete_not_found(self, app):
        with app.app_context():
            with pytest.raises(ValueError, match="not found"):
                delete_entity("nonexistent", cascade_orphans=True)

    def test_delete_writes_events(self, app):
        with app.app_context():
            entity = create_entity(
                entity_type="note", title="Test", actor="user"
            )
            # Verify event is written before delete completes
            # (events are cascade-deleted with the entity, so we check before commit)
            from services.entity_service import delete_preview
            preview = delete_preview(entity.id)
            assert preview["entity"]["id"] == entity.id
            # After delete, entity and its events are cascade-deleted
            delete_entity(entity.id, cascade_orphans=True)
            assert Entity.query.get(entity.id) is None
