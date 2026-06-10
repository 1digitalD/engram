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
