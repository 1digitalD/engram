from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from services import v4_extraction


def _make_note(**overrides):
    defaults = {
        "id": "n1",
        "title": None,
        "type": "note",
        "content": "Some content.",
        "created_at": datetime(2026, 6, 26, 0, 0, 0, tzinfo=timezone.utc),
    }
    note = MagicMock()
    for key, value in {**defaults, **overrides}.items():
        setattr(note, key, value)
    return note


def _patch_models_entity(note):
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = [note]

    mock_entity = MagicMock()
    mock_entity.query.filter.return_value = mock_query
    return patch("models.Entity", mock_entity)


def test_recent_context_block_uses_placeholder_for_missing_title():
    note = _make_note(title=None)

    with _patch_models_entity(note):
        notes = v4_extraction._recent_context_notes()

    block = v4_extraction._format_recent_context_block(notes)
    assert "(no title)" in block
    assert "Untitled" not in block


def test_recent_context_block_uses_title_when_present():
    note = _make_note(title="Real note")

    with _patch_models_entity(note):
        notes = v4_extraction._recent_context_notes()

    block = v4_extraction._format_recent_context_block(notes)
    assert "Real note" in block
    assert "Untitled" not in block


def test_recent_context_block_placeholder_includes_id_and_type():
    note = _make_note(id="n42", title=None, type="note")

    with _patch_models_entity(note):
        notes = v4_extraction._recent_context_notes()

    block = v4_extraction._format_recent_context_block(notes)
    assert "(no title) n42 [note]" in block
