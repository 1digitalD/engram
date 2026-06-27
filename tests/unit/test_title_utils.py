from unittest.mock import MagicMock

from services.title_utils import title_or_placeholder


def _make_entity(**overrides):
    defaults = {"id": "e1", "title": None, "type": "note"}
    entity = MagicMock()
    for key, value in {**defaults, **overrides}.items():
        setattr(entity, key, value)
    return entity


def test_returns_title_when_present():
    entity = _make_entity(title="Real title")
    assert title_or_placeholder(entity) == "Real title"


def test_returns_placeholder_with_id_and_type():
    entity = _make_entity(title=None, id="p7", type="project")
    assert title_or_placeholder(entity) == "(no title) p7 [project]"


def test_returns_placeholder_without_type_when_disabled():
    entity = _make_entity(title=None, id="p7", type="project")
    assert title_or_placeholder(entity, include_type=False) == "(no title) p7"


def test_placeholder_omits_id_when_missing():
    entity = _make_entity(title=None, id=None, type="note")
    assert title_or_placeholder(entity) == "(no title) [note]"


def test_placeholder_omits_type_when_missing():
    entity = _make_entity(title=None, id="e1", type=None)
    assert title_or_placeholder(entity) == "(no title) e1"


def test_placeholder_never_contains_untitled():
    entity = _make_entity(title=None)
    assert "Untitled" not in title_or_placeholder(entity)
