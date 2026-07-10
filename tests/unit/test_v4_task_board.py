from datetime import datetime, timedelta, timezone

from services.v4_task_board import (
    NO_PROJECT_KEY,
    _group_items,
    _normalize_status_filters,
    _sort_key,
    get_task_board,
)


NOW = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)


def test_normalize_status_filters_defaults_to_open_family():
    assert _normalize_status_filters(None) == ["open", "in_progress", "waiting", "blocked"]
    assert _normalize_status_filters([]) == ["open", "in_progress", "waiting", "blocked"]


def test_normalize_status_filters_splits_comma_values():
    assert _normalize_status_filters(["open,done", "cancelled"]) == ["open", "done", "cancelled"]


def test_sort_key_puts_null_dates_last():
    with_date = _sort_key(
        {"title": "B", "created_at": "2026-07-01T12:00:00Z"},
        sort="created_at",
        order="desc",
    )
    without_date = _sort_key({"title": "A", "created_at": None}, sort="created_at", order="desc")
    assert without_date > with_date


def test_group_items_sorts_created_at_descending():
    items = [
        {"id": "t1", "title": "Older", "created_at": "2026-07-01T12:00:00Z"},
        {"id": "t2", "title": "Newer", "created_at": "2026-07-09T12:00:00Z"},
    ]
    parents = {"t1": None, "t2": None}
    groups = _group_items(items, parents, sort="created_at", order="desc")
    assert [row["id"] for row in groups[0]["items"]] == ["t2", "t1"]


def test_group_items_places_no_project_bucket_last():
    items = [
        {"id": "t1", "title": "Zulu", "created_at": "2026-07-01T12:00:00Z"},
        {"id": "t2", "title": "Alpha", "created_at": "2026-07-02T12:00:00Z"},
    ]

    class Parent:
        def __init__(self, id, title):
            self.id = id
            self.title = title
            self.type = "project"
            self.lifecycle = "active"

    parents = {
        "t1": Parent("project-zulu", "Zulu"),
        "t2": None,
    }
    groups = _group_items(items, parents, sort="created_at", order="desc")
    assert groups[0]["label"] == "Zulu"
    assert groups[1]["key"] == NO_PROJECT_KEY


def test_get_task_board_rejects_invalid_status():
    try:
        get_task_board(status_filters=["bogus"], now=NOW)
    except ValueError as exc:
        assert "invalid status filter" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_get_task_board_rejects_invalid_sort():
    try:
        get_task_board(sort="due_at", now=NOW)
    except ValueError as exc:
        assert "sort must be one of" in str(exc)
    else:
        raise AssertionError("expected ValueError")
