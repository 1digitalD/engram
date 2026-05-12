"""Unit tests for api/batch.py."""
import pytest
from extensions import db
from models import Note


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
            note = Note(raw_text="Batch test note")
            db.session.add(note)
            db.session.commit()
            note_id = note.id

        resp = client.post("/api/v1/batch", json={
            "operations": [{"op": "get_note", "note_id": note_id}]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "data" in data["results"][0]
        assert data["results"][0]["data"]["note"]["raw_text"] == "Batch test note"

    def test_batch_update_note(self, client, app):
        with app.app_context():
            note = Note(raw_text="Original text")
            db.session.add(note)
            db.session.commit()
            note_id = note.id

        resp = client.post("/api/v1/batch", json={
            "operations": [
                {"op": "update_note", "note_id": note_id, "raw_text": "Updated text"}
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
