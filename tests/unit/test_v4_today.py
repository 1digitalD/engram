"""Unit tests for v6 Today feed extensions."""

from datetime import datetime, timedelta, timezone

from extensions import db
from models import AppSetting
from services.v4_today import (
    AT_RISK_SNAPSHOT_KEY,
    compute_newly_at_risk,
    extend_today_payload,
    load_at_risk_snapshot,
    save_at_risk_snapshot,
)

NOW = datetime(2026, 7, 8, 15, 0, tzinfo=timezone.utc)


def test_extend_today_payload_partitions_needs_you_and_in_motion():
    payload = {
        "overdue": [{"id": "task-overdue", "title": "Overdue task", "attention": {"reasons": [{"label": "overdue"}]}}],
        "due_today": [{"id": "task-today", "title": "Due today", "attention": {"reasons": [{"label": "due today"}]}}],
        "upcoming_due_tasks": [{"id": "task-later", "title": "Later task", "attention": {"reasons": []}}],
        "recent_notes": [{"id": "note-1", "title": "Recent note", "ai": {"intent": "reference"}}],
        "delegations_quiet": [],
        "dependency_interventions": [],
        "pending_suggestions": [],
        "fired_markers": [
            {
                "id": "marker-1",
                "kind": "nudge",
                "note": "Ping Sam",
                "entity": {"id": "task-1", "type": "task", "title": "Task"},
            }
        ],
        "blocked_tasks": [],
        "waiting_tasks": [],
        "unscheduled_attention_tasks": [],
        "stale_projects": [],
        "suggested_archival": [],
        "new_since_yesterday_count": 0,
    }

    extend_today_payload(payload, NOW)

    assert payload["counts"]["needs_you"] == len(payload["needs_you"])
    assert payload["counts"]["in_motion"] == len(payload["in_motion"])
    assert payload["counts"]["fired_markers"] == 1
    assert any(item["kind"] == "fired_marker" for item in payload["needs_you"])
    assert any(item["kind"] == "upcoming_due" for item in payload["in_motion"])
    assert any(item["kind"] == "recent_note" for item in payload["in_motion"])


def test_compute_newly_at_risk_excludes_prior_snapshot_keys(app):
    with app.app_context():
        save_at_risk_snapshot(
            [
                {
                    "id": "task-old",
                    "type": "task",
                    "title": "Old risk",
                    "reason": "stale",
                    "receipts": [],
                }
            ],
            NOW - timedelta(days=1),
        )

        def fake_list(_now=None):
            return [
                {
                    "id": "task-old",
                    "type": "task",
                    "title": "Old risk",
                    "reason": "still stale",
                    "receipts": [],
                },
                {
                    "id": "task-new",
                    "type": "task",
                    "title": "Fresh risk",
                    "reason": "new stale",
                    "receipts": [],
                },
            ]

        from services import v4_today

        original = v4_today.list_at_risk_items
        v4_today.list_at_risk_items = fake_list
        try:
            newly = compute_newly_at_risk(NOW)
        finally:
            v4_today.list_at_risk_items = original

        assert [item["id"] for item in newly] == ["task-new"]
        snapshot = load_at_risk_snapshot()
        assert "task:task-old" in snapshot["keys"]


def test_compute_newly_at_risk_empty_without_snapshot(app):
    with app.app_context():
        setting = db.session.get(AppSetting, AT_RISK_SNAPSHOT_KEY)
        if setting is not None:
            db.session.delete(setting)
            db.session.commit()

        from services import v4_today

        original = v4_today.list_at_risk_items
        v4_today.list_at_risk_items = lambda _now=None: [
            {"id": "task-1", "type": "task", "title": "Risk", "reason": "stale", "receipts": []}
        ]
        try:
            assert compute_newly_at_risk(NOW) == []
        finally:
            v4_today.list_at_risk_items = original
