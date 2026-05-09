import json
import os
from unittest.mock import MagicMock, patch

import pytest

from extensions import db
from models import Area, BucketType, Note, Project
from services.rollup import rollup_project_to_area


def test_rollup_project_to_area_creates_summary_note_and_archives(app):
    with app.app_context():
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        area = Area(name="Work")
        db.session.add(area)
        db.session.flush()
        proj = Project(name="Ship v1", area_id=area.id)
        db.session.add(proj)
        db.session.flush()
        n1 = Note(
            raw_text="Note one about feature",
            bucket=BucketType.PROJECTS,
            project_id=proj.id,
        )
        n1.projects.append(proj)
        db.session.add(n1)
        db.session.commit()

        mock_usage = MagicMock(input_tokens=10, output_tokens=5)
        mock_text_block = MagicMock()
        mock_text_block.text = json.dumps(
            {
                "summary_text": "Shipped the thing.",
                "key_themes": ["launch"],
                "action_items": [],
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
        assert proj.is_archived is True
        assert summary.area_id == area.id
        assert summary.bucket == BucketType.AREAS
        assert "#retrospective" in summary.raw_text
        assert "#project-complete" in summary.raw_text
        assert "Shipped the thing." in summary.raw_text
        tag_names = {t.name.lower() for t in summary.tags}
        assert "retrospective" in tag_names
        assert "project-complete" in tag_names


def test_rollup_project_requires_parent_area(app):
    with app.app_context():
        proj = Project(name="Orphan project", area_id=None)
        db.session.add(proj)
        db.session.commit()
        with pytest.raises(ValueError, match="no parent area"):
            rollup_project_to_area(proj.id)


def test_rollup_empty_project_creates_note_and_archives(app):
    with app.app_context():
        area = Area(name="Home")
        db.session.add(area)
        db.session.flush()
        proj = Project(name="Empty", area_id=area.id)
        db.session.add(proj)
        db.session.commit()
        summary = rollup_project_to_area(proj.id)
        assert "no notes were linked" in summary.raw_text.lower()
        db.session.refresh(proj)
        assert proj.is_archived is True
        assert summary.area_id == area.id
        assert "#retrospective" in summary.raw_text
