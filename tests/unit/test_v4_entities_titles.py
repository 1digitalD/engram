from unittest.mock import MagicMock

from api.v4_entities import _activity_update_title


def _make_target(**overrides):
    defaults = {"id": "t1", "title": None, "type": "task"}
    target = MagicMock()
    for key, value in {**defaults, **overrides}.items():
        setattr(target, key, value)
    return target


def test_activity_update_title_uses_title_when_present():
    target = _make_target(title="Real target")
    title = _activity_update_title(target)
    assert title.startswith("Update: Real target")
    assert "Untitled" not in title


def test_activity_update_title_uses_placeholder_for_missing_title():
    target = _make_target(title=None)
    title = _activity_update_title(target)
    assert title.startswith("Update: (no title)")
    assert "Untitled" not in title


def test_activity_update_title_placeholder_includes_id_and_type():
    target = _make_target(id="p99", title=None, type="project")
    title = _activity_update_title(target)
    assert "(no title) p99 [project]" in title
