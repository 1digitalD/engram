import json
import os
from unittest.mock import MagicMock, patch

import pytest

from extensions import db
from models import Entity, EntityLink
from services.moc import generate_map_of_content


def _create_source_entity(content: str) -> Entity:
    entity = Entity(
        type="note",
        title=content[:50],
        content=content,
        properties={},
        lifecycle="active",
        ai_meta={},
        ai_status="pending",
    )
    db.session.add(entity)
    db.session.flush()
    return entity


def test_generate_moc_creates_entity_and_links(app):
    with app.app_context():
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        src1 = _create_source_entity("Machine learning fundamentals and neural networks.")
        src2 = _create_source_entity("Deep learning architectures and training techniques.")
        db.session.commit()

        mock_text_block = MagicMock()
        mock_text_block.text = json.dumps({
            "title": "AI Knowledge Map",
            "overview": "A map covering AI fundamentals.",
            "sections": [
                {
                    "heading": "Fundamentals",
                    "body": "See [ML basics](/notes/%s)" % src1.id,
                },
                {
                    "heading": "Advanced",
                    "body": "See [DL techniques](/notes/%s)" % src2.id,
                },
            ],
        })
        mock_msg = MagicMock()
        mock_msg.content = [mock_text_block]
        mock_client_instance = MagicMock()
        mock_client_instance.messages.create = MagicMock(return_value=mock_msg)

        with patch("anthropic.Anthropic", return_value=mock_client_instance):
            moc = generate_map_of_content([src1.id, src2.id])

        assert moc.type == "note"
        assert moc.title == "AI Knowledge Map"
        assert "#moc" in moc.content
        assert "AI Knowledge Map" in moc.content

        ai_meta = moc.ai_meta or {}
        assert "moc_source_note_ids" in ai_meta

        links = EntityLink.query.filter_by(
            src_id=moc.id, link_type="child_of"
        ).all()
        assert len(links) == 2
        link_dst_ids = {link.dst_id for link in links}
        assert src1.id in link_dst_ids
        assert src2.id in link_dst_ids


def test_generate_moc_empty_ids_raises(app):
    with app.app_context():
        with pytest.raises(ValueError, match="must be non-empty"):
            generate_map_of_content([])


def test_generate_moc_missing_entity_raises(app):
    with app.app_context():
        with pytest.raises(ValueError, match="not found"):
            generate_map_of_content(["00000000-0000-0000-0000-000000000000"])


def test_generate_moc_no_api_key_raises(app):
    with app.app_context():
        entity = _create_source_entity("test content")
        db.session.commit()

        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                generate_map_of_content([entity.id])
        finally:
            if old_key is not None:
                os.environ["ANTHROPIC_API_KEY"] = old_key


def test_generate_moc_deduplicates_ids(app):
    with app.app_context():
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        src = _create_source_entity("Duplicate test content.")
        db.session.commit()

        mock_text_block = MagicMock()
        mock_text_block.text = json.dumps({
            "title": "Test MOC",
            "overview": "Overview.",
            "sections": [{"heading": "Section", "body": "Body."}],
        })
        mock_msg = MagicMock()
        mock_msg.content = [mock_text_block]
        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_msg)

        with patch("anthropic.Anthropic", return_value=mock_client):
            moc = generate_map_of_content([src.id, src.id, src.id])

        links = EntityLink.query.filter_by(src_id=moc.id, link_type="child_of").all()
        assert len(links) == 1
        assert links[0].dst_id == src.id


def test_generate_moc_no_sections_fallback(app):
    with app.app_context():
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        src = _create_source_entity("Single note content.")
        db.session.commit()

        mock_text_block = MagicMock()
        mock_text_block.text = json.dumps({
            "title": "Minimal MOC",
            "overview": "Minimal overview.",
            "sections": [],
        })
        mock_msg = MagicMock()
        mock_msg.content = [mock_text_block]
        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_msg)

        with patch("anthropic.Anthropic", return_value=mock_client):
            moc = generate_map_of_content([src.id])

        assert "## Sources" in moc.content
        assert "No sections returned" in moc.content
