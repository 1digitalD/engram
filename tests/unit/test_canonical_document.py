from datetime import datetime, timezone
from unittest.mock import MagicMock

from services.canonical_document import generate_canonical_markdown


def _make_entity(**overrides):
    defaults = {
        "id": "e1",
        "title": None,
        "type": "note",
        "status": "active",
        "lifecycle": "active",
        "follow_up_at": None,
        "properties": {},
        "content": "",
        "source": None,
        "reference_url": None,
        "created_at": datetime(2026, 6, 26, 0, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 6, 26, 0, 0, 0, tzinfo=timezone.utc),
        "entity_tags": [],
    }
    entity = MagicMock()
    for key, value in {**defaults, **overrides}.items():
        setattr(entity, key, value)
    return entity


def test_canonical_markdown_uses_title_when_present():
    entity = _make_entity(title="Real title")
    md = generate_canonical_markdown(entity)
    assert "# Real title" in md
    assert "Untitled" not in md


def test_canonical_markdown_uses_placeholder_for_missing_title():
    entity = _make_entity(title=None, id="n42", type="note")
    md = generate_canonical_markdown(entity)
    assert "# (no title)" in md
    assert "Untitled" not in md


def test_canonical_markdown_placeholder_includes_id_and_type():
    entity = _make_entity(title=None, id="p7", type="project")
    md = generate_canonical_markdown(entity)
    assert "(no title) p7 [project]" in md
