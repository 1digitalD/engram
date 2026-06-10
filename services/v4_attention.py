"""Shared attention scoring for v4 workspace surfaces."""

from __future__ import annotations

from datetime import datetime, time, timezone


PRIORITY_WEIGHTS = {
    "urgent": 35,
    "high": 25,
    "medium": 15,
    "med": 15,
    "low": 5,
}

INTENT_WEIGHTS = {
    "blocker": 35,
    "follow_up": 25,
    "delegation": 22,
    "task_signal": 15,
    "update": 8,
    "reference": 4,
    "note": 0,
    "junk": -20,
}

STATUS_WEIGHTS = {
    "blocked": 35,
    "waiting": 20,
}

CONTEXT_WEIGHTS = {
    "needs_review": 12,
    "project_without_open_tasks": 18,
}

# Staleness: weight by days since the entity's last activity (no update,
# no recent change). Lets undated/unscheduled tasks accrue attention from
# being neglected, not just from due/follow-up dates.
STALENESS_THRESHOLDS = (
    (21, 25),
    (14, 18),
    (7, 10),
    (3, 4),
)

# Impact: weight by how many other active, non-done entities this entity
# blocks. Lets a blocker task rank highly even with no date of its own.
IMPACT_WEIGHT_PER_BLOCK = 12
IMPACT_WEIGHT_CAP = 24


def attention_for_entity(
    entity,
    *,
    pending_suggestion_count=0,
    context=None,
    now=None,
    inherited_priority=None,
    staleness_days=None,
    blocks_count=0,
):
    """Return derived attention metadata for an entity-like object.

    `inherited_priority` (e.g. a parent project's priority) is used only when
    the entity has no `properties.priority` of its own.

    `staleness_days` (days since the entity's last activity) and
    `blocks_count` (how many other active entities this one blocks) let
    undated tasks accrue attention from neglect (staleness) and impact
    (blockage) rather than only from due/follow-up dates. Both are computed
    by the caller via batched queries — this function stays pure.
    """
    now = now or datetime.now(timezone.utc)
    reasons = []

    due_at = _datetime_value(entity, "due_at")
    follow_up_at = _datetime_value(entity, "follow_up_at")
    status = _value(entity, "status")
    own_priority = ((_value(entity, "properties") or {}).get("priority") or "").lower()
    priority = own_priority or (inherited_priority or "").lower()
    priority_inherited = not own_priority and bool(priority)
    intent = ((_value(entity, "ai") or {}).get("intent") or (_value(entity, "ai_meta") or {}).get("intent") or "").lower()

    if due_at:
        _add_date_reason(reasons, "due", "due date", due_at, now, overdue_weight=45, today_weight=32, upcoming_weight=8)
    if follow_up_at:
        _add_date_reason(reasons, "follow_up", "follow-up", follow_up_at, now, overdue_weight=38, today_weight=28, upcoming_weight=6)

    status_weight = STATUS_WEIGHTS.get(status, 0)
    if status_weight:
        reasons.append({"key": f"status:{status}", "label": status.replace("_", " "), "weight": status_weight})

    priority_weight = PRIORITY_WEIGHTS.get(priority, 0)
    if priority_weight:
        label = f"{priority} priority"
        if priority_inherited:
            label += " (from project)"
        reasons.append({"key": f"priority:{priority}", "label": label, "weight": priority_weight})

    intent_weight = INTENT_WEIGHTS.get(intent, 0)
    if intent_weight:
        reasons.append({"key": f"intent:{intent}", "label": f"captured {intent.replace('_', ' ')}", "weight": intent_weight})

    if pending_suggestion_count:
        reasons.append({
            "key": "pending_suggestions",
            "label": f"{pending_suggestion_count} pending suggestion{'s' if pending_suggestion_count != 1 else ''}",
            "weight": min(24, 8 + pending_suggestion_count * 4),
        })

    for item in context or []:
        weight = CONTEXT_WEIGHTS.get(item, 0)
        if weight:
            reasons.append({"key": f"context:{item}", "label": item.replace("_", " "), "weight": weight})

    if staleness_days is not None:
        staleness_weight = _staleness_weight(staleness_days)
        if staleness_weight:
            reasons.append({
                "key": "staleness",
                "label": f"no update in {staleness_days} days",
                "weight": staleness_weight,
            })

    if blocks_count:
        impact_weight = min(IMPACT_WEIGHT_CAP, blocks_count * IMPACT_WEIGHT_PER_BLOCK)
        reasons.append({
            "key": "impact:blocks",
            "label": f"blocks {blocks_count} other item{'s' if blocks_count != 1 else ''}",
            "weight": impact_weight,
        })

    score = max(0, min(100, sum(reason["weight"] for reason in reasons)))
    return {
        "score": score,
        "level": _level(score),
        "reasons": sorted(reasons, key=lambda reason: reason["weight"], reverse=True),
    }


def _add_date_reason(reasons, key, label, value, now, *, overdue_weight, today_weight, upcoming_weight):
    start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    end = datetime.combine(now.date(), time.max, tzinfo=timezone.utc)
    if value < start:
        days = max(1, (start.date() - value.date()).days)
        weight = min(60, overdue_weight + min(days, 7) * 2)
        reasons.append({"key": f"{key}:overdue", "label": f"{label} overdue", "weight": weight})
    elif value <= end:
        reasons.append({"key": f"{key}:today", "label": f"{label} today", "weight": today_weight})
    else:
        days_until = (value.date() - now.date()).days
        if days_until <= 7:
            reasons.append({"key": f"{key}:upcoming", "label": f"{label} upcoming", "weight": upcoming_weight})


def _staleness_weight(days):
    for threshold, weight in STALENESS_THRESHOLDS:
        if days >= threshold:
            return weight
    return 0


def _level(score):
    if score >= 75:
        return "urgent"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _datetime_value(entity, key):
    value = _value(entity, key)
    if value is None or isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _value(entity, key):
    if isinstance(entity, dict):
        return entity.get(key)
    return getattr(entity, key, None)
