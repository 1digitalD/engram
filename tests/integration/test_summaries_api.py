"""Tests for api/summaries — v2 Entity model.

Verifies that summaries API uses Entity and EntityLink instead of
Note, Project, Area. OpenAI calls are mocked.
"""

import uuid
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from extensions import db
from models import Entity, EntityLink, Summary, SummaryGranularity


# ─── Helpers ─────────────────────────────────────────────────────────────────

NONEXISTENT_UUID = str(uuid.uuid4())


def _create_entity(entity_type, title, content=None, **kwargs):
    entity = Entity(
        type=entity_type,
        title=title,
        content=content or f"Content for {title}",
        **kwargs
    )
    db.session.add(entity)
    db.session.commit()
    return entity


def _link_entities(src_id, dst_id, link_type="related"):
    link = EntityLink(
        src_id=src_id,
        dst_id=dst_id,
        link_type=link_type,
    )
    db.session.add(link)
    db.session.commit()
    return link


def _mock_openai_response():
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "This is the generated weekly summary."
    mock_response.choices = [mock_choice]
    return mock_response


# ─── list_summaries ──────────────────────────────────────────────────────────

class TestListSummaries:
    def test_list_empty(self, client, app):
        with app.app_context():
            resp = client.get("/api/v1/summaries")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["data"] == []

    def test_list_with_summaries(self, client, app):
        with app.app_context():
            note = _create_entity("note", "Test Note")
            summary = Summary(
                note_id=note.id,
                summary_text="Test summary",
                generated_at=datetime.utcnow(),
                granularity=SummaryGranularity.WEEKLY,
            )
            db.session.add(summary)
            db.session.commit()

            resp = client.get("/api/v1/summaries")
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data["data"]) == 1
            assert data["data"][0]["summary_text"] == "Test summary"

    def test_list_filter_by_entity_type(self, client, app):
        with app.app_context():
            note = _create_entity("note", "Test Note")
            s1 = Summary(
                note_id=note.id,
                summary_text="User summary",
                generated_at=datetime.utcnow(),
                entity_type="user",
                granularity=SummaryGranularity.WEEKLY,
            )
            s2 = Summary(
                note_id=note.id,
                summary_text="System summary",
                generated_at=datetime.utcnow(),
                entity_type="system",
                granularity=SummaryGranularity.WEEKLY,
            )
            db.session.add_all([s1, s2])
            db.session.commit()

            resp = client.get("/api/v1/summaries?entity_type=user")
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data["data"]) == 1
            assert data["data"][0]["entity_type"] == "user"


# ─── create_summary ──────────────────────────────────────────────────────────

class TestCreateSummary:
    def test_create_summary_with_entity(self, client, app):
        with app.app_context():
            note = _create_entity("note", "Test Note")

            resp = client.post("/api/v1/summaries", json={
                "note_id": note.id,
                "summary_text": "A new summary",
                "granularity": "WEEKLY",
            })
            assert resp.status_code == 201
            data = resp.get_json()
            assert data["data"]["summary_text"] == "A new summary"
            assert str(data["data"]["note_id"]) == str(note.id)

    def test_create_summary_entity_not_found(self, client, app):
        with app.app_context():
            resp = client.post("/api/v1/summaries", json={
                "note_id": NONEXISTENT_UUID,
                "summary_text": "Should fail",
            })
            assert resp.status_code == 404

    def test_create_summary_missing_fields(self, client, app):
        with app.app_context():
            resp = client.post("/api/v1/summaries", json={})
            assert resp.status_code == 400


# ─── generate_summary (project) ──────────────────────────────────────────────

class TestGenerateSummaryProject:
    @patch("api.summaries.client")
    def test_generate_project_summary(self, mock_client, client, app):
        with app.app_context():
            mock_client.chat.completions.create.return_value = _mock_openai_response()

            project = _create_entity("project", "Test Project")
            note1 = _create_entity("note", "Note 1", content="First note content")
            note2 = _create_entity("note", "Note 2", content="Second note content")

            # Link notes to project
            _link_entities(note1.id, project.id, "project")
            _link_entities(note2.id, project.id, "project")

            resp = client.post("/api/v1/summaries/generate", json={
                "entity_type": "project",
                "entity_id": project.id,
            })
            assert resp.status_code == 201
            data = resp.get_json()
            assert "summary_text" in data["data"]

            # Verify OpenAI was called with project title (not name)
            call_args = mock_client.chat.completions.create.call_args
            prompt = call_args[1]["messages"][1]["content"]
            assert "Test Project" in prompt

    @patch("api.summaries.client")
    def test_generate_project_summary_entity_not_found(self, mock_client, client, app):
        with app.app_context():
            resp = client.post("/api/v1/summaries/generate", json={
                "entity_type": "project",
                "entity_id": NONEXISTENT_UUID,
            })
            assert resp.status_code == 404

    @patch("api.summaries.client")
    def test_generate_project_summary_no_notes(self, mock_client, client, app):
        with app.app_context():
            project = _create_entity("project", "Empty Project")

            resp = client.post("/api/v1/summaries/generate", json={
                "entity_type": "project",
                "entity_id": project.id,
            })
            # Should return 400 when no notes and no note_id provided
            assert resp.status_code == 400


# ─── generate_summary (area) ─────────────────────────────────────────────────

