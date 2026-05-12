"""Unit tests for api/tags.py."""
import pytest
from extensions import db
from models import Tag


class TestTagsAPI:
    def test_list_tags_empty(self, client):
        resp = client.get("/api/v1/tags")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"] == []

    def test_list_tags(self, client, app):
        with app.app_context():
            db.session.add(Tag(name="python"))
            db.session.add(Tag(name="testing"))
            db.session.commit()

        resp = client.get("/api/v1/tags")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["data"]) == 2

    def test_get_tag(self, client, app):
        with app.app_context():
            tag = Tag(name="python")
            db.session.add(tag)
            db.session.commit()
            tag_id = tag.id

        resp = client.get(f"/api/v1/tags/{tag_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["name"] == "python"

    def test_get_tag_not_found(self, client):
        resp = client.get("/api/v1/tags/nonexistent")
        assert resp.status_code == 404

    def test_create_tag(self, client):
        resp = client.post("/api/v1/tags", json={"name": "new-tag"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["data"]["name"] == "new-tag"

    def test_create_tag_no_name(self, client):
        resp = client.post("/api/v1/tags", json={})
        assert resp.status_code == 400

    def test_create_tag_existing_returns_200(self, client, app):
        with app.app_context():
            db.session.add(Tag(name="existing"))
            db.session.commit()

        resp = client.post("/api/v1/tags", json={"name": "existing"})
        assert resp.status_code == 200

    def test_update_tag(self, client, app):
        with app.app_context():
            tag = Tag(name="old-name")
            db.session.add(tag)
            db.session.commit()
            tag_id = tag.id

        resp = client.patch(f"/api/v1/tags/{tag_id}", json={"name": "new-name"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["name"] == "new-name"

    def test_update_tag_not_found(self, client):
        resp = client.patch("/api/v1/tags/nonexistent", json={"name": "test"})
        assert resp.status_code == 404

    def test_update_tag_color(self, client, app):
        with app.app_context():
            tag = Tag(name="colored")
            db.session.add(tag)
            db.session.commit()
            tag_id = tag.id

        resp = client.patch(f"/api/v1/tags/{tag_id}", json={"color": "#ff0000"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["color"] == "#ff0000"

    def test_delete_tag(self, client, app):
        with app.app_context():
            tag = Tag(name="to-delete")
            db.session.add(tag)
            db.session.commit()
            tag_id = tag.id

        resp = client.delete(f"/api/v1/tags/{tag_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_delete_tag_not_found(self, client):
        resp = client.delete("/api/v1/tags/nonexistent")
        assert resp.status_code == 404
