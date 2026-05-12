"""Unit tests for api/batch.py — v2 Entity model."""
import pytest
from extensions import db
from models import Entity, EntityTag, Tag


class TestBatchAPI:
    def test_batch_empty_ops(self, client):
        resp = client.post("/api/v1/batch", json={"operations": []})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_batch_too_many_ops(self, client):
        ops = [{"op": "get_note", "note_id": "x"}] * 51
        resp = client.post("/api/v1/batch", json={"operations": ops})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_batch_get_note_not_found(self, client):
        resp = client.post("/api/v1/batch", json={
            "operations": [{"op": "get_note", "note_id": "nonexistent"}]
        })
        assert resp.status_code == 207
        data = resp.get_json()
        assert "error" in data["results"][0]

    def test_batch_create_note(self, client):
        resp = client.post("/api/v1/batch", json={
            "operations": [{"op": "create_note", "raw_text": "Test batch note"}]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data["results"][0]
        assert "note" in data["results"][0]["data"]

    def test_batch_create_note_no_content(self, client):
        resp = client.post("/api/v1/batch", json={
            "operations": [{"op": "create_note"}]
        })
        assert resp.status_code == 207
        data = resp.get_json()
        assert "error" in data["results"][0]

    def test_batch_unknown_op(self, client):
        resp = client.post("/api/v1/batch", json={
            "operations": [{"op": "unknown_operation"}]
        })
        assert resp.status_code == 207
        data = resp.get_json()
        assert "error" in data["results"][0]

    def test_batch_multiple_ops(self, client):
        resp = client.post("/api/v1/batch", json={
            "operations": [
                {"op": "create_note", "raw_text": "First note"},
                {"op": "create_note", "raw_text": "Second note"},
            ]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["results"]) == 2

    def test_batch_get_note_after_create(self, client, app):
        with app.app_context():
            entity = Entity(type="note", title="Batch test note", content="Batch test note")
            db.session.add(entity)
            db.session.commit()
            entity_id = entity.id

        resp = client.post("/api/v1/batch", json={
            "operations": [{"op": "get_note", "note_id": entity_id}]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data["results"][0]
        assert data["results"][0]["data"]["note"]["raw_text"] == "Batch test note"

    def test_batch_update_note(self, client, app):
        with app.app_context():
            entity = Entity(type="note", title="Original", content="Original text")
            db.session.add(entity)
            db.session.commit()
            entity_id = entity.id

        resp = client.post("/api/v1/batch", json={
            "operations": [
                {"op": "update_note", "note_id": entity_id, "raw_text": "Updated text"}
            ]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data["results"][0]

    def test_batch_update_note_not_found(self, client):
        resp = client.post("/api/v1/batch", json={
            "operations": [
                {"op": "update_note", "note_id": "nonexistent", "raw_text": "test"}
            ]
        })
        assert resp.status_code == 207
        data = resp.get_json()
        assert "error" in data["results"][0]

    # ─── Task operations ─────────────────────────────────────────────────────

    def test_batch_create_task(self, client):
        resp = client.post("/api/v1/batch", json={
            "operations": [{"op": "create_task", "title": "Test task"}]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data["results"][0]
        assert "task" in data["results"][0]["data"]

    def test_batch_create_task_no_title(self, client):
        resp = client.post("/api/v1/batch", json={
            "operations": [{"op": "create_task"}]
        })
        assert resp.status_code == 207
        data = resp.get_json()
        assert "error" in data["results"][0]

    def test_batch_update_task(self, client, app):
        with app.app_context():
            entity = Entity(type="task", title="Test task", status="pending")
            db.session.add(entity)
            db.session.commit()
            entity_id = entity.id

        resp = client.post("/api/v1/batch", json={
            "operations": [
                {"op": "update_task", "task_id": entity_id, "title": "Updated task"}
            ]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data["results"][0]

    def test_batch_update_task_status_transition(self, client, app):
        with app.app_context():
            entity = Entity(type="task", title="Status test", status="pending")
            db.session.add(entity)
            db.session.commit()
            entity_id = entity.id

        resp = client.post("/api/v1/batch", json={
            "operations": [
                {"op": "update_task", "task_id": entity_id, "status": "in_progress"}
            ]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        task_data = data["results"][0]["data"]["task"]
        assert task_data["status"] == "in_progress"

    def test_batch_update_task_invalid_transition(self, client, app):
        with app.app_context():
            entity = Entity(type="task", title="Invalid transition", status="done")
            db.session.add(entity)
            db.session.commit()
            entity_id = entity.id

        resp = client.post("/api/v1/batch", json={
            "operations": [
                {"op": "update_task", "task_id": entity_id, "status": "in_progress"}
            ]
        })
        assert resp.status_code == 207
        data = resp.get_json()
        assert "error" in data["results"][0]

    def test_batch_update_task_not_found(self, client):
        resp = client.post("/api/v1/batch", json={
            "operations": [
                {"op": "update_task", "task_id": "nonexistent", "title": "test"}
            ]
        })
        assert resp.status_code == 207
        data = resp.get_json()
        assert "error" in data["results"][0]

    # ─── Tag operations ──────────────────────────────────────────────────────

    def test_batch_update_note_with_tags(self, client, app):
        with app.app_context():
            entity = Entity(type="note", title="Tagged note", content="Content")
            db.session.add(entity)
            db.session.commit()
            entity_id = entity.id

        resp = client.post("/api/v1/batch", json={
            "operations": [
                {"op": "update_note", "note_id": entity_id, "tag_names": ["test-tag", "another-tag"]}
            ]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data["results"][0]

        with app.app_context():
            tags = EntityTag.query.filter_by(entity_id=entity_id).all()
            assert len(tags) == 2

    def test_batch_create_note_with_content_field(self, client):
        """Support both raw_text and content fields."""
        resp = client.post("/api/v1/batch", json={
            "operations": [{"op": "create_note", "content": "Using content field"}]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data["results"][0]