class TestGenerateSummaryArea:
    @patch("api.summaries.client")
    def test_generate_area_summary(self, mock_client, client, app):
        with app.app_context():
            mock_client.chat.completions.create.return_value = _mock_openai_response()

            area = _create_entity("area", "Test Area")
            note1 = _create_entity("note", "Area Note 1", content="Area note content")

            # Link note to area
            _link_entities(note1.id, area.id, "area")

            resp = client.post("/api/v1/summaries/generate", json={
                "entity_type": "area",
                "entity_id": area.id,
            })
            assert resp.status_code == 201
            data = resp.get_json()
            assert "summary_text" in data["data"]

            # Verify OpenAI was called with area title (not name)
            call_args = mock_client.chat.completions.create.call_args
            prompt = call_args[1]["messages"][1]["content"]
            assert "Test Area" in prompt

    @patch("api.summaries.client")
    def test_generate_area_summary_entity_not_found(self, mock_client, client, app):
        with app.app_context():
            resp = client.post("/api/v1/summaries/generate", json={
                "entity_type": "area",
                "entity_id": NONEXISTENT_UUID,
            })
            assert resp.status_code == 404


# ─── generate_summary (validation) ───────────────────────────────────────────

class TestGenerateSummaryValidation:
    def test_missing_entity_type(self, client, app):
        with app.app_context():
            resp = client.post("/api/v1/summaries/generate", json={
                "entity_id": NONEXISTENT_UUID,
            })
            assert resp.status_code == 400

    def test_missing_entity_id(self, client, app):
        with app.app_context():
            resp = client.post("/api/v1/summaries/generate", json={
                "entity_type": "project",
            })
            assert resp.status_code == 400

    def test_invalid_entity_type(self, client, app):
        with app.app_context():
            resp = client.post("/api/v1/summaries/generate", json={
                "entity_type": "invalid",
                "entity_id": NONEXISTENT_UUID,
            })
            assert resp.status_code == 400


# ─── get_summary ─────────────────────────────────────────────────────────────

class TestGetSummary:
    def test_get_summary(self, client, app):
        with app.app_context():
            note = _create_entity("note", "Test Note")
            summary = Summary(
                note_id=note.id,
                summary_text="Get this summary",
                generated_at=datetime.utcnow(),
                granularity=SummaryGranularity.WEEKLY,
            )
            db.session.add(summary)
            db.session.commit()

            resp = client.get(f"/api/v1/summaries/{summary.id}")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["data"]["summary_text"] == "Get this summary"

    def test_get_summary_not_found(self, client, app):
        with app.app_context():
            resp = client.get(f"/api/v1/summaries/{NONEXISTENT_UUID}")
            assert resp.status_code == 404


# ─── patch_summary ───────────────────────────────────────────────────────────

class TestPatchSummary:
    def test_patch_summary_text(self, client, app):
        with app.app_context():
            note = _create_entity("note", "Test Note")
            summary = Summary(
                note_id=note.id,
                summary_text="Original",
                generated_at=datetime.utcnow(),
                granularity=SummaryGranularity.WEEKLY,
            )
            db.session.add(summary)
            db.session.commit()

            resp = client.patch(f"/api/v1/summaries/{summary.id}", json={
                "summary_text": "Updated",
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["data"]["summary_text"] == "Updated"

    def test_patch_summary_note_id_with_entity(self, client, app):
        with app.app_context():
            note1 = _create_entity("note", "Note 1")
            note2 = _create_entity("note", "Note 2")
            summary = Summary(
                note_id=note1.id,
                summary_text="Test",
                generated_at=datetime.utcnow(),
                granularity=SummaryGranularity.WEEKLY,
            )
            db.session.add(summary)
            db.session.commit()

            resp = client.patch(f"/api/v1/summaries/{summary.id}", json={
                "note_id": note2.id,
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert str(data["data"]["note_id"]) == str(note2.id)

    def test_patch_summary_invalid_note_id(self, client, app):
        with app.app_context():
            note = _create_entity("note", "Test Note")
            summary = Summary(
                note_id=note.id,
                summary_text="Test",
                generated_at=datetime.utcnow(),
                granularity=SummaryGranularity.WEEKLY,
            )
            db.session.add(summary)
            db.session.commit()

            resp = client.patch(f"/api/v1/summaries/{summary.id}", json={
                "note_id": NONEXISTENT_UUID,
            })
            assert resp.status_code == 404


# ─── delete_summary ──────────────────────────────────────────────────────────

class TestDeleteSummary:
    def test_delete_summary(self, client, app):
        with app.app_context():
            note = _create_entity("note", "Test Note")
            summary = Summary(
                note_id=note.id,
                summary_text="To delete",
                generated_at=datetime.utcnow(),
                granularity=SummaryGranularity.WEEKLY,
            )
            db.session.add(summary)
            db.session.commit()
            summary_id = summary.id

            resp = client.delete(f"/api/v1/summaries/{summary_id}")
            assert resp.status_code == 200

            resp = client.get(f"/api/v1/summaries/{summary_id}")
            assert resp.status_code == 404

    def test_delete_summary_not_found(self, client, app):
        with app.app_context():
            resp = client.delete(f"/api/v1/summaries/{NONEXISTENT_UUID}")
            assert resp.status_code == 404
