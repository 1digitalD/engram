"""Engram v4 system API."""

from api import api_v4_bp
from api.v4._shared import *


REVIEW_METRICS_KEY = "review_metrics"
REVIEW_METRICS_MAX_EVENTS = 200


def _review_metrics_events():
    raw = _get_app_setting(REVIEW_METRICS_KEY) or {}
    events = raw.get("events") if isinstance(raw, dict) else []
    return events if isinstance(events, list) else []


def _parse_review_completed_at(value):
    try:
        return _parse_datetime(value)
    except Exception:
        return None


def _review_metrics_summary(days):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    events = []
    for event in _review_metrics_events():
        if not isinstance(event, dict):
            continue
        completed_at = _parse_review_completed_at(event.get("completed_at"))
        duration_ms = event.get("duration_ms")
        if completed_at is None or completed_at < since:
            continue
        if not isinstance(duration_ms, int) or duration_ms < 0:
            continue
        events.append({**event, "completed_at": completed_at, "duration_ms": duration_ms})

    durations = sorted(event["duration_ms"] for event in events)
    median_duration_ms = None
    if durations:
        midpoint = len(durations) // 2
        if len(durations) % 2:
            median_duration_ms = durations[midpoint]
        else:
            median_duration_ms = round((durations[midpoint - 1] + durations[midpoint]) / 2)

    return {
        "completed_reports": len(events),
        "median_duration_ms": median_duration_ms,
        "median_duration_seconds": round(median_duration_ms / 1000, 1)
        if median_duration_ms is not None
        else None,
        "total_duration_ms": sum(durations),
        "last_completed_at": _iso(max((event["completed_at"] for event in events), default=None)),
    }


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
    review = _review_metrics_summary(days)

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
        "review": review,
        "weekly": weekly,
    })


@api_v4_bp.route("/metrics/trust/review", methods=["POST"])
def record_review_metrics():
    """Record one completed v6 review session duration."""
    data = request.get_json(silent=True) or {}
    duration_ms = data.get("duration_ms")
    report_id = _clean_text(data.get("report_id"))

    if not isinstance(duration_ms, int):
        return _error("duration_ms must be an integer")
    if duration_ms < 0:
        return _error("duration_ms must be >= 0")

    completed_at = datetime.now(timezone.utc)
    event = {
        "report_id": report_id,
        "duration_ms": duration_ms,
        "completed_at": completed_at.isoformat(),
    }

    suggestion_count = data.get("suggestion_count")
    if isinstance(suggestion_count, int) and suggestion_count >= 0:
        event["suggestion_count"] = suggestion_count

    setting = _app_setting_row(REVIEW_METRICS_KEY)
    value = setting.value if isinstance(setting.value, dict) else {}
    events = value.get("events") if isinstance(value.get("events"), list) else []
    events.append(event)
    setting.value = {"events": events[-REVIEW_METRICS_MAX_EVENTS:]}
    flag_modified(setting, "value")
    db.session.commit()

    return jsonify({"data": event}), 201


@api_v4_bp.route("/settings/operator", methods=["GET"])
def get_operator_setting():
    """Return the configured operator person identity.

    If `operator_person_id` has never been persisted, backfill the response
    from the legacy `owner_person_id` setting when present. The backfill is
    read-only: it is not written to `operator_person_id` until a PUT persists
    it explicitly.
    """
    operator_id = _clean_text(_get_app_setting("operator_person_id"))
    configured = operator_id is not None

    if operator_id is None:
        operator_id = _clean_text(_get_app_setting("owner_person_id"))

    return jsonify({"operator_person_id": operator_id, "configured": configured})


@api_v4_bp.route("/settings/operator", methods=["PUT"])
def put_operator_setting():
    """Persist the operator person identity.

    Body: { operator_person_id: <person entity id> }
    """
    data = request.get_json(silent=True) or {}
    person_id = _clean_text(data.get("operator_person_id"))
    if person_id is None:
        return _error("operator_person_id is required")

    person = db.session.get(Entity, person_id)
    if person is None or person.type != "person":
        return _error("operator_person_id must reference an existing person entity")

    setting = _app_setting_row("operator_person_id")
    setting.value = person_id
    flag_modified(setting, "value")
    db.session.commit()

    return jsonify({"operator_person_id": person_id, "configured": True})


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

