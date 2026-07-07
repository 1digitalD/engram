"""Engram v4 system API."""

from api import api_v4_bp
from api import v4_entities as _v4e
from api.v4._shared import *

@api_v4_bp.route("/health", methods=["GET"])
def health():
    database_ready, database_reason = runtime_health.probe_database_connection()
    current_app.config["DATABASE_READY"] = database_ready
    current_app.config["DATABASE_UNAVAILABLE_REASON"] = database_reason
    if not database_ready:
        return jsonify(runtime_health.backend_unavailable_payload(database_reason)), 503
    return jsonify({"status": "ok", "api": "v4", "database": "ok"})


@api_v4_bp.route("/metrics/trust", methods=["GET"])
def trust_metrics():
    """Aggregate how much the agent's work is being accepted vs corrected.

    The product goal is "surface what matters without looking hard"; every
    dismissal, revert, merge, or quick archive of agent output is the user
    paying a correction tax. This endpoint turns the existing audit trail
    into that signal — no extra instrumentation.
    """
    days = max(1, min(request.args.get("days", 30, type=int), 365))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Suggestion outcomes (resolution within window; pending = current backlog).
    resolved = (
        db.session.query(AiSuggestion.status, func.count())
        .filter(AiSuggestion.resolved_at.isnot(None), AiSuggestion.resolved_at >= since)
        .group_by(AiSuggestion.status)
        .all()
    )
    suggestion_counts = {status: count for status, count in resolved}
    accepted = suggestion_counts.get("accepted", 0)
    dismissed = suggestion_counts.get("dismissed", 0)
    expired = suggestion_counts.get("expired", 0)
    decided = accepted + dismissed
    pending = AiSuggestion.query.filter_by(status="pending").count()
    oldest_pending = (
        db.session.query(func.min(AiSuggestion.created_at))
        .filter(AiSuggestion.status == "pending")
        .scalar()
    )

    # Agent action volume in window.
    agent_rows = (
        db.session.query(EntityEvent.event_type, func.count())
        .filter(EntityEvent.actor.like("agent:%"), EntityEvent.created_at >= since)
        .group_by(EntityEvent.event_type)
        .all()
    )
    agent_by_type = {event_type: count for event_type, count in agent_rows}
    agent_total = sum(agent_by_type.values())

    # Corrections: the user undoing or repairing agent output.
    reverts = (
        EntityEvent.query
        .filter(EntityEvent.event_type == "reverted", EntityEvent.created_at >= since)
        .count()
    )
    merges = (
        EntityEvent.query
        .filter(EntityEvent.event_type == "merged", EntityEvent.created_at >= since)
        .count()
    )
    # Quick kills: user archives/deletes within the window of entities the
    # agent created — the clearest "this shouldn't exist" signal.
    agent_created_ids = (
        db.session.query(EntityEvent.entity_id)
        .filter(EntityEvent.event_type == "created", EntityEvent.actor.like("agent:%"))
        .subquery()
    )
    quick_kills = (
        EntityEvent.query
        .filter(
            EntityEvent.event_type.in_(["archived", "deleted"]),
            EntityEvent.actor == "user",
            EntityEvent.created_at >= since,
            EntityEvent.entity_id.in_(db.session.query(agent_created_ids.c.entity_id)),
        )
        .count()
    )
    corrections_total = reverts + merges + dismissed + quick_kills

    # Weekly trend of agent actions vs corrections.
    week = func.date_trunc("week", EntityEvent.created_at)
    weekly_agent = dict(
        db.session.query(week, func.count())
        .filter(EntityEvent.actor.like("agent:%"), EntityEvent.created_at >= since)
        .group_by(week)
        .all()
    )
    weekly_corrections = dict(
        db.session.query(week, func.count())
        .filter(EntityEvent.event_type.in_(["reverted", "merged"]), EntityEvent.created_at >= since)
        .group_by(week)
        .all()
    )
    weeks = sorted(set(weekly_agent) | set(weekly_corrections))
    weekly = [
        {
            "week_start": w.date().isoformat() if hasattr(w, "date") else str(w),
            "agent_actions": weekly_agent.get(w, 0),
            "corrections": weekly_corrections.get(w, 0),
        }
        for w in weeks
    ]

    return jsonify({
        "window_days": days,
        "suggestions": {
            "accepted": accepted,
            "dismissed": dismissed,
            "expired": expired,
            "pending": pending,
            "acceptance_rate": round(accepted / decided, 3) if decided else None,
            "oldest_pending_at": _iso(oldest_pending),
        },
        "agent_actions": {"total": agent_total, "by_type": agent_by_type},
        "corrections": {
            "total": corrections_total,
            "reverts": reverts,
            "merges": merges,
            "dismissals": dismissed,
            "quick_kills": quick_kills,
        },
        "correction_rate": round(corrections_total / agent_total, 3) if agent_total else None,
        "weekly": weekly,
    })


@api_v4_bp.route("/agent-activity", methods=["GET"])
def agent_activity():
    limit = max(1, min(request.args.get("limit", 50, type=int), 200))
    events = (
        EntityEvent.query.options(selectinload(EntityEvent.entity))
        .filter(EntityEvent.actor.like("agent:%"))
        .order_by(EntityEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    suggestions = (
        AiSuggestion.query.options(selectinload(AiSuggestion.source_entity))
        .filter(AiSuggestion.status == "pending")
        .order_by(AiSuggestion.created_at.desc())
        .limit(limit)
        .all()
    )
    failed_notes = (
        Entity.query.filter(Entity.type == "note", Entity.lifecycle == "active", Entity.ai_status == "failed")
        .order_by(Entity.updated_at.desc(), Entity.created_at.desc())
        .limit(limit)
        .all()
    )

    items = (
        [_agent_event_item(event) for event in events]
        + [_agent_suggestion_item(suggestion) for suggestion in suggestions]
        + [_agent_failed_note_item(note) for note in failed_notes]
    )
    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    items = items[:limit]

    counts = {}
    for item in items:
        counts[item["category"]] = counts.get(item["category"], 0) + 1

    return jsonify({"data": items, "meta": {"total": len(items), "limit": limit, "counts": counts}})


