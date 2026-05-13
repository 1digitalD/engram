"""Unit tests for V3-5.1: Delete flow with cascade preview.

Tests cover:
- Delete preview returns correct orphan analysis
- Cascade delete deletes selected orphans
- Blocked entities are not deleted
"""

import pytest
from extensions import db
from models import Entity
from services.entity_service import create_entity
from services.link_service import create_link


class TestDeletePreviewService:
    """Tests for delete preview service logic."""

    def test_preview_returns_entity_info(self, app):
        """Preview returns the entity being deleted."""
        with app.app_context():
            entity = create_entity(entity_type="note", title="Test Note", actor="user")
            entity_id = str(entity.id)

            from services.entity_service import delete_preview
            result = delete_preview(entity_id)

            assert result["entity"]["id"] == entity_id
            assert "safe_to_cascade" in result
            assert "blocked" in result

    def test_preview_identifies_orphan(self, app):
        """Preview identifies orphaned linked entities (only connected to deleted entity)."""
        with app.app_context():
            parent = create_entity(entity_type="note", title="Parent", actor="user")
            child = create_entity(entity_type="note", title="Child", actor="user")
            create_link(parent.id, child.id, link_type="related", actor="user")
            parent_id = str(parent.id)
            child_id = str(child.id)

            from services.entity_service import delete_preview
            result = delete_preview(parent_id)

            assert child_id in result["safe_to_cascade"]

    def test_preview_identifies_blocked(self, app):
        """Preview identifies blocked entities (have other connections)."""
        with app.app_context():
            a = create_entity(entity_type="note", title="A", actor="user")
            b = create_entity(entity_type="note", title="B", actor="user")
            c = create_entity(entity_type="note", title="C", actor="user")
            create_link(a.id, b.id, link_type="related", actor="user")
            create_link(b.id, c.id, link_type="related", actor="user")
            a_id = str(a.id)
            b_id = str(b.id)

            from services.entity_service import delete_preview
            result = delete_preview(a_id)

            assert b_id in result["blocked"]

    def test_preview_not_found(self, app):
        """Preview raises ValueError for nonexistent entity."""
        from services.entity_service import delete_preview
        with app.app_context():
            with pytest.raises(ValueError):
                delete_preview("00000000-0000-0000-0000-000000000000")


class TestCascadeDelete:
    """Tests for cascade delete functionality."""

    def test_delete_with_cascade_deletes_orphans(self, app):
        """Cascade delete removes the entity and selected orphans."""
        with app.app_context():
            parent = create_entity(entity_type="note", title="Parent", actor="user")
            child = create_entity(entity_type="note", title="Child", actor="user")
            create_link(parent.id, child.id, link_type="related", actor="user")
            parent_id = str(parent.id)
            child_id = str(child.id)

            from services.entity_service import delete_entity
            result = delete_entity(parent_id, cascade_orphans=True)

            assert parent_id in result["deleted"]
            assert child_id in result["deleted"]
            assert db.session.get(Entity, parent_id) is None
            assert db.session.get(Entity, child_id) is None

    def test_delete_without_cascade_returns_preview(self, app):
        """Delete without cascade returns preview without deleting."""
        with app.app_context():
            entity = create_entity(entity_type="note", title="To Delete", actor="user")
            entity_id = str(entity.id)

            from services.entity_service import delete_entity
            result = delete_entity(entity_id, cascade_orphans=False)

            assert "safe_to_cascade" in result
            assert "blocked" in result
            assert db.session.get(Entity, entity_id) is not None

    def test_delete_blocked_entities_not_affected(self, app):
        """Blocked entities are not deleted even with cascade."""
        with app.app_context():
            a = create_entity(entity_type="note", title="A", actor="user")
            b = create_entity(entity_type="note", title="B", actor="user")
            c = create_entity(entity_type="note", title="C", actor="user")
            create_link(a.id, b.id, link_type="related", actor="user")
            create_link(b.id, c.id, link_type="related", actor="user")
            a_id = str(a.id)
            b_id = str(b.id)
            c_id = str(c.id)

            from services.entity_service import delete_entity
            result = delete_entity(a_id, cascade_orphans=True)

            assert a_id in result["deleted"]
            assert b_id not in result["deleted"]
            assert db.session.get(Entity, b_id) is not None
            assert db.session.get(Entity, c_id) is not None
