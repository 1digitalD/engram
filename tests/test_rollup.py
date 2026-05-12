import json
import os
from unittest.mock import MagicMock, patch

import pytest

from extensions import db
from models import Entity, EntityLink
from services.rollup import rollup_project_to_area


def _create_area(title: str) -> Entity:
    area = Entity(
        type="area",
        title=title,
        content="",
        properties={},
        lifecycle="active",
        ai_meta={},
        ai_status="pending",
    )
    db.session.add(area)
    db.session.flush()
    return area


def _create_project(title: str, area_id: str) -> Entity:
    project = Entity(
        type="project",
        title=title,
        content="",
        properties={"area_id": area_id},
        lifecycle="active",
        ai_meta={},
        ai_status="pending",
    )
    db.session.add(project)
    db.session.flush()
    return project


def _create_note(content: str, project_id: str) -> Entity:
    note = Entity(
        type="note",
        title=content[:50],
        content=content,
        properties={},
        lifecycle="active",
        ai_meta={},
        ai_status="pending",
    )
    db.session.add(note)
    db.session.flush()
    link = EntityLink(
        src_id=note.id,
        dst_id=project_id,
        link_type="related",
        source="manual",
    )
    db.session.add(link)
    db.session.flush()
    return note


def test_rollup_project_to_area_creates_summary_note_and_archives(app):
    with app.app_context():
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        area = _create_area("Work")
        proj = _create_project("Ship v1", area.id)
        _create_note("Note one about feature", proj.id)
        db.session.commit()

        mock_usage = MagicMock(input_tokens=10, output_tokens=5)
        mock_text_block = MagicMock()
        mock_text_block.text = json.dumps(
            {
                "accomplished": "- Shipped the thing.",
                "key_decisions": "- Used weekly milestones.",
                "lessons_learned": "- Earlier QA catches regressions.",
                "outstanding_items": "- Monitor adoption metrics.",
            }
        )
        mock_msg = MagicMock()
        mock_msg.content = [mock_text_block]
        mock_msg.usage = mock_usage
        mock_client_instance = MagicMock()
        mock_client_instance.messages.create = MagicMock(return_value=mock_msg)

        with patch("anthropic.Anthropic", return_value=mock_client_instance):
            summary = rollup_project_to_area(proj.id)

        db.session.refresh(proj)
        assert proj.lifecycle == "archived"
        assert summary.type == "note"
        assert summary.properties.get("area_id") == str(area.id)
        assert summary.properties.get("bucket") == "AREAS"
        assert "#retrospective" in summary.content
        assert "#project-complete" in summary.content
        assert "## What was accomplished" in summary.content
        assert "## Key decisions" in summary.content
        assert "## Lessons learned" in summary.content
        assert "## Outstanding items" in summary.content
        assert "Shipped the thing." in summary.content
        assert "weekly milestones" in summary.content
        tag_names = {et.tag.name.lower() for et in summary.entity_tags}
        assert "retrospective" in tag_names
        assert "project-complete" in tag_names

        link = EntityLink.query.filter_by(
            src_id=summary.id, dst_id=proj.id, link_type="related"
        ).first()
        assert link is not None


def test_rollup_project_requires_parent_area(app):
    with app.app_context():
        proj = Entity(
            type="project",
            title="Orphan project",
            content="",
            properties={},
            lifecycle="active",
            ai_meta={},
            ai_status="pending",
        )
        db.session.add(proj)
        db.session.commit()
        with pytest.raises(ValueError, match="no parent area"):
            rollup_project_to_area(proj.id)


def test_rollup_empty_project_creates_note_and_archives(app):
    with app.app_context():
        area = _create_area("Home")
        proj = _create_project("Empty", area.id)
        db.session.commit()
        summary = rollup_project_to_area(proj.id)
        low = summary.content.lower()
        assert "no notes were linked" in low
        assert "## what was accomplished" in low
        assert "## key decisions" in low
        db.session.refresh(proj)
        assert proj.lifecycle == "archived"
        assert summary.properties.get("area_id") == str(area.id)
        assert "#retrospective" in summary.content
