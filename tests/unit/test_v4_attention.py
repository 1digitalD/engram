from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from services.v4_attention import attention_for_entity


def test_attention_scores_overdue_blocked_urgent_task():
    now = datetime(2026, 6, 7, tzinfo=timezone.utc)
    entity = SimpleNamespace(
        type="task",
        status="blocked",
        due_at=now - timedelta(days=2),
        follow_up_at=None,
        properties={"priority": "urgent"},
        ai_meta={},
    )

    attention = attention_for_entity(entity, now=now)

    assert attention["level"] == "urgent"
    assert attention["score"] == 100
    assert [reason["key"] for reason in attention["reasons"][:3]] == [
        "due:overdue",
        "status:blocked",
        "priority:urgent",
    ]


def test_attention_uses_inherited_priority_when_own_is_unset():
    now = datetime(2026, 6, 7, tzinfo=timezone.utc)
    entity = SimpleNamespace(
        type="task",
        status="open",
        due_at=None,
        follow_up_at=None,
        properties={},
        ai_meta={},
    )

    attention = attention_for_entity(entity, now=now, inherited_priority="high")

    reason = next(r for r in attention["reasons"] if r["key"] == "priority:high")
    assert reason["weight"] == 25
    assert "from project" in reason["label"]


def test_attention_prefers_own_priority_over_inherited():
    now = datetime(2026, 6, 7, tzinfo=timezone.utc)
    entity = SimpleNamespace(
        type="task",
        status="open",
        due_at=None,
        follow_up_at=None,
        properties={"priority": "low"},
        ai_meta={},
    )

    attention = attention_for_entity(entity, now=now, inherited_priority="urgent")

    reason = next(r for r in attention["reasons"] if r["key"] == "priority:low")
    assert "from project" not in reason["label"]


def test_attention_staleness_weight_table():
    now = datetime(2026, 6, 7, tzinfo=timezone.utc)
    entity = SimpleNamespace(
        type="task",
        status="open",
        due_at=None,
        follow_up_at=None,
        properties={},
        ai_meta={},
    )

    cases = [
        (0, 0),
        (2, 0),
        (3, 4),
        (6, 4),
        (7, 10),
        (13, 10),
        (14, 18),
        (20, 18),
        (21, 25),
        (40, 25),
    ]
    for days, expected_weight in cases:
        attention = attention_for_entity(entity, now=now, staleness_days=days)
        reason = next((r for r in attention["reasons"] if r["key"] == "staleness"), None)
        if expected_weight == 0:
            assert reason is None, f"days={days}"
        else:
            assert reason["weight"] == expected_weight, f"days={days}"
            assert reason["label"] == f"no update in {days} days"


def test_attention_impact_weight_table():
    now = datetime(2026, 6, 7, tzinfo=timezone.utc)
    entity = SimpleNamespace(
        type="task",
        status="open",
        due_at=None,
        follow_up_at=None,
        properties={},
        ai_meta={},
    )

    cases = [
        (0, 0),
        (1, 12),
        (2, 24),
        (3, 24),
    ]
    for count, expected_weight in cases:
        attention = attention_for_entity(entity, now=now, blocks_count=count)
        reason = next((r for r in attention["reasons"] if r["key"] == "impact:blocks"), None)
        if expected_weight == 0:
            assert reason is None, f"count={count}"
        else:
            assert reason["weight"] == expected_weight, f"count={count}"


def test_attention_undated_high_priority_stale_task_outranks_dated_low_priority_task():
    now = datetime(2026, 6, 7, tzinfo=timezone.utc)

    dated_low_priority = SimpleNamespace(
        type="task",
        status="open",
        due_at=now,
        follow_up_at=None,
        properties={"priority": "low"},
        ai_meta={},
    )
    undated_high_priority_stale = SimpleNamespace(
        type="task",
        status="open",
        due_at=None,
        follow_up_at=None,
        properties={"priority": "high"},
        ai_meta={},
    )

    dated_score = attention_for_entity(dated_low_priority, now=now)["score"]
    undated_score = attention_for_entity(undated_high_priority_stale, now=now, staleness_days=14)["score"]

    assert undated_score > dated_score


def test_attention_scores_high_signal_note_intent():
    now = datetime(2026, 6, 7, tzinfo=timezone.utc)
    entity = SimpleNamespace(
        type="note",
        status="active",
        due_at=None,
        follow_up_at=None,
        properties={},
        ai_meta={"intent": "blocker"},
    )

    attention = attention_for_entity(entity, pending_suggestion_count=2, context=["needs_review"], now=now)

    assert attention["level"] == "high"
    assert attention["score"] == 63
    assert {reason["key"] for reason in attention["reasons"]} >= {
        "intent:blocker",
        "pending_suggestions",
        "context:needs_review",
    }
