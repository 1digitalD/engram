"""Tests for status transitions and lifecycle features (V3-5.3).

Tests:
- Project status transitions trigger rollup on completion
- Area archive detaches child projects
- Note lifecycle (bucket) updates
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from extensions import db
from models import Entity, EntityLink, EntityEvent
from services.entity_service import transition_status, archive_entity


# ─── Project status transitions ──────────────────────────────────────────────

class TestProjectStatusTransitions:
    def test_project_active_to_completed(self, app):
        with app.app_context():
            area = Entity(
                type="area", title="Work", content="",
                properties={}, lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(area)
            db.session.flush()

            project = Entity(
                type="project", title="Ship v1", content="",
                properties={"area_id": area.id},
                lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(project)
            db.session.commit()

            updated = transition_status(project.id, "completed", actor="user")
            assert updated.status == "completed"

            event = EntityEvent.query.filter_by(
                entity_id=project.id, event_type="status_changed"
            ).first()
            assert event is not None
            assert event.new_value == {"status": "completed"}

    def test_project_active_to_on_hold(self, app):
        with app.app_context():
            project = Entity(
                type="project", title="Paused", content="",
                properties={}, lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(project)
            db.session.commit()

            updated = transition_status(project.id, "on_hold", actor="user")
            assert updated.status == "on_hold"

    def test_project_completed_to_active(self, app):
        with app.app_context():
            project = Entity(
                type="project", title="Reopened", content="",
                properties={}, lifecycle="active",
                status="completed", ai_meta={}, ai_status="pending",
            )
            db.session.add(project)
            db.session.commit()

            updated = transition_status(project.id, "active", actor="user")
            assert updated.status == "active"

    def test_project_invalid_transition(self, app):
        with app.app_context():
            project = Entity(
                type="project", title="Test", content="",
                properties={}, lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(project)
            db.session.commit()

            with pytest.raises(ValueError, match="invalid transition"):
                transition_status(project.id, "archived", actor="user")


# ─── Area status transitions ─────────────────────────────────────────────────

class TestAreaStatusTransitions:
    def test_area_active_to_archived(self, app):
        with app.app_context():
            area = Entity(
                type="area", title="Archived Area", content="",
                properties={}, lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(area)
            db.session.commit()

            updated = transition_status(area.id, "archived", actor="user")
            assert updated.status == "archived"

    def test_area_archived_to_active(self, app):
        with app.app_context():
            area = Entity(
                type="area", title="Restored", content="",
                properties={}, lifecycle="active",
                status="archived", ai_meta={}, ai_status="pending",
            )
            db.session.add(area)
            db.session.commit()

            updated = transition_status(area.id, "active", actor="user")
            assert updated.status == "active"


# ─── Area archive with child project detachment ──────────────────────────────

class TestAreaArchiveDetachProjects:
    def test_archive_area_detaches_child_projects_via_api(self, app, client):
        """Area archive via API detaches child projects."""
        with app.app_context():
            area = Entity(
                type="area", title="Parent", content="",
                properties={}, lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(area)
            db.session.flush()

            proj1 = Entity(
                type="project", title="Child 1", content="",
                properties={"area_id": area.id},
                lifecycle="active", ai_meta={}, ai_status="pending",
            )
            proj2 = Entity(
                type="project", title="Child 2", content="",
                properties={"area_id": area.id},
                lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add_all([proj1, proj2])
            db.session.commit()
            area_id = area.id
            proj1_id = proj1.id
            proj2_id = proj2.id

        # Archive via API
        response = client.patch(
            f"/api/v1/areas/{area_id}",
            json={"is_archived": True},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["lifecycle"] == "archived"
        assert data.get("detached_projects") == 2

        # Verify projects are detached
        with app.app_context():
            p1 = db.session.get(Entity, proj1_id)
            p2 = db.session.get(Entity, proj2_id)
            assert "area_id" not in (p1.properties or {})
            assert "area_id" not in (p2.properties or {})

    def test_archive_area_no_child_projects(self, app, client):
        with app.app_context():
            area = Entity(
                type="area", title="Empty", content="",
                properties={}, lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(area)
            db.session.commit()
            area_id = area.id

        response = client.patch(
            f"/api/v1/areas/{area_id}",
            json={"is_archived": True},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["lifecycle"] == "archived"
        assert data.get("detached_projects") == 0


# ─── Rollup trigger on project completion ────────────────────────────────────

class TestRollupTrigger:
    def test_rollup_called_on_project_completion(self, app):
        with app.app_context():
            os.environ["ANTHROPIC_API_KEY"] = "test-key"

            area = Entity(
                type="area", title="Work", content="",
                properties={}, lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(area)
            db.session.flush()

            project = Entity(
                type="project", title="Complete Me", content="",
                properties={"area_id": area.id},
                lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(project)
            db.session.commit()

            # Mock the summarizer to avoid real API calls
            mock_usage = MagicMock(input_tokens=10, output_tokens=5)
            mock_text_block = MagicMock()
            mock_text_block.text = json.dumps({
                "accomplished": "Done everything",
                "key_decisions": "Good decisions",
                "lessons_learned": "Learned stuff",
                "outstanding_items": "Nothing",
            })
            mock_msg = MagicMock()
            mock_msg.content = [mock_text_block]
            mock_msg.usage = mock_usage
            mock_client = MagicMock()
            mock_client.messages.create = MagicMock(return_value=mock_msg)

            with patch("anthropic.Anthropic", return_value=mock_client):
                from services.rollup import rollup_project_to_area
                summary = rollup_project_to_area(project.id)

            db.session.refresh(project)
            assert project.lifecycle == "archived"
            assert summary.type == "note"
            assert "Retrospective" in summary.title


# ─── API: Project completion triggers rollup ─────────────────────────────────

class TestProjectCompletionAPI:
    def test_patch_project_completed_triggers_rollup(self, app, client):
        os.environ["ANTHROPIC_API_KEY"] = "test-key"

        with app.app_context():
            area = Entity(
                type="area", title="Work", content="",
                properties={}, lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(area)
            db.session.flush()

            project = Entity(
                type="project", title="API Test Project", content="",
                properties={"area_id": area.id},
                lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(project)
            db.session.commit()
            project_id = project.id

        # Mock the summarizer
        mock_usage = MagicMock(input_tokens=10, output_tokens=5)
        mock_text_block = MagicMock()
        mock_text_block.text = json.dumps({
            "accomplished": "API test accomplished",
            "key_decisions": "API decisions",
            "lessons_learned": "API lessons",
            "outstanding_items": "API items",
        })
        mock_msg = MagicMock()
        mock_msg.content = [mock_text_block]
        mock_msg.usage = mock_usage
        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_msg)

        with patch("anthropic.Anthropic", return_value=mock_client):
            response = client.patch(
                f"/api/v1/projects/{project_id}",
                json={"status": "completed"},
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["status"] == "completed"
        # Rollup should have been triggered
        assert data.get("rollup") is not None
        assert "summary_id" in data["rollup"]

    def test_patch_project_status_normalized(self, app, client):
        with app.app_context():
            project = Entity(
                type="project", title="Normalize Test", content="",
                properties={}, lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(project)
            db.session.commit()
            project_id = project.id

        response = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"status": "DONE"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["status"] == "completed"


# ─── API: Area archive with detachment ───────────────────────────────────────

class TestAreaArchiveAPI:
    def test_patch_area_archive_detaches_projects(self, app, client):
        with app.app_context():
            area = Entity(
                type="area", title="Archive Test", content="",
                properties={}, lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(area)
            db.session.flush()

            proj = Entity(
                type="project", title="Child Project", content="",
                properties={"area_id": area.id},
                lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(proj)
            db.session.commit()
            area_id = area.id
            proj_id = proj.id

        response = client.patch(
            f"/api/v1/areas/{area_id}",
            json={"is_archived": True},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["lifecycle"] == "archived"
        assert data.get("detached_projects") == 1

        # Verify project was detached
        with app.app_context():
            p = db.session.get(Entity, proj_id)
            assert "area_id" not in (p.properties or {})

    def test_patch_area_status_transition(self, app, client):
        with app.app_context():
            area = Entity(
                type="area", title="Status Test", content="",
                properties={}, lifecycle="active", ai_meta={}, ai_status="pending",
            )
            db.session.add(area)
            db.session.commit()
            area_id = area.id

        response = client.patch(
            f"/api/v1/areas/{area_id}",
            json={"status": "archived"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["status"] == "archived"
