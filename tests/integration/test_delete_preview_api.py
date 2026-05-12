"""Tests for V2-API-02: DELETE preview endpoint and cascade delete wiring."""

import pytest
from extensions import db
from models import Entity
from services.entity_service import create_entity
from services.link_service import create_link


# ─── GET /api/v2/entities/:id/delete-preview ─────────────────────────────────


class TestDeletePreviewAPI:
    def test_delete_preview_returns_orphan_analysis(self, client, app):
        """DELETE preview returns orphan analysis with safe_to_cascade and blocked."""
        with app.app_context():
            entity = create_entity(entity_type="note", title="Test Note", actor="user")
            entity_id = str(entity.id)

        resp = client.get(f"/api/v2/entities/{entity_id}/delete-preview")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "entity" in data
        assert "safe_to_cascade" in data
        assert "blocked" in data
        assert data["entity"]["id"] == entity_id

    def test_delete_preview_with_orphan(self, client, app):
        """Preview identifies orphaned linked entities."""
        with app.app_context():
            parent = create_entity(entity_type="note", title="Parent", actor="user")
            child = create_entity(entity_type="note", title="Child", actor="user")
            create_link(parent.id, child.id, link_type="related", actor="user")
            parent_id = str(parent.id)
            child_id = str(child.id)

        resp = client.get(f"/api/v2/entities/{parent_id}/delete-preview")
        assert resp.status_code == 200
        data = resp.get_json()
        assert child_id in data["safe_to_cascade"]

    def test_delete_preview_with_blocked(self, client, app):
        """Preview identifies blocked entities (have other connections)."""
        with app.app_context():
            a = create_entity(entity_type="note", title="A", actor="user")
            b = create_entity(entity_type="note", title="B", actor="user")
            c = create_entity(entity_type="note", title="C", actor="user")
            create_link(a.id, b.id, link_type="related", actor="user")
            create_link(b.id, c.id, link_type="related", actor="user")
            a_id = str(a.id)
            b_id = str(b.id)

        resp = client.get(f"/api/v2/entities/{a_id}/delete-preview")
        assert resp.status_code == 200
        data = resp.get_json()
        assert b_id in data["blocked"]

    def test_delete_preview_not_found(self, client):
        """Preview returns 404 for nonexistent entity."""
        resp = client.get("/api/v2/entities/00000000-0000-0000-0000-000000000000/delete-preview")
        assert resp.status_code == 404


# ─── DELETE /notes/:id with cascade ──────────────────────────────────────────


class TestDeleteNotesAPI:
    def test_delete_note_preview_mode(self, client, app):
        """DELETE /notes/:id without cascade returns preview."""
        with app.app_context():
            entity = create_entity(entity_type="note", title="To Delete", actor="user")
            entity_id = str(entity.id)

        resp = client.delete(f"/api/v1/notes/{entity_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "safe_to_cascade" in data
        assert "blocked" in data
        # Entity should still exist
        with app.app_context():
            assert db.session.get(Entity, entity_id) is not None

    def test_delete_note_with_cascade(self, client, app):
        """DELETE /notes/:id?cascade=true deletes entity."""
        with app.app_context():
            entity = create_entity(entity_type="note", title="To Delete", actor="user")
            entity_id = str(entity.id)

        resp = client.delete(f"/api/v1/notes/{entity_id}?cascade=true")
        assert resp.status_code == 200
        data = resp.get_json()
        assert entity_id in data["deleted"]
        with app.app_context():
            assert db.session.get(Entity, entity_id) is None

    def test_delete_note_not_found(self, client):
        resp = client.delete("/api/v1/notes/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


# ─── DELETE /tasks/:id with cascade ──────────────────────────────────────────


class TestDeleteTasksAPI:
    def test_delete_task_preview_mode(self, client, app):
        with app.app_context():
            entity = create_entity(entity_type="task", title="To Delete", actor="user")
            entity_id = str(entity.id)

        resp = client.delete(f"/api/v1/tasks/{entity_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "safe_to_cascade" in data
        with app.app_context():
            assert db.session.get(Entity, entity_id) is not None

    def test_delete_task_with_cascade(self, client, app):
        with app.app_context():
            entity = create_entity(entity_type="task", title="To Delete", actor="user")
            entity_id = str(entity.id)

        resp = client.delete(f"/api/v1/tasks/{entity_id}?cascade=true")
        assert resp.status_code == 200
        data = resp.get_json()
        assert entity_id in data["deleted"]
        with app.app_context():
            assert db.session.get(Entity, entity_id) is None


# ─── DELETE /projects/:id with cascade ───────────────────────────────────────


class TestDeleteProjectsAPI:
    def test_delete_project_preview_mode(self, client, app):
        with app.app_context():
            entity = create_entity(entity_type="project", title="To Delete", actor="user")
            entity_id = str(entity.id)

        resp = client.delete(f"/api/v1/projects/{entity_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "safe_to_cascade" in data
        with app.app_context():
            assert db.session.get(Entity, entity_id) is not None

    def test_delete_project_with_cascade(self, client, app):
        with app.app_context():
            entity = create_entity(entity_type="project", title="To Delete", actor="user")
            entity_id = str(entity.id)

        resp = client.delete(f"/api/v1/projects/{entity_id}?cascade=true")
        assert resp.status_code == 200
        data = resp.get_json()
        assert entity_id in data["deleted"]
        with app.app_context():
            assert db.session.get(Entity, entity_id) is None


# ─── DELETE /areas/:id with cascade ──────────────────────────────────────────


class TestDeleteAreasAPI:
    def test_delete_area_preview_mode(self, client, app):
        with app.app_context():
            entity = create_entity(entity_type="area", title="To Delete", actor="user")
            entity_id = str(entity.id)

        resp = client.delete(f"/api/v1/areas/{entity_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "safe_to_cascade" in data
        with app.app_context():
            assert db.session.get(Entity, entity_id) is not None

    def test_delete_area_with_cascade(self, client, app):
        with app.app_context():
            entity = create_entity(entity_type="area", title="To Delete", actor="user")
            entity_id = str(entity.id)

        resp = client.delete(f"/api/v1/areas/{entity_id}?cascade=true")
        assert resp.status_code == 200
        data = resp.get_json()
        assert entity_id in data["deleted"]
        with app.app_context():
            assert db.session.get(Entity, entity_id) is None
