"""Engram v4 insights API."""

from api import api_v4_bp
from api import v4_entities as _v4e
from api.v4._shared import *

@api_v4_bp.route("/brief", methods=["GET"])
def daily_brief():
    """Ranked daily brief: what deserves attention today, with reasons."""
    from services.v4_brief import get_brief

    force = request.args.get("force") in ("1", "true")
    brief, from_cache = get_brief(force=force)
    if brief is None:
        return jsonify({"brief": None, "from_cache": False, "reason": "generation unavailable"})
    return jsonify({"brief": brief, "from_cache": from_cache})


@api_v4_bp.route("/timeline", methods=["GET"])
def timeline():
    """Chronological event stream across all entities.

    Returns a descending-ordered list of entity_events with narration and a
    derived thread_id (parent project, assigned person, or the entity itself).
    """
    limit = max(1, min(request.args.get("limit", 50, type=int), 200))
    offset = max(0, request.args.get("offset", 0, type=int))

    from_dt, from_err = _parse_datetime_or_error(request.args.get("from"))
    if from_err:
        return from_err
    to_dt, to_err = _parse_datetime_or_error(request.args.get("to"))
    if to_err:
        return to_err
    thread_id = request.args.get("thread_id")
    actor = request.args.get("actor")
    entity_type = request.args.get("entity_type")

    if entity_type and entity_type not in ENTITY_TYPES:
        return _error(f"invalid entity type: {entity_type}")

    query = (
        db.session.query(EntityEvent, Entity.type)
        .join(Entity, Entity.id == EntityEvent.entity_id)
        .filter(Entity.lifecycle != "deleted")
    )

    if from_dt:
        query = query.filter(EntityEvent.created_at >= from_dt)
    if to_dt:
        query = query.filter(EntityEvent.created_at <= to_dt)
    if actor:
        if actor.endswith(":"):
            escaped_actor = actor.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = query.filter(EntityEvent.actor.like(f"{escaped_actor}%", escape="\\"))
        else:
            query = query.filter(EntityEvent.actor == actor)
    if entity_type:
        query = query.filter(Entity.type == entity_type)
    if thread_id:
        entity_ids = _timeline_thread_entity_ids(thread_id)
        if not entity_ids:
            return jsonify({"events": [], "next_offset": None})
        query = query.filter(EntityEvent.entity_id.in_(entity_ids))

    rows = (
        query.order_by(EntityEvent.created_at.desc(), EntityEvent.id.desc())
        .offset(offset)
        .limit(limit + 1)
        .all()
    )

    has_more = len(rows) > limit
    rows = rows[:limit]

    entity_ids_in_page = {event.entity_id for event, _ in rows}
    thread_map = _timeline_thread_map(entity_ids_in_page)

    events = []
    for event, entity_type in rows:
        event_dict = event.to_dict()
        event_dict["entity_type"] = entity_type
        event_dict["occurred_at"] = event_dict["created_at"]
        event_dict["thread_id"] = thread_map.get(event.entity_id, event.entity_id)
        event_dict["narration"] = narrate_event(event)
        events.append(event_dict)

    return jsonify({
        "events": events,
        "next_offset": offset + len(events) if has_more else None,
    })


@api_v4_bp.route("/summary", methods=["GET"])
def summary():
    now = datetime.now(timezone.utc)
    today_payload = _build_today_payload(now)
    return jsonify({
        "inbox_count": _needs_review_count(),
        "today_count": today_attention_count(today_payload),
        "suggestions_count": _pending_suggestions_count(),
    "threads_count": len(_all_threads_payload(now)),
        "last_reviewed_at": today_payload["last_reviewed_at"],
        "reviewed_today": today_payload["reviewed_today"],
        "stale_projects_count": (
            len(today_payload["stale_projects"]) + len(today_payload["suggested_archival"])
        ),
        "new_since_yesterday_count": today_payload["new_since_yesterday_count"],
        "coordination_radar": _coordination_radar(now),
    })


@api_v4_bp.route("/threads", methods=["GET"])
def threads():
    rank = request.args.get("rank", "attention")
    if rank != "attention":
        return _error("unsupported rank; only 'attention' is supported", 400)
    limit = max(1, min(request.args.get("limit", 20, type=int), 200))
    now = datetime.now(timezone.utc)
    all_threads = _all_threads_payload(now)
    return jsonify({"threads": all_threads[:limit], "total_count": len(all_threads)})


def _all_threads_payload(now):
    threads = _people_threads(now) + _project_threads(now) + _v4e._topic_threads(now, limit=None)
    threads.sort(key=lambda thread: thread["attention_score"], reverse=True)
    return threads


