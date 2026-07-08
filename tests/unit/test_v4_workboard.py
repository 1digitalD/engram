from datetime import datetime, timedelta, timezone

from services.v4_workboard import (
    DEFAULT_STALE_DAYS,
    derive_space_at_risk,
    derive_task_states,
    space_stale_threshold_days,
)


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def _task(**overrides):
    task = {
        "id": "task-1",
        "title": "Task",
        "status": "open",
        "due_at": None,
        "owner_id": None,
        "stale_days": 0,
        "space_finish_line_at": None,
        "space_id": "space-1",
        "blocked_by_open_ids": [],
        "prior_at_risk": False,
        "stale_threshold_days": DEFAULT_STALE_DAYS,
    }
    task.update(overrides)
    return task


def _space(**overrides):
    space = {
        "id": "space-1",
        "title": "Space",
        "due_at": None,
        "open_tasks_count": 0,
        "stale_open_tasks_count": 0,
        "last_activity_days": 0,
        "prior_at_risk": False,
    }
    space.update(overrides)
    return space


def test_tc20_mine_and_waiting_on_follow_operator_identity():
    mine = derive_task_states(
        _task(owner_id="person-1"),
        operator_person_id="person-1",
        operator_configured=True,
        now=NOW,
    )
    waiting = derive_task_states(
        _task(owner_id="person-2"),
        operator_person_id="person-1",
        operator_configured=True,
        now=NOW,
    )
    unconfigured = derive_task_states(
        _task(owner_id="person-2"),
        operator_person_id=None,
        operator_configured=False,
        now=NOW,
    )

    assert mine["mine"] is True
    assert mine["waiting_on"] is False
    assert waiting["mine"] is False
    assert waiting["waiting_on"] is True
    assert unconfigured["mine"] is True
    assert unconfigured["waiting_on"] is False


def test_tc20_overdue_stale_and_blocked_predicates():
    states = derive_task_states(
        _task(
            due_at=NOW - timedelta(days=1),
            stale_days=11,
            blocked_by_open_ids=["blocker-1"],
        ),
        operator_person_id="person-1",
        operator_configured=True,
        now=NOW,
    )

    assert states["overdue"] is True
    assert states["stale"] is True
    assert states["blocked"] is True


def test_tc20_at_risk_reason_and_receipts_are_present():
    states = derive_task_states(
        _task(
            stale_days=12,
            due_at=NOW + timedelta(days=5),
            prior_at_risk=False,
        ),
        operator_person_id="person-1",
        operator_configured=True,
        now=NOW,
    )

    assert states["at_risk"] is True
    assert "reason" in states["at_risk_detail"]
    assert states["at_risk_detail"]["reason"]
    assert states["at_risk_detail"]["receipts"]


def test_tc23_hysteresis_keeps_at_risk_until_threshold_plus_two_days():
    sticky = derive_task_states(
        _task(
            stale_days=9,
            due_at=NOW + timedelta(days=8),
            prior_at_risk=True,
        ),
        operator_person_id="person-1",
        operator_configured=True,
        now=NOW,
    )
    cleared = derive_task_states(
        _task(
            stale_days=7,
            due_at=NOW + timedelta(days=10),
            prior_at_risk=True,
        ),
        operator_person_id="person-1",
        operator_configured=True,
        now=NOW,
    )

    assert sticky["at_risk"] is True
    assert cleared["at_risk"] is False


def test_tc24_space_threshold_override_changes_stale_verdict():
    assert space_stale_threshold_days({"thresholds": {"stale_days": 14}}) == 14
    assert space_stale_threshold_days({}) == DEFAULT_STALE_DAYS

    default_states = derive_task_states(
        _task(stale_days=11, stale_threshold_days=DEFAULT_STALE_DAYS),
        operator_person_id="person-1",
        operator_configured=True,
        now=NOW,
    )
    overridden_states = derive_task_states(
        _task(stale_days=11, stale_threshold_days=14),
        operator_person_id="person-1",
        operator_configured=True,
        now=NOW,
    )

    assert default_states["stale"] is True
    assert overridden_states["stale"] is False


def test_tc20_space_at_risk_uses_finish_line_and_space_activity():
    risk = derive_space_at_risk(
        _space(
            due_at=NOW + timedelta(days=10),
            open_tasks_count=4,
            stale_open_tasks_count=2,
            last_activity_days=16,
        ),
        now=NOW,
    )

    assert risk["flag"] is True
    assert risk["reason"]
    assert risk["receipts"]
