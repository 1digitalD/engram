"""Engram v4 canonical entity API."""

from datetime import datetime, time, timezone, timedelta
import hashlib
import json
import re

from flask import current_app, jsonify, request
from sqlalchemy import func, or_
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import selectinload

from api import api_v4_bp
from extensions import db
from models import AiSuggestion, AppSetting, Entity, EntityEvent, EntityLink, EntityTag, Job, Tag, _iso
from services import runtime_health
from services.v4_attention import attention_for_entity, today_attention_count, today_attention_items
from services.title_utils import title_or_placeholder

STATUS_BY_TYPE = {
    "note": ["active", "processed", "archived"],
    "task": ["open", "in_progress", "waiting", "blocked", "done", "cancelled"],
    "project": ["active", "on_hold", "completed", "cancelled"],
    "area": ["active", "archived"],
    "person": ["active", "archived"],
    "resource": ["active", "archived"],
}

ENTITY_TYPES = {"note", "task", "project", "area", "resource", "person"}
PRIORITY_LEVELS = {"low", "medium", "high", "urgent"}
PRIORITY_ORDER = {"low": 1, "medium": 2, "high": 3, "urgent": 4}
DEFAULT_STATUS = {
    "note": "active",
    "task": "open",
    "project": "active",
    "area": "active",
    "resource": "active",
    "person": "active",
}
VALID_STATUS = {
    "note": {"active", "processed", "archived"},
    "task": {"open", "in_progress", "waiting", "blocked", "done", "cancelled"},
    "project": {"active", "on_hold", "completed", "cancelled"},
    "area": {"active", "archived"},
    "resource": {"active", "archived"},
    "person": {"active", "archived"},
}
VALID_LIFECYCLE = {"active", "archived", "deleted"}
WRITABLE_FIELDS = {
    "title",
    "content",
    "status",
    "lifecycle",
    "due_at",
    "follow_up_at",
    "source",
    "reference_url",
    "properties",
}
RELATIONSHIP_PROPERTY_KEYS = {
    f"{prefix}{suffix}"
    for prefix in ("project", "area", "person", "note", "source_note", "parent")
    for suffix in ("_id", "_ids")
}
RELATIONSHIP_TYPES = {
    "parent",
    "related",
    "derived_from",
    "mentions",
    "assigned_to",
    "references",
    "blocks",
    "activity_update",
}
DEFAULT_OWNER_ALIASES = ["dan"]
DEFAULT_DELEGATION_CADENCE_DAYS = 3
AUTO_APPLY_CONFIDENCE = 0.8
AUTO_CREATE_ENTITY_CONFIDENCE = 0.9
RISKY_ENTITY_CREATION_TYPES = {"task", "project", "area", "resource", "person"}
# Types that must never be auto-created from capture — always reviewed.
SUGGEST_ONLY_CREATION_TYPES = {"project", "area", "task"}
# Reconciliation similarity at or above which a "new" decision is treated as
# a potential duplicate and routed to the review queue instead of auto-created.
NEAR_DUPLICATE_SCORE = 0.75
CAPTURE_INTENTS = {"update", "task_signal", "follow_up", "blocker", "delegation", "reference", "junk", "note"}
INBOX_INTENT_PRIORITY = {
    "blocker": 0,
    "follow_up": 1,
    "delegation": 2,
    "task_signal": 3,
    "update": 4,
    "reference": 5,
    "note": 6,
    "junk": 7,
}
INTENT_SUGGESTION_CONFIDENCE_FLOOR = 0.9
SUGGESTION_DUPLICATE_MEMORY_DAYS = 14
COMPACT_LINK_COUNT_RULES = {
    "person": {
        "notes": ("incoming", {"mentions"}, {"note"}),
        "tasks": ("incoming", {"assigned_to"}, {"task"}),
        "projects": ("both", {"assigned_to", "mentions", "related"}, {"project"}),
    },
    "area": {
        "notes": ("both", {"related", "mentions"}, {"note"}),
        "tasks": ("incoming", {"parent", "related"}, {"task"}),
        "projects": ("incoming", {"parent", "related"}, {"project"}),
    },
}


@api_v4_bp.route("/health", methods=["GET"])
def health():
    database_ready, database_reason = runtime_health.probe_database_connection()
    current_app.config["DATABASE_READY"] = database_ready
    current_app.config["DATABASE_UNAVAILABLE_REASON"] = database_reason
    if not database_ready:
        return jsonify(runtime_health.backend_unavailable_payload(database_reason)), 503
    return jsonify({"status": "ok", "api": "v4", "database": "ok"})


@api_v4_bp.route("/capture", methods=["POST"])
def capture():
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return _error("content is required")

    user_title = (data.get("title") or "").strip() or None
    existing = _find_duplicate_capture_note(content)
    if existing is not None:
        return jsonify({
            "source_note": existing.to_dict(),
            "applied_changes": [],
            "suggestions": [],
            "warnings": [],
            "skipped": True,
            "reason": "exact duplicate",
        })

    note = Entity(
        type="note",
        title=user_title or _title_from_content(content),
        content=content,
        status="active",
        lifecycle="active",
        source=data.get("source") or "quick_capture",
        properties={},
        ai_meta={"title_auto": user_title is None},
        ai_status="pending",
    )
    db.session.add(note)
    db.session.flush()
    _clear_review_resolution(note)
    _write_event(note, "created", new_value=note.to_dict())
    db.session.add(Job(job_type="embed", entity_id=note.id, payload={"entity_id": note.id, "reason": "capture"}))

    applied_changes = []
    suggestions = []
    warnings = []
    applied_changes.extend(_apply_explicit_mentions(note, content))
    try:
        result = _run_basic_capture_extraction(note, data.get("mode") or "auto")
        extraction_changes, extraction_suggestions = _reconcile_capture_candidates(note, result or {})
        applied_changes.extend(extraction_changes)
        suggestions.extend(extraction_suggestions)
    except Exception as exc:
        warnings.append(str(exc))
        note.ai_status = "failed"
        _apply_capture_intent(note, {})

    db.session.commit()
    return jsonify({
        "source_note": _load_entity(note.id).to_dict(),
        "applied_changes": applied_changes,
        "suggestions": suggestions,
        "warnings": warnings,
    }), 201


@api_v4_bp.route("/brief", methods=["GET"])
def daily_brief():
    """Ranked daily brief: what deserves attention today, with reasons."""
    from services.v4_brief import get_brief

    force = request.args.get("force") in ("1", "true")
    brief, from_cache = get_brief(force=force)
    if brief is None:
        return jsonify({"brief": None, "from_cache": False, "reason": "generation unavailable"})
    return jsonify({"brief": brief, "from_cache": from_cache})


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


@api_v4_bp.route("/entities", methods=["GET"])
def list_entities():
    query = _entity_query()
    entity_type = request.args.get("type")
    status_values = request.args.getlist("status")
    lifecycle = request.args.get("lifecycle")
    limit = max(1, min(request.args.get("limit", 50, type=int), 200))

    if entity_type:
        if entity_type not in ENTITY_TYPES:
            return _error(f"invalid entity type: {entity_type}")
        query = query.filter(Entity.type == entity_type)
    if status_values:
        valid_statuses = set(STATUS_BY_TYPE.get(entity_type, []))
        filtered = [s for s in status_values if s in valid_statuses]
        if filtered:
            query = query.filter(Entity.status.in_(filtered))
    if lifecycle:
        if lifecycle not in VALID_LIFECYCLE:
            return _error(f"invalid lifecycle: {lifecycle}")
        query = query.filter(Entity.lifecycle == lifecycle)
    else:
        query = query.filter(Entity.lifecycle != "deleted")

    rows = query.order_by(Entity.updated_at.desc(), Entity.created_at.desc()).limit(limit).all()
    _attach_project_task_counts(rows)
    _attach_task_context(rows)
    _attach_compact_link_counts(rows)
    return jsonify({"data": [row.to_dict() for row in rows]})


# Path segment used for each entity type, e.g. /tasks/<id>, /people/<id>.
ENTITY_TYPE_PLURAL = {t: ("people" if t == "person" else f"{t}s") for t in ENTITY_TYPES}
ENTITY_TYPE_BY_PLURAL = {plural: t for t, plural in ENTITY_TYPE_PLURAL.items()}

MENTION_TYPES_PER_GROUP = 5


@api_v4_bp.route("/entities/mentions", methods=["GET"])
def entity_mentions():
    """Lightweight, fast lookup for inline @-mention / [[link]] pickers.

    Returns active entities grouped by type, title-matching `q` (or most
    recently updated if `q` is empty), so the editor can show a live list
    while the user is still typing.
    """
    q = (request.args.get("q") or "").strip()
    limit_per_type = max(1, min(request.args.get("limit", MENTION_TYPES_PER_GROUP, type=int), 20))
    types_param = request.args.get("types")
    types = [t for t in (types_param.split(",") if types_param else ENTITY_TYPES) if t in ENTITY_TYPES]

    results = {}
    for entity_type in types:
        query = Entity.query.filter(Entity.type == entity_type, Entity.lifecycle == "active")
        if q:
            query = query.filter(Entity.title.ilike(f"%{q}%"))
        rows = query.order_by(Entity.updated_at.desc()).limit(limit_per_type).all()
        if rows:
            results[entity_type] = [
                {"id": row.id, "type": row.type, "title": row.title, "path": f"/{ENTITY_TYPE_PLURAL[row.type]}/{row.id}"}
                for row in rows
            ]
    return jsonify({"query": q, "results": results})


@api_v4_bp.route("/search", methods=["GET"])
def search():
    q = request.args.get("q", "").strip()
    tag = (request.args.get("tag") or "").strip().lower() or None
    if not q and not tag:
        return _error("either q or tag parameter is required")
    mode = request.args.get("mode", "hybrid")
    entity_type = request.args.get("type")
    status = request.args.get("status")
    lifecycle = request.args.get("lifecycle", "active")
    limit = request.args.get("limit", 20, type=int)

    if entity_type and entity_type not in ENTITY_TYPES:
        return _error(f"invalid entity type: {entity_type}")
    if lifecycle and lifecycle not in VALID_LIFECYCLE:
        return _error(f"invalid lifecycle: {lifecycle}")

    from services.v4_search import search_entities, list_by_tag
    if not q and tag:
        results = list_by_tag(
            tag,
            entity_type=entity_type,
            status=status,
            lifecycle=lifecycle,
            limit=limit,
        )
        return jsonify({"query": "", "tag": tag, "mode": "tag", "results": results})

    results = search_entities(
        q,
        mode=mode,
        entity_type=entity_type,
        status=status,
        lifecycle=lifecycle,
        limit=limit,
        tag=tag,
    )
    resolved_mode = mode if mode in {"keyword", "semantic", "hybrid"} else "hybrid"
    return jsonify({"query": q, "tag": tag, "mode": resolved_mode, "results": results})


DONE_TASK_STATUSES = {"done", "completed", "cancelled"}
OPEN_TASK_STATUSES = {"open", "in_progress", "waiting", "blocked"}
FOLLOW_UP_ENTITY_TYPES = {"task", "project"}

# Phase F (proactive monitoring): an active project with no activity update,
# event, or field change in this many days is "stale"; at the longer
# threshold, archival is suggested (never applied automatically).
STALE_PROJECT_DAYS = 14
ARCHIVAL_SUGGESTION_DAYS = 30
PERSON_PULSE_QUIET_DAYS = 7


@api_v4_bp.route("/today", methods=["GET"])
def today():
    return jsonify(_build_today_payload(datetime.now(timezone.utc)))


def _build_today_payload(now):
    start_of_today = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    end_of_today = datetime.combine(now.date(), time.max, tzinfo=timezone.utc)

    overdue = (
        _entity_query()
        .filter(
            Entity.lifecycle == "active",
            Entity.type.in_(FOLLOW_UP_ENTITY_TYPES),
            Entity.due_at.isnot(None),
            Entity.due_at < start_of_today,
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(Entity.due_at.asc())
        .limit(50)
        .all()
    )
    due_today = (
        _entity_query()
        .filter(
            Entity.lifecycle == "active",
            Entity.type.in_(FOLLOW_UP_ENTITY_TYPES),
            Entity.due_at.isnot(None),
            Entity.due_at >= start_of_today,
            Entity.due_at <= end_of_today,
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(Entity.due_at.asc())
        .limit(50)
        .all()
    )
    overdue_follow_ups = (
        _entity_query()
        .filter(
            Entity.lifecycle == "active",
            Entity.type.in_(FOLLOW_UP_ENTITY_TYPES),
            Entity.follow_up_at.isnot(None),
            Entity.follow_up_at < start_of_today,
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(Entity.follow_up_at.asc())
        .limit(50)
        .all()
    )
    follow_ups = (
        _entity_query()
        .filter(
            Entity.lifecycle == "active",
            Entity.type.in_(FOLLOW_UP_ENTITY_TYPES),
            Entity.follow_up_at.isnot(None),
            Entity.follow_up_at >= start_of_today,
            Entity.follow_up_at <= end_of_today,
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(Entity.follow_up_at.asc())
        .limit(50)
        .all()
    )
    end_of_week = end_of_today + timedelta(days=7)
    upcoming_follow_ups = (
        _entity_query()
        .filter(
            Entity.lifecycle == "active",
            Entity.type.in_(FOLLOW_UP_ENTITY_TYPES),
            Entity.follow_up_at.isnot(None),
            Entity.follow_up_at > end_of_today,
            Entity.follow_up_at <= end_of_week,
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(Entity.follow_up_at.asc())
        .limit(50)
        .all()
    )
    upcoming_due_tasks = (
        _entity_query()
        .filter(
            Entity.lifecycle == "active",
            Entity.type.in_(FOLLOW_UP_ENTITY_TYPES),
            Entity.due_at.isnot(None),
            Entity.due_at > end_of_today,
            Entity.due_at <= end_of_week,
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(Entity.due_at.asc())
        .limit(50)
        .all()
    )
    blocked_tasks = (
        _entity_query()
        .filter(Entity.type == "task", Entity.lifecycle == "active", Entity.status == "blocked")
        .order_by(Entity.updated_at.desc())
        .limit(50)
        .all()
    )
    waiting_tasks = (
        _entity_query()
        .filter(Entity.type == "task", Entity.lifecycle == "active", Entity.status == "waiting")
        .order_by(Entity.updated_at.desc())
        .limit(50)
        .all()
    )
    # Single query: which active projects have at least one open task parent-linked.
    projects_with_open_subquery = (
        db.session.query(EntityLink.target_entity_id)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "parent",
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
        )
        .distinct()
        .subquery()
    )
    projects_without_open_tasks = (
        _entity_query()
        .filter(
            Entity.type == "project",
            Entity.lifecycle == "active",
            Entity.status == "active",
            ~Entity.id.in_(db.session.query(projects_with_open_subquery.c.target_entity_id)),
        )
        .order_by(Entity.updated_at.desc())
        .limit(25)
        .all()
    )
    # Open tasks with no due/follow-up date of their own — invisible to the
    # date-based buckets above. Ranked by impact + staleness so neglected or
    # blocking work still surfaces.
    unscheduled_tasks = (
        _entity_query()
        .filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
            Entity.due_at.is_(None),
            Entity.follow_up_at.is_(None),
        )
        .order_by(Entity.updated_at.desc())
        .limit(100)
        .all()
    )

    delegations_quiet = _delegations_quiet(now)
    dependency_interventions = _today_dependency_interventions(now)

    active_projects = (
        _entity_query()
        .filter(Entity.type == "project", Entity.lifecycle == "active", Entity.status == "active")
        .all()
    )
    project_staleness = _project_staleness_days(active_projects, now)
    stale_projects = []
    suggested_archival = []
    for project in active_projects:
        days = project_staleness.get(project.id, 0)
        if days >= STALE_PROJECT_DAYS:
            entry = _entity_with_attention(project)
            entry["stale_days"] = days
            if days >= ARCHIVAL_SUGGESTION_DAYS:
                suggested_archival.append(entry)
            else:
                stale_projects.append(entry)
    stale_projects.sort(key=lambda item: item["stale_days"], reverse=True)
    suggested_archival.sort(key=lambda item: item["stale_days"], reverse=True)

    pending_suggestions = (
        AiSuggestion.query.filter_by(status="pending")
        .order_by(AiSuggestion.created_at.desc())
        .limit(25)
        .all()
    )
    recent_notes = (
        _entity_query()
        .filter(
            Entity.type == "note",
            Entity.lifecycle == "active",
            Entity.source != "activity_update",
        )
        .order_by(Entity.updated_at.desc(), Entity.created_at.desc())
        .limit(25)
        .all()
    )

    all_tasks = (
        overdue + due_today + overdue_follow_ups + follow_ups + upcoming_follow_ups
        + upcoming_due_tasks + blocked_tasks + waiting_tasks + unscheduled_tasks
    )
    inherited_priorities = _inherited_task_priorities(all_tasks)
    staleness_by_id = _staleness_days_for(all_tasks, now)
    impact_by_id = _blocking_impact_counts(all_tasks)
    _attach_task_context(all_tasks)

    def with_priority(entity, **kwargs):
        return _entity_with_attention(
            entity,
            inherited_priority=inherited_priorities.get(entity.id),
            staleness_days=staleness_by_id.get(entity.id),
            blocks_count=impact_by_id.get(entity.id, 0),
            **kwargs,
        )

    unscheduled_attention = sorted(
        (with_priority(entity) for entity in unscheduled_tasks),
        key=lambda item: item["attention"]["score"],
        reverse=True,
    )
    unscheduled_attention = [item for item in unscheduled_attention if item["attention"]["score"] > 0][:20]

    last_reviewed_at = _get_app_setting("last_reviewed_at")
    reviewed_today = bool(
        last_reviewed_at and _parse_datetime(last_reviewed_at) >= start_of_today
    )

    payload = {
        "overdue": [with_priority(entity) for entity in overdue],
        "due_today": [with_priority(entity) for entity in due_today],
        "overdue_follow_ups": [with_priority(entity) for entity in overdue_follow_ups],
        "follow_ups": [with_priority(entity) for entity in follow_ups],
        "upcoming_follow_ups": [with_priority(entity) for entity in upcoming_follow_ups],
        "upcoming_due_tasks": [with_priority(entity) for entity in upcoming_due_tasks],
        "blocked_tasks": [with_priority(entity) for entity in blocked_tasks],
        "waiting_tasks": [with_priority(entity) for entity in waiting_tasks],
        "unscheduled_attention_tasks": unscheduled_attention,
        "last_reviewed_at": last_reviewed_at,
        "reviewed_today": reviewed_today,
        "projects_without_open_tasks": [
            _entity_with_attention(entity, context=["project_without_open_tasks"])
            for entity in projects_without_open_tasks
        ],
        "recent_notes": [_entity_with_attention(entity) for entity in recent_notes],
        "delegations_quiet": delegations_quiet,
        "dependency_interventions": dependency_interventions,
        "stale_projects": stale_projects,
        "suggested_archival": suggested_archival,
        "pending_suggestions": [suggestion.to_dict() for suggestion in pending_suggestions],
        # Retained for any external callers; matches the new bucket structure semantically.
        "blocked_or_waiting_tasks": [with_priority(e) for e in (blocked_tasks + waiting_tasks)],
    }

    # Phase F (proactive monitoring): "N new items since yesterday" — items in
    # today's actionable set created within the last 24h, or since the last
    # day-review if that was more recent (so re-checking shortly after a
    # review doesn't re-surface the same items as "new").
    since_cutoff = now - timedelta(hours=24)
    if last_reviewed_at:
        reviewed_dt = _parse_datetime(last_reviewed_at)
        if reviewed_dt > since_cutoff:
            since_cutoff = reviewed_dt
    new_since_yesterday_count = sum(
        1
        for item in today_attention_items(payload)
        if item.get("created_at") and _parse_datetime(item["created_at"]) >= since_cutoff
    )
    payload["new_since_yesterday_count"] = new_since_yesterday_count

    return payload


@api_v4_bp.route("/today/review", methods=["POST"])
def mark_today_reviewed():
    now = datetime.now(timezone.utc)
    start_of_today = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    last_reviewed_at = _set_app_setting("last_reviewed_at", now.isoformat())
    return jsonify({
        "last_reviewed_at": last_reviewed_at,
        "reviewed_today": _parse_datetime(last_reviewed_at) >= start_of_today,
    })


def _needs_review_query():
    unresolved_review = or_(
        Entity.ai_meta["review_state"].as_string().is_(None),
        Entity.ai_meta["review_state"].as_string() != "resolved",
    )

    # Notes with pending AI suggestions linked to them.
    notes_with_suggestions = {
        row[0] for row in db.session.query(AiSuggestion.source_entity_id)
        .filter(AiSuggestion.status == "pending")
        .distinct().all()
    }

    return _entity_query().filter(
        Entity.type == "note",
        Entity.lifecycle == "active",
        unresolved_review,
        or_(
            Entity.ai_status == "pending",
            Entity.ai_status == "failed",
            Entity.id.in_(notes_with_suggestions) if notes_with_suggestions else Entity.id.is_(None),
        ),
    )


def _needs_review_count():
    return _needs_review_query().count()


@api_v4_bp.route("/summary", methods=["GET"])
def summary():
    now = datetime.now(timezone.utc)
    today_payload = _build_today_payload(now)
    return jsonify({
        "inbox_count": _needs_review_count(),
        "today_count": today_attention_count(today_payload),
        "suggestions_count": _needs_review_count(),
        "last_reviewed_at": today_payload["last_reviewed_at"],
        "reviewed_today": today_payload["reviewed_today"],
        "stale_projects_count": (
            len(today_payload["stale_projects"]) + len(today_payload["suggested_archival"])
        ),
        "new_since_yesterday_count": today_payload["new_since_yesterday_count"],
        "coordination_radar": _coordination_radar(now),
    })


@api_v4_bp.route("/inbox", methods=["GET"])
def inbox():
    limit = max(1, min(request.args.get("limit", 30, type=int), 200))

    needs_review = (
        _needs_review_query()
        .order_by(Entity.updated_at.desc(), Entity.created_at.desc())
        .all()
    )
    needs_review_ids = {n.id for n in needs_review}

    recent = (
        _entity_query()
        .filter(
            Entity.type == "note",
            Entity.lifecycle == "active",
            ~Entity.id.in_(needs_review_ids) if needs_review_ids else Entity.id.is_not(None),
        )
        .order_by(Entity.created_at.desc())
        .all()
    )

    # Single query: pending-suggestion counts per source note in this page.
    note_ids = [n.id for n in needs_review] + [n.id for n in recent]
    pending_counts = {}
    if note_ids:
        rows = (
            db.session.query(AiSuggestion.source_entity_id, func.count(AiSuggestion.id))
            .filter(AiSuggestion.source_entity_id.in_(note_ids), AiSuggestion.status == "pending")
            .group_by(AiSuggestion.source_entity_id)
            .all()
        )
        pending_counts = {sid: cnt for sid, cnt in rows}

    needs_review = _sort_inbox_notes(needs_review, pending_counts, mode="needs_review")[:limit]
    recent = _sort_inbox_notes(recent, pending_counts, mode="recent")[:limit]

    def annotate(note):
        d = note.to_dict()
        d["pending_suggestion_count"] = pending_counts.get(note.id, 0)
        d["attention"] = attention_for_entity(
            note,
            pending_suggestion_count=d["pending_suggestion_count"],
            context=["needs_review"] if note.id in needs_review_ids else None,
        )
        return d

    return jsonify({
        "needs_review": [annotate(n) for n in needs_review],
        "recent": [annotate(n) for n in recent],
    })


def _entity_with_attention(
    entity,
    *,
    pending_suggestion_count=0,
    context=None,
    inherited_priority=None,
    staleness_days=None,
    blocks_count=0,
):
    data = entity.to_dict()
    data["attention"] = attention_for_entity(
        entity,
        pending_suggestion_count=pending_suggestion_count,
        context=context,
        inherited_priority=inherited_priority,
        staleness_days=staleness_days,
        blocks_count=blocks_count,
    )
    if inherited_priority and not (entity.properties or {}).get("priority"):
        data["inherited_priority"] = inherited_priority
    return data


def _inherited_task_priorities(tasks):
    """Map task_id -> parent project's properties.priority, for tasks that
    have no priority of their own and a 'parent' project link. Batched."""
    candidates = [t for t in tasks if t.type == "task" and not (t.properties or {}).get("priority")]
    if not candidates:
        return {}
    task_ids = [t.id for t in candidates]
    rows = (
        db.session.query(EntityLink.source_entity_id, Entity.properties)
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.source_entity_id.in_(task_ids),
            EntityLink.relationship_type == "parent",
            Entity.type == "project",
        )
        .all()
    )
    result = {}
    for task_id, properties in rows:
        priority = (properties or {}).get("priority")
        if priority:
            result[task_id] = priority
    return result


def _staleness_days_for(entities, now):
    """Map entity_id -> days since its last activity (most recent
    activity-update note, falling back to updated_at). Batched (no N+1)."""
    if not entities:
        return {}
    entity_ids = [e.id for e in entities]
    latest_update = _latest_activity_updates(entity_ids)
    result = {}
    for entity in entities:
        last = latest_update.get(entity.id)
        reference = last[0] if last else entity.created_at
        if reference is None:
            continue
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        result[entity.id] = max(0, (now - reference).days)
    return result


def _project_staleness_days(entities, now):
    """Map entity_id -> days since the most recent of: an activity-update
    note, an EntityEvent, or any field change (`updated_at`). Batched."""
    if not entities:
        return {}
    entity_ids = [e.id for e in entities]
    latest_update = _latest_activity_updates(entity_ids)
    latest_event = _latest_event_at(entity_ids)
    result = {}
    for entity in entities:
        candidates = [entity.created_at]
        if entity.id in latest_update:
            candidates.append(latest_update[entity.id][0])
        if entity.id in latest_event:
            candidates.append(latest_event[entity.id])
        candidates = [c for c in candidates if c is not None]
        reference = max(candidates)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        result[entity.id] = max(0, (now - reference).days)
    return result


def _latest_event_at(entity_ids):
    """Map entity_id -> created_at of its most recent non-creation
    EntityEvent (the `created` event is already covered by `created_at`)."""
    if not entity_ids:
        return {}
    rows = (
        db.session.query(EntityEvent.entity_id, func.max(EntityEvent.created_at))
        .filter(EntityEvent.entity_id.in_(entity_ids), EntityEvent.event_type != "created")
        .group_by(EntityEvent.entity_id)
        .all()
    )
    return dict(rows)


def _blocking_impact_counts(entities):
    """Map entity_id -> count of other active, non-done entities it blocks
    (via a `blocks` relationship link). Batched (no N+1)."""
    if not entities:
        return {}
    entity_ids = [e.id for e in entities]
    rows = (
        db.session.query(EntityLink.source_entity_id, func.count(EntityLink.target_entity_id))
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.source_entity_id.in_(entity_ids),
            EntityLink.relationship_type == "blocks",
            Entity.lifecycle == "active",
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .group_by(EntityLink.source_entity_id)
        .all()
    )
    return {source_id: count for source_id, count in rows}


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


def _agent_event_item(event):
    entity = event.entity
    category = "review_action" if event.event_type in {"suggestion_accepted", "suggestion_dismissed"} else "auto_applied"
    return {
        "id": event.id,
        "kind": "event",
        "category": category,
        "event_type": event.event_type,
        "actor": event.actor,
        "entity": _audit_entity(entity),
        "confidence": event.confidence,
        "reason": event.reason,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _agent_suggestion_item(suggestion):
    return {
        "id": suggestion.id,
        "kind": "suggestion",
        "category": "suggested",
        "event_type": suggestion.suggestion_type,
        "actor": "agent:v4-capture",
        "entity": _audit_entity(suggestion.source_entity),
        "confidence": suggestion.confidence,
        "reason": suggestion.reason,
        "created_at": suggestion.created_at.isoformat() if suggestion.created_at else None,
    }


def _agent_failed_note_item(note):
    return {
        "id": f"failed:{note.id}",
        "kind": "failed_note",
        "category": "failed",
        "event_type": "ai_failed",
        "actor": "agent:v4-capture",
        "entity": _audit_entity(note),
        "confidence": None,
        "reason": "capture extraction failed",
        "created_at": note.updated_at.isoformat() if note.updated_at else None,
    }


def _audit_entity(entity):
    if entity is None:
        return None
    return {"id": entity.id, "type": entity.type, "title": entity.title}


def _clear_review_resolution(entity):
    ai_meta = dict(entity.ai_meta or {})
    changed = False
    for key in ("review_state", "reviewed_at", "review_resolution"):
        if key in ai_meta:
            ai_meta.pop(key, None)
            changed = True
    if changed:
        entity.ai_meta = ai_meta
        flag_modified(entity, "ai_meta")


def _mark_review_resolved(entity):
    ai_meta = dict(entity.ai_meta or {})
    ai_meta["review_state"] = "resolved"
    ai_meta["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    ai_meta["review_resolution"] = "no_change_needed"
    entity.ai_meta = ai_meta
    flag_modified(entity, "ai_meta")


@api_v4_bp.route("/recent", methods=["GET"])
def recent():
    query = _entity_query().filter(Entity.lifecycle == "active")
    entity_type = request.args.get("type")
    limit = max(1, min(request.args.get("limit", 20, type=int), 100))

    if entity_type:
        if entity_type not in ENTITY_TYPES:
            return _error(f"invalid entity type: {entity_type}")
        query = query.filter(Entity.type == entity_type)

    rows = query.order_by(Entity.updated_at.desc(), Entity.created_at.desc()).limit(limit).all()
    return jsonify({"data": [row.to_dict() for row in rows]})


@api_v4_bp.route("/entities", methods=["POST"])
def create_entity():
    data = request.get_json(silent=True) or {}
    entity_type = data.get("type")
    if entity_type not in ENTITY_TYPES:
        return _error("type must be one of: " + ", ".join(sorted(ENTITY_TYPES)))

    status = data.get("status") or DEFAULT_STATUS[entity_type]
    validation_error = _validate_status(entity_type, status)
    if validation_error:
        return validation_error

    properties = data.get("properties") or {}
    properties_error = _validate_properties(properties)
    if properties_error:
        return properties_error

    follow_up_at, follow_up_error = _parse_datetime_or_error(data.get("follow_up_at"))
    if follow_up_error:
        return follow_up_error
    due_at, due_error = _parse_datetime_or_error(data.get("due_at"))
    if due_error:
        return due_error

    entity = Entity(
        type=entity_type,
        title=data.get("title"),
        content=data.get("content"),
        status=status,
        lifecycle=data.get("lifecycle") or "active",
        due_at=due_at,
        follow_up_at=follow_up_at,
        source=data.get("source") or "manual",
        reference_url=data.get("reference_url"),
        properties=properties,
        ai_meta=data.get("ai_meta") or {},
        ai_status=data.get("ai_status") or "pending",
    )
    lifecycle_error = _validate_lifecycle(entity.lifecycle)
    if lifecycle_error:
        return lifecycle_error

    db.session.add(entity)
    db.session.flush()
    _replace_tags(entity, data.get("tags", []))
    _write_event(entity, "created", new_value=entity.to_dict())
    _queue_embed_job(entity.id, "entity_create")
    db.session.commit()

    return jsonify({"data": _load_entity(entity.id).to_dict()}), 201


@api_v4_bp.route("/entities/<entity_id>", methods=["GET"])
def get_entity(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    return jsonify({"data": entity.to_dict()})


@api_v4_bp.route("/entities/<entity_id>/detail", methods=["GET"])
def get_entity_detail(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    entity_data = entity.to_dict()
    if entity.type == "person":
        entity_data["is_owner"] = _is_owner(entity.title, entity.id)
    detail = {"entity": entity_data, "sections": _relationship_detail_sections(entity)}
    if entity.type == "person":
        tasks = _person_open_tasks(entity)
        latest_update = _latest_activity_updates([task.id for task in tasks])
        pulse = _person_pulse(tasks, latest_update)
        detail["current_load"] = _person_current_load(tasks, latest_update)
        detail["pulse"] = pulse
        detail["dependency_watch"] = _task_dependency_watch(tasks, latest_update)
        detail["meeting_prep"] = _person_meeting_prep(entity, tasks, latest_update, pulse)
    if entity.type == "project":
        tasks = _project_open_tasks(entity)
        latest_update = _latest_activity_updates([task.id for task in tasks])
        detail["project_pulse"] = _project_pulse(tasks, latest_update)
        detail["dependency_watch"] = _task_dependency_watch(tasks, latest_update)
    return jsonify(detail)


@api_v4_bp.route("/entities/<entity_id>/owner", methods=["POST"])
def set_owner_person(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    if entity.type != "person":
        return _error("owner identity must reference a person")

    previous_owner_id = _owner_person_id()
    previous_owner = db.session.get(Entity, previous_owner_id) if previous_owner_id else None
    setting = _app_setting_row("owner_person_id")
    setting.value = entity.id
    flag_modified(setting, "value")
    _record_owner_identity_change(previous_owner, entity)
    db.session.commit()
    return jsonify({"data": {"owner_person_id": entity.id, "is_owner": True}})


@api_v4_bp.route("/entities/<entity_id>/owner", methods=["DELETE"])
def clear_owner_person(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    if entity.type != "person":
        return _error("owner identity must reference a person")

    previous_owner_id = _owner_person_id()
    previous_owner = db.session.get(Entity, previous_owner_id) if previous_owner_id else None
    setting = _app_setting_row("owner_person_id")
    setting.value = None
    flag_modified(setting, "value")
    _record_owner_identity_change(previous_owner, None)
    db.session.commit()
    return jsonify({"data": {"owner_person_id": None, "is_owner": False}})


@api_v4_bp.route("/entities/<entity_id>", methods=["PATCH"])
def update_entity(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)

    data = request.get_json(silent=True) or {}
    unknown = set(data) - WRITABLE_FIELDS - {"tags"}
    if unknown:
        return _error("unsupported fields: " + ", ".join(sorted(unknown)))

    old_snapshot = entity.to_dict()
    status_changed = False
    archived = False

    if "status" in data:
        validation_error = _validate_status(entity.type, data["status"])
        if validation_error:
            return validation_error
        status_changed = data["status"] != entity.status
        entity.status = data["status"]

    if "lifecycle" in data:
        lifecycle_error = _validate_lifecycle(data["lifecycle"])
        if lifecycle_error:
            return lifecycle_error
        archived = data["lifecycle"] == "archived" and entity.lifecycle != "archived"
        entity.lifecycle = data["lifecycle"]

    if "properties" in data:
        properties = data.get("properties") or {}
        properties_error = _validate_properties(properties)
        if properties_error:
            return properties_error
        entity.properties = properties

    for field in ("title", "content", "source", "reference_url"):
        if field in data:
            setattr(entity, field, data[field])
    if "title" in data and entity.type == "note" and (entity.ai_meta or {}).get("title_auto"):
        ai_meta = dict(entity.ai_meta or {})
        ai_meta["title_auto"] = False
        entity.ai_meta = ai_meta
        flag_modified(entity, "ai_meta")
    if "follow_up_at" in data:
        follow_up_at, follow_up_error = _parse_datetime_or_error(data["follow_up_at"])
        if follow_up_error:
            return follow_up_error
        entity.follow_up_at = follow_up_at
    if "due_at" in data:
        due_at, due_error = _parse_datetime_or_error(data["due_at"])
        if due_error:
            return due_error
        entity.due_at = due_at
    if "tags" in data:
        _replace_tags(entity, data.get("tags") or [])

    db.session.flush()
    new_snapshot = entity.to_dict()
    _write_event(entity, "updated", old_value=old_snapshot, new_value=new_snapshot)
    if status_changed:
        _write_event(
            entity,
            "status_changed",
            old_value={"status": old_snapshot["status"]},
            new_value={"status": entity.status},
        )
    if archived:
        _archive_incoming_activity_updates(entity)
        _write_event(
            entity,
            "archived",
            old_value={"lifecycle": old_snapshot["lifecycle"]},
            new_value={"lifecycle": entity.lifecycle},
        )
    _queue_embed_job(entity.id, "entity_update")

    # When a task is updated, propagate updated_at to its parent projects
    if entity.type == "task":
        _touch_parent_projects(entity)

    db.session.commit()

    return jsonify({"data": _load_entity(entity.id).to_dict()})


@api_v4_bp.route("/entities/<entity_id>", methods=["DELETE"])
def delete_entity(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)

    old_snapshot = entity.to_dict()
    entity.lifecycle = "deleted"
    db.session.flush()
    _delete_incoming_activity_updates(entity)
    _write_event(
        entity,
        "deleted",
        old_value={"lifecycle": old_snapshot["lifecycle"]},
        new_value={"lifecycle": "deleted"},
    )
    db.session.commit()

    return jsonify({"data": _load_entity(entity.id).to_dict()})


@api_v4_bp.route("/entities/<entity_id>/merge", methods=["POST"])
def merge_entity(entity_id):
    """Merge this entity (the duplicate) into another entity (the survivor).

    The duplicate is tombstoned (lifecycle="deleted", properties.merged_into)
    rather than removed: its events stay attached, and undo is a state flip.
    Everything that referenced the duplicate is re-pointed at the survivor.
    """
    loser = _load_entity(entity_id)
    if loser is None:
        return _error("entity not found", 404)

    data = request.get_json(silent=True) or {}
    survivor_id = data.get("target_id")
    if not survivor_id:
        return _error("target_id is required")
    if survivor_id == entity_id:
        return _error("cannot merge an entity into itself")

    survivor = _load_entity(survivor_id)
    if survivor is None:
        return _error("target entity not found", 404)
    if loser.type != survivor.type:
        return _error(f"cannot merge {loser.type} into {survivor.type}: types must match")
    if loser.lifecycle == "deleted":
        return _error("entity is already deleted or merged")
    if survivor.lifecycle == "deleted":
        return _error("target entity is deleted")

    summary = _merge_entities(loser, survivor, actor="user")
    db.session.commit()

    return jsonify({"data": _load_entity(survivor.id).to_dict(), "merge": summary})


def _merge_entities(loser, survivor, actor="user"):
    """Re-point all references from loser to survivor and tombstone the loser.

    Returns a summary dict of what moved. Caller commits.
    """
    loser_snapshot = loser.to_dict()
    links_moved = 0
    links_dropped = 0

    # Re-point links in both directions. Links that would become self-links
    # or duplicate an existing survivor link are dropped (the survivor
    # relationship already exists or is meaningless).
    for link in EntityLink.query.filter_by(source_entity_id=loser.id).all():
        if link.target_entity_id == survivor.id or EntityLink.query.filter_by(
            source_entity_id=survivor.id,
            target_entity_id=link.target_entity_id,
            relationship_type=link.relationship_type,
        ).first():
            db.session.delete(link)
            links_dropped += 1
        else:
            link.source_entity_id = survivor.id
            links_moved += 1
    db.session.flush()
    for link in EntityLink.query.filter_by(target_entity_id=loser.id).all():
        if link.source_entity_id == survivor.id or EntityLink.query.filter_by(
            source_entity_id=link.source_entity_id,
            target_entity_id=survivor.id,
            relationship_type=link.relationship_type,
        ).first():
            db.session.delete(link)
            links_dropped += 1
        else:
            link.target_entity_id = survivor.id
            links_moved += 1
    db.session.flush()

    # Tags: union onto the survivor.
    survivor_tag_ids = {et.tag_id for et in EntityTag.query.filter_by(entity_id=survivor.id).all()}
    tags_moved = 0
    for entity_tag in EntityTag.query.filter_by(entity_id=loser.id).all():
        tag_id = entity_tag.tag_id
        db.session.delete(entity_tag)
        if tag_id not in survivor_tag_ids:
            db.session.add(EntityTag(entity_id=survivor.id, tag_id=tag_id))
            tags_moved += 1
    db.session.flush()

    # Pending suggestions and jobs that reference the loser follow the survivor.
    for suggestion in AiSuggestion.query.filter_by(status="pending").all():
        changed = False
        if suggestion.source_entity_id == loser.id:
            suggestion.source_entity_id = survivor.id
            changed = True
        payload = dict(suggestion.payload or {})
        for key in ("target_entity_id", "source_entity_id"):
            if payload.get(key) == loser.id:
                payload[key] = survivor.id
                changed = True
        if changed:
            suggestion.payload = payload
            flag_modified(suggestion, "payload")
    for job in Job.query.filter_by(entity_id=loser.id, status="pending").all():
        job.entity_id = survivor.id
        payload = dict(job.payload or {})
        if payload.get("entity_id") == loser.id:
            payload["entity_id"] = survivor.id
            job.payload = payload
            flag_modified(job, "payload")

    # Backfill scalar fields the survivor is missing — never overwrite.
    fields_copied = []
    for field in ("content", "due_at", "follow_up_at", "reference_url"):
        if not getattr(survivor, field, None) and getattr(loser, field, None):
            setattr(survivor, field, getattr(loser, field))
            fields_copied.append(field)

    # The loser must stop matching future captures: drop its chunks and
    # tombstone it. All read paths already exclude lifecycle="deleted".
    from models import EntityChunk
    EntityChunk.query.filter_by(entity_id=loser.id).delete()
    loser.lifecycle = "deleted"
    properties = dict(loser.properties or {})
    properties["merged_into"] = survivor.id
    loser.properties = properties
    flag_modified(loser, "properties")

    survivor.updated_at = datetime.now(timezone.utc)

    summary = {
        "merged_from_id": loser.id,
        "merged_into_id": survivor.id,
        "links_moved": links_moved,
        "links_dropped": links_dropped,
        "tags_moved": tags_moved,
        "fields_copied": fields_copied,
    }
    _write_event(
        survivor,
        "merged",
        old_value={"merged_from": loser_snapshot},
        new_value=summary,
        actor=actor,
        reason=f"merged duplicate '{loser_snapshot.get('title')}'",
    )
    _write_event(
        loser,
        "merged_into",
        old_value={"lifecycle": loser_snapshot["lifecycle"]},
        new_value={"lifecycle": "deleted", "merged_into": survivor.id},
        actor=actor,
    )
    _queue_embed_job(survivor.id, "entity_merge")
    return summary


TYPE_CONVERSIONS = {("project", "task"), ("task", "project")}
CONVERSION_STATUS_MAP = {
    ("project", "task"): {"active": "open", "on_hold": "waiting", "completed": "done", "cancelled": "cancelled"},
    ("task", "project"): {"open": "active", "in_progress": "active", "waiting": "on_hold", "blocked": "on_hold", "done": "completed", "cancelled": "cancelled"},
}


@api_v4_bp.route("/entities/<entity_id>/convert", methods=["POST"])
def convert_entity(entity_id):
    """Convert an entity between project and task (granularity repair)."""
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    if entity.lifecycle == "deleted":
        return _error("entity is deleted")

    data = request.get_json(silent=True) or {}
    new_type = data.get("type")
    if (entity.type, new_type) not in TYPE_CONVERSIONS:
        supported = ", ".join(sorted(f"{a}→{b}" for a, b in TYPE_CONVERSIONS))
        return _error(f"unsupported conversion {entity.type}→{new_type} (supported: {supported})")

    if entity.type == "project":
        # A project with active children can't become a task — the children
        # would dangle. Re-point them first.
        child_count = (
            EntityLink.query
            .join(Entity, Entity.id == EntityLink.source_entity_id)
            .filter(
                EntityLink.target_entity_id == entity.id,
                EntityLink.relationship_type == "parent",
                Entity.lifecycle == "active",
            )
            .count()
        )
        if child_count:
            return _error(
                f"project has {child_count} active child entit{'y' if child_count == 1 else 'ies'}; "
                "re-point or resolve them before converting to a task"
            )

    old_snapshot = {"type": entity.type, "status": entity.status}
    entity.status = CONVERSION_STATUS_MAP[(entity.type, new_type)].get(entity.status, DEFAULT_STATUS[new_type])
    entity.type = new_type
    db.session.flush()
    _write_event(
        entity,
        "type_converted",
        old_value=old_snapshot,
        new_value={"type": entity.type, "status": entity.status},
    )
    _queue_embed_job(entity.id, "type_convert")
    db.session.commit()

    return jsonify({"data": _load_entity(entity.id).to_dict()})


@api_v4_bp.route("/entities/<entity_id>/events", methods=["GET"])
def get_entity_events(entity_id):
    if db.session.get(Entity, entity_id) is None:
        return _error("entity not found", 404)
    events = (
        EntityEvent.query.filter_by(entity_id=entity_id)
        .order_by(EntityEvent.created_at.desc())
        .limit(100)
        .all()
    )
    return jsonify({"data": [event.to_dict() for event in events]})


CAPTURE_CHANGE_EVENT_TYPES = {
    "created",
    "ai_updated",
    "relationship_added",
    "activity_update_added",
}


@api_v4_bp.route("/entities/<entity_id>/capture-changes", methods=["GET"])
def get_capture_changes(entity_id):
    if db.session.get(Entity, entity_id) is None:
        return _error("entity not found", 404)
    events = (
        EntityEvent.query.filter_by(source_note_id=entity_id)
        .filter(EntityEvent.event_type.in_(CAPTURE_CHANGE_EVENT_TYPES))
        .order_by(EntityEvent.created_at.asc())
        .all()
    )
    return jsonify({"data": [event.to_dict() for event in events]})


@api_v4_bp.route("/events/<event_id>/revert", methods=["POST"])
def revert_event(event_id):
    event = db.session.get(EntityEvent, event_id)
    if event is None:
        return _error("event not found", 404)
    if event.reverted_at is not None:
        return _error("event already reverted", 409)

    entity = db.session.get(Entity, event.entity_id)
    if entity is None:
        return _error("entity for event not found", 404)

    if event.event_type == "ai_updated":
        old_value = event.old_value or {}
        new_value = event.new_value or {}
        restored = {}
        for field in new_value:
            if field == "status":
                status = old_value.get("status")
                if status is None or status not in VALID_STATUS.get(entity.type, set()):
                    return _error(f"cannot revert: invalid prior status {status!r}")
                entity.status = status
                restored["status"] = status
            elif field == "title":
                entity.title = old_value.get("title")
                restored["title"] = entity.title
            elif field in ("due_at", "follow_up_at"):
                parsed, err = _parse_datetime_or_error(old_value.get(field))
                if err:
                    return err
                setattr(entity, field, parsed)
                restored[field] = old_value.get(field)
            else:
                return _error(f"cannot revert field: {field}")
        db.session.flush()
        _write_event(entity, "reverted", old_value=new_value, new_value=restored, reason=f"revert of event {event.id}")
        _queue_embed_job(entity.id, "revert")

    elif event.event_type == "created":
        old_lifecycle = entity.lifecycle
        entity.lifecycle = "deleted"
        db.session.flush()
        _write_event(
            entity, "reverted",
            old_value={"lifecycle": old_lifecycle}, new_value={"lifecycle": "deleted"},
            reason=f"revert of event {event.id}",
        )

    elif event.event_type == "activity_update_added":
        note_id = (event.new_value or {}).get("note_id")
        au_note = db.session.get(Entity, note_id) if note_id else None
        if au_note is None:
            return _error("activity-update note not found", 404)
        old_lifecycle = au_note.lifecycle
        au_note.lifecycle = "archived"
        db.session.flush()
        _write_event(
            au_note, "reverted",
            old_value={"lifecycle": old_lifecycle}, new_value={"lifecycle": "archived"},
            reason=f"revert of event {event.id}",
        )

    elif event.event_type == "relationship_added":
        link_id = (event.new_value or {}).get("id")
        link = db.session.get(EntityLink, link_id) if link_id else None
        if link is not None:
            link_snapshot = link.to_dict()
            db.session.delete(link)
            db.session.flush()
            _write_event(
                entity, "reverted",
                old_value=link_snapshot, new_value=None,
                reason=f"revert of event {event.id}",
            )

    else:
        return _error(f"cannot revert event of type: {event.event_type}")

    event.reverted_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"data": event.to_dict()})


MAX_ACTIVITY_UPDATES_PER_TARGET = 30


@api_v4_bp.route("/entities/<entity_id>/activity_updates", methods=["GET"])
def get_activity_updates(entity_id):
    target = db.session.get(Entity, entity_id)
    if target is None:
        return _error("entity not found", 404)

    notes = (
        Entity.query.join(
            EntityLink,
            (EntityLink.source_entity_id == Entity.id) & (EntityLink.target_entity_id == entity_id),
        )
        .filter(
            Entity.type == "note",
            Entity.source == "activity_update",
            EntityLink.relationship_type == "activity_update",
        )
        .order_by(Entity.updated_at.desc())
        .limit(MAX_ACTIVITY_UPDATES_PER_TARGET)
        .all()
    )
    return jsonify({"data": [note.to_dict() for note in notes]})


def _create_activity_update_note(target, content, actor="user", confidence=None, evidence=None, source_note_id=None):
    """Create (or reuse) an activity-update note linked to `target`.

    Returns (note_or_None, created_bool). Returns (existing, False) if an
    identical update for this target was created within the last 24h.
    Returns (None, False) if the target already has the maximum number of
    activity updates.
    """
    existing = (
        Entity.query.join(
            EntityLink,
            (EntityLink.source_entity_id == Entity.id) & (EntityLink.target_entity_id == target.id),
        )
        .filter(
            Entity.type == "note",
            Entity.source == "activity_update",
            EntityLink.relationship_type == "activity_update",
            Entity.content == content,
            Entity.updated_at >= datetime.now(timezone.utc) - timedelta(hours=24),
        )
        .first()
    )
    if existing is not None:
        return existing, False

    count = (
        Entity.query.join(
            EntityLink,
            (EntityLink.source_entity_id == Entity.id) & (EntityLink.target_entity_id == target.id),
        )
        .filter(
            Entity.type == "note",
            Entity.source == "activity_update",
            EntityLink.relationship_type == "activity_update",
        )
        .count()
    )
    if count >= MAX_ACTIVITY_UPDATES_PER_TARGET:
        return None, False

    note = Entity(
        type="note",
        title=_activity_update_title(target),
        content=content,
        status="active",
        source="activity_update",
        ai_status="done",
    )
    db.session.add(note)
    db.session.flush()

    link = EntityLink(
        source_entity_id=note.id,
        target_entity_id=target.id,
        relationship_type="activity_update",
        source="activity_update",
    )
    db.session.add(link)

    old_updated = target.updated_at
    target.updated_at = datetime.now(timezone.utc)
    db.session.flush()

    _write_event(
        target,
        "updated",
        old_value={"updated_at": old_updated.isoformat() if old_updated else None},
        new_value={"updated_at": target.updated_at.isoformat()},
    )
    _write_event(
        target,
        "activity_update_added",
        new_value={"note_id": note.id, "content_preview": content[:120]},
        actor=actor,
        confidence=confidence,
        reason=evidence,
        source_note_id=source_note_id,
    )
    _refresh_delegation_cadence(target, source_note_id=source_note_id, actor=actor)
    return note, True


def _refresh_delegation_cadence(target, source_note_id=None, actor="user"):
    """If `target` is a task delegated to a non-owner person, push follow_up_at
    forward by the delegation cadence following an activity update."""
    if target.type != "task":
        return
    assignee_link = (
        EntityLink.query.filter_by(
            source_entity_id=target.id,
            relationship_type="assigned_to",
        )
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(Entity.type == "person")
        .first()
    )
    if assignee_link is None:
        return
    person = db.session.get(Entity, assignee_link.target_entity_id)
    if person is None or _is_owner(person.title, person.id):
        return
    old_follow_up = target.follow_up_at
    cadence_days = _delegation_cadence_days(person.id)
    target.follow_up_at = _add_working_days(datetime.now(timezone.utc), cadence_days)
    _write_event(
        target,
        "ai_updated",
        old_value={"follow_up_at": old_follow_up.isoformat() if old_follow_up else None},
        new_value={"follow_up_at": target.follow_up_at.isoformat()},
        actor=actor,
        reason="delegation cadence refresh",
        source_note_id=source_note_id,
    )


@api_v4_bp.route("/entities/<entity_id>/activity_updates", methods=["POST"])
def create_activity_update(entity_id):
    target = db.session.get(Entity, entity_id)
    if target is None:
        return _error("entity not found", 404)

    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return _error("content is required")

    # Snapshot follow_up_at before note creation: _refresh_delegation_cadence
    # may set it for delegated tasks inside _create_activity_update_note.
    follow_up_before = target.follow_up_at
    note, created = _create_activity_update_note(target, content, actor="user")
    if note is None:
        return _error(
            f"maximum {MAX_ACTIVITY_UPDATES_PER_TARGET} activity updates per entity",
            409,
        )
    if not created:
        return jsonify({"data": note.to_dict(), "skipped": True, "reason": "duplicate within 24h"})

    applied_mentions = _apply_explicit_mentions(note, content)

    # Lightweight extraction: scan for dates and new tasks (no full capture cycle).
    from services.v4_extraction import extract_dates_and_tasks_from_update

    extraction = extract_dates_and_tasks_from_update(content)
    extracted_tasks = []
    suggestions = []

    # ── Follow-up date ──────────────────────────────────────────────────
    explicit_follow_up = extraction.get("follow_up_at")
    delegation_updated = target.follow_up_at is not None and target.follow_up_at != follow_up_before

    if explicit_follow_up:
        old_follow_up = target.follow_up_at
        target.follow_up_at = _parse_iso_date(explicit_follow_up)
        _write_event(
            target,
            "ai_updated",
            old_value={"follow_up_at": old_follow_up.isoformat() if old_follow_up else None},
            new_value={"follow_up_at": target.follow_up_at.isoformat()},
            actor="agent:activity-update",
            reason="extracted from activity update",
            source_note_id=note.id,
        )
    elif target.type == "task" and not delegation_updated:
        # No explicit date found, and delegation cadence didn't set one.
        # Auto-set follow-up to 2 business days from now for tasks.
        old_follow_up = target.follow_up_at
        target.follow_up_at = _add_working_days(datetime.now(timezone.utc), 2)
        _write_event(
            target,
            "ai_updated",
            old_value={"follow_up_at": old_follow_up.isoformat() if old_follow_up else None},
            new_value={"follow_up_at": target.follow_up_at.isoformat()},
            actor="agent:activity-update",
            reason="auto-set 2 business day follow-up",
            source_note_id=note.id,
        )

    # ── New tasks from update content ────────────────────────────────────
    for task_candidate in extraction.get("tasks") or []:
        confidence = task_candidate.get("confidence", 0.0)
        if confidence >= AUTO_APPLY_CONFIDENCE:
            new_task = _auto_create_entity(
                "task",
                task_candidate.get("title"),
                content=task_candidate.get("content"),
                due_at=task_candidate.get("due_at"),
            )
            if new_task:
                found_existing = getattr(new_task, "_auto_create_found_existing", False)
                # Link the new task to the target entity (derived_from).
                _create_entity_link(
                    new_task, target, "derived_from",
                    confidence=confidence,
                    evidence=task_candidate.get("title"),
                    source="activity_update",
                )
                # Handle assignee if specified.
                assignee_name = task_candidate.get("assigned_to")
                if assignee_name:
                    _apply_assignee(
                        note, new_task, assignee_name,
                        confidence=confidence,
                        evidence=f"assigned in activity update: {assignee_name}",
                        source="activity_update",
                        actor="agent:activity-update",
                    )
                if not found_existing:
                    _write_event(
                        new_task,
                        "created",
                        new_value=new_task.to_dict(),
                        actor="agent:activity-update",
                        confidence=confidence,
                        reason="extracted from activity update",
                        source_note_id=note.id,
                    )
                    _queue_embed_job(new_task.id, "activity_update_task")
                extracted_tasks.append({
                    "entity_id": new_task.id,
                    "title": new_task.title,
                    "confidence": confidence,
                    "auto_created": not found_existing,
                })
        else:
            # Lower confidence: create a suggestion for the user to review.
            suggestion = _create_suggestion(
                note,
                suggestion_type="create_task",
                operation_type="create_new_entity",
                payload={
                    "type": "task",
                    "title": task_candidate.get("title"),
                    "content": task_candidate.get("content"),
                    "due_at": task_candidate.get("due_at"),
                    "assigned_to": task_candidate.get("assigned_to"),
                    "evidence": task_candidate.get("title"),
                    "target_entity_id": target.id,
                    "relationship_type": "derived_from",
                },
                confidence=confidence,
                reason=f"extracted from activity update: {task_candidate.get('title', '')[:80]}",
            )
            if suggestion:
                suggestions.append(suggestion.to_dict())
                extracted_tasks.append({
                    "title": task_candidate.get("title"),
                    "confidence": confidence,
                    "auto_created": False,
                    "suggestion_id": suggestion.id,
                })

    db.session.commit()

    return jsonify({
        "data": _load_entity(note.id).to_dict(),
        "target": _load_entity(target.id).to_dict(),
        "extracted": {
            "follow_up_at": explicit_follow_up,
            "follow_up_auto_set": explicit_follow_up is None and target.type == "task",
            "tasks": extracted_tasks,
        },
        "applied_mentions": applied_mentions,
        "suggestions": suggestions,
    }), 201


@api_v4_bp.route("/suggestions", methods=["GET"])
def list_suggestions():
    status = request.args.get("status", "pending")
    limit = max(1, min(request.args.get("limit", 200, type=int), 200))
    query = AiSuggestion.query.options(selectinload(AiSuggestion.source_entity))
    if status != "all":
        query = query.filter(AiSuggestion.status == status)
    total = query.count()
    rows = query.order_by(AiSuggestion.created_at.desc()).limit(limit).all()

    def _serialize(s):
        d = s.to_dict()
        d["source_note_title"] = s.source_entity.title if s.source_entity else None
        return d

    return jsonify({"data": [_serialize(row) for row in rows], "meta": {"total": total, "limit": limit}})


@api_v4_bp.route("/suggestions/reconcile", methods=["POST"])
def reconcile_suggestions():
    limit = max(1, min(request.args.get("limit", 200, type=int), 500))
    rows = (
        AiSuggestion.query.options(selectinload(AiSuggestion.source_entity))
        .filter(AiSuggestion.status == "pending")
        .order_by(AiSuggestion.created_at.asc())
        .limit(limit)
        .all()
    )

    expired = []
    for suggestion in rows:
        outcome = _expire_stale_suggestion_if_needed(suggestion)
        if outcome is not None:
            expired.append(outcome)

    db.session.commit()
    return jsonify({"data": expired, "meta": {"scanned": len(rows), "expired": len(expired), "limit": limit}})


@api_v4_bp.route("/suggestions/<suggestion_id>", methods=["PATCH"])
def update_suggestion(suggestion_id):
    suggestion = db.session.get(AiSuggestion, suggestion_id)
    if suggestion is None:
        return _error("suggestion not found", 404)
    if suggestion.status != "pending":
        return _error("suggestion is not pending", 409)
    if not _is_create_suggestion_operation(suggestion.operation_type):
        return _error("only create_entity suggestions can be edited")

    data = request.get_json(silent=True) or {}
    payload = dict(suggestion.payload or {})

    if "title" in data:
        payload["title"] = (data["title"] or "").strip() or payload.get("title")
    if "content" in data:
        payload["content"] = data["content"]
    if "type" in data:
        new_type = data["type"]
        if new_type not in RISKY_ENTITY_CREATION_TYPES:
            return _error("type must be one of: " + ", ".join(sorted(RISKY_ENTITY_CREATION_TYPES)))
        payload["type"] = new_type

    suggestion.payload = payload
    flag_modified(suggestion, "payload")
    db.session.commit()
    return jsonify({"data": suggestion.to_dict()})


@api_v4_bp.route("/suggestions/<suggestion_id>/accept", methods=["POST"])
def accept_suggestion(suggestion_id):
    suggestion = db.session.get(AiSuggestion, suggestion_id)
    if suggestion is None:
        return _error("suggestion not found", 404)
    if suggestion.status != "pending":
        return _error("suggestion is not pending", 409)
    if suggestion.operation_type == "link_existing":
        return _accept_link_existing_suggestion(suggestion)
    if suggestion.operation_type == "update_entity":
        return _accept_update_entity_suggestion(suggestion)
    if not _is_create_suggestion_operation(suggestion.operation_type):
        return _error(f"unsupported suggestion operation: {suggestion.operation_type}")

    payload = suggestion.payload or {}
    entity_type = payload.get("type")
    if entity_type not in RISKY_ENTITY_CREATION_TYPES:
        return _error("suggestion payload type must be one of: " + ", ".join(sorted(RISKY_ENTITY_CREATION_TYPES)))

    properties = payload.get("properties") or {}
    properties_error = _validate_properties(properties)
    if properties_error:
        return properties_error

    status = payload.get("status") or DEFAULT_STATUS[entity_type]
    validation_error = _validate_status(entity_type, status)
    if validation_error:
        return validation_error

    follow_up_at, follow_up_error = _parse_datetime_or_error(payload.get("follow_up_at"))
    if follow_up_error:
        return follow_up_error
    due_at, due_error = _parse_datetime_or_error(payload.get("due_at"))
    if due_error:
        return due_error

    source_note = db.session.get(Entity, suggestion.source_entity_id)
    if source_note is None:
        return _error("source note not found", 404)

    entity = Entity(
        type=entity_type,
        title=payload.get("title"),
        content=payload.get("content"),
        status=status,
        lifecycle="active",
        due_at=due_at,
        follow_up_at=follow_up_at,
        source="ai_suggestion",
        reference_url=payload.get("reference_url"),
        properties=properties,
        ai_meta={},
        ai_status="pending",
    )
    db.session.add(entity)
    db.session.flush()
    _write_event(entity, "created", new_value=entity.to_dict(), actor="agent:v4-review")
    _queue_embed_job(entity.id, "suggestion_accept_create")

    link_source, link_target, relationship_type = _accepted_suggestion_link(source_note, entity, payload)
    link = _create_entity_link(
        link_source,
        link_target,
        relationship_type,
        suggestion.confidence,
        suggestion.reason,
        source="ai_review",
    )
    if link is not None:
        _write_event(
            link_source,
            "relationship_added",
            new_value=link.to_dict(),
            actor="agent:v4-review",
            confidence=suggestion.confidence,
            reason=suggestion.reason,
        )

    assigned_person, assignment_link, assigned_person_created = _apply_assignee(
        source_note,
        entity,
        payload.get("assigned_to"),
        suggestion.confidence,
        payload.get("evidence") or suggestion.reason,
        source="ai_review",
        actor="agent:v4-review",
    )
    if assigned_person_created:
        _write_event(
            assigned_person,
            "created",
            new_value=assigned_person.to_dict(),
            actor="agent:v4-review",
            confidence=suggestion.confidence,
            reason=suggestion.reason,
        )

    suggestion.status = "accepted"
    suggestion.resolved_at = datetime.utcnow()
    _write_event(
        source_note,
        "suggestion_accepted",
        new_value={"suggestion_id": suggestion.id, "created_entity_id": entity.id},
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        reason=suggestion.reason,
    )
    db.session.commit()

    return jsonify({
        "suggestion": suggestion.to_dict(),
        "created_entity": _load_entity(entity.id).to_dict(),
        "relationship": assignment_link.to_dict() if assignment_link is not None else (link.to_dict() if link is not None else None),
    })


def _accept_link_existing_suggestion(suggestion):
    payload = suggestion.payload or {}
    source_entity = db.session.get(Entity, suggestion.source_entity_id)
    if source_entity is None:
        return _error("source entity not found", 404)

    target_entity_id = payload.get("target_entity_id")
    if not target_entity_id:
        return _error("target_entity_id is required")
    if target_entity_id == source_entity.id:
        return _error("self-link relationships are not allowed")

    target_entity = db.session.get(Entity, target_entity_id)
    if target_entity is None:
        return _error("target entity not found", 404)

    relationship_type = payload.get("relationship_type") or _default_relationship_type(target_entity.type)
    if relationship_type not in RELATIONSHIP_TYPES:
        return _error(f"invalid relationship_type: {relationship_type}")
    if EntityLink.query.filter_by(
        source_entity_id=source_entity.id,
        target_entity_id=target_entity.id,
        relationship_type=relationship_type,
    ).first():
        return _error("duplicate relationship", 409)

    link_source, link_target = _candidate_link_endpoints(source_entity, target_entity, relationship_type)
    link = _create_entity_link(
        link_source,
        link_target,
        relationship_type,
        suggestion.confidence,
        payload.get("evidence") or suggestion.reason,
        source="ai_review",
    )
    _write_event(
        source_entity,
        "relationship_added",
        new_value=link.to_dict(),
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        reason=suggestion.reason,
    )

    suggestion.status = "accepted"
    suggestion.resolved_at = datetime.utcnow()
    _write_event(
        source_entity,
        "suggestion_accepted",
        new_value={"suggestion_id": suggestion.id, "relationship_id": link.id},
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        reason=suggestion.reason,
    )
    db.session.commit()

    return jsonify({
        "suggestion": suggestion.to_dict(),
        "created_entity": None,
        "relationship": link.to_dict(),
    })


def _accept_update_entity_suggestion(suggestion):
    payload = suggestion.payload or {}
    source_entity = db.session.get(Entity, suggestion.source_entity_id)
    if source_entity is None:
        return _error("source entity not found", 404)

    target_entity_id = payload.get("target_entity_id")
    if not target_entity_id:
        return _error("target_entity_id is required")

    target_entity = db.session.get(Entity, target_entity_id)
    if target_entity is None or target_entity.lifecycle == "deleted":
        return _error("target entity not found", 404)

    target_type = payload.get("target_type")
    if target_type and target_type != target_entity.type:
        return _error("target_type does not match target entity")

    fields = payload.get("fields") or {}
    if not isinstance(fields, dict):
        return _error("fields must be an object")

    unsupported = set(fields) - {"status", "due_at", "follow_up_at", "priority"}
    if unsupported:
        return _error("unsupported update fields: " + ", ".join(sorted(unsupported)))

    old_snapshot = target_entity.to_dict()
    changed = {}

    if "status" in fields:
        validation_error = _validate_status(target_entity.type, fields["status"])
        if validation_error:
            return validation_error
        if fields["status"] != target_entity.status:
            target_entity.status = fields["status"]
            changed["status"] = fields["status"]

    if "due_at" in fields:
        due_at, due_error = _parse_datetime_or_error(fields["due_at"])
        if due_error:
            return due_error
        if due_at != target_entity.due_at:
            target_entity.due_at = due_at
            changed["due_at"] = due_at.isoformat() if due_at else None

    if "follow_up_at" in fields:
        follow_up_at, follow_up_error = _parse_datetime_or_error(fields["follow_up_at"])
        if follow_up_error:
            return follow_up_error
        if follow_up_at != target_entity.follow_up_at:
            target_entity.follow_up_at = follow_up_at
            changed["follow_up_at"] = follow_up_at.isoformat() if follow_up_at else None

    if "priority" in fields:
        priority = fields["priority"]
        if priority not in PRIORITY_LEVELS:
            return _error("invalid priority: " + str(priority))
        if priority != (target_entity.properties or {}).get("priority"):
            properties = dict(target_entity.properties or {})
            properties["priority"] = priority
            target_entity.properties = properties
            changed["priority"] = priority

    relationship_type = payload.get("relationship_type") or _default_relationship_type(target_entity.type)
    if relationship_type not in RELATIONSHIP_TYPES:
        return _error(f"invalid relationship_type: {relationship_type}")

    link_source, link_target = _candidate_link_endpoints(source_entity, target_entity, relationship_type)
    link = _create_entity_link(
        link_source,
        link_target,
        relationship_type,
        suggestion.confidence,
        payload.get("evidence") or suggestion.reason,
        source="ai_review",
    )

    if not changed and link is None:
        return _error("suggestion no longer applies", 409)

    if changed:
        db.session.flush()
        new_snapshot = target_entity.to_dict()
        _write_event(
            target_entity,
            "updated",
            old_value=old_snapshot,
            new_value=new_snapshot,
            actor="agent:v4-review",
            confidence=suggestion.confidence,
            reason=suggestion.reason,
        )
        if "status" in changed:
            _write_event(
                target_entity,
                "status_changed",
                old_value={"status": old_snapshot["status"]},
                new_value={"status": target_entity.status},
                actor="agent:v4-review",
                confidence=suggestion.confidence,
                reason=suggestion.reason,
            )
        _queue_embed_job(target_entity.id, "suggestion_accept_update")

    if link is not None:
        _write_event(
            link_source,
            "relationship_added",
            new_value=link.to_dict(),
            actor="agent:v4-review",
            confidence=suggestion.confidence,
            reason=suggestion.reason,
        )

    assigned_person, assignment_link, assigned_person_created = _apply_assignee(
        source_entity,
        target_entity,
        payload.get("assigned_to"),
        suggestion.confidence,
        payload.get("evidence") or suggestion.reason,
        source="ai_review",
        actor="agent:v4-review",
    )
    if assigned_person_created:
        _write_event(
            assigned_person,
            "created",
            new_value=assigned_person.to_dict(),
            actor="agent:v4-review",
            confidence=suggestion.confidence,
            reason=suggestion.reason,
        )

    suggestion.status = "accepted"
    suggestion.resolved_at = datetime.utcnow()
    _write_event(
        source_entity,
        "suggestion_accepted",
        new_value={
            "suggestion_id": suggestion.id,
            "updated_entity_id": target_entity.id,
            "relationship_id": link.id if link is not None else None,
        },
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        reason=suggestion.reason,
    )
    db.session.commit()

    return jsonify({
        "suggestion": suggestion.to_dict(),
        "created_entity": _load_entity(target_entity.id).to_dict(),
        "relationship": assignment_link.to_dict() if assignment_link is not None else (link.to_dict() if link is not None else None),
    })


@api_v4_bp.route("/suggestions/<suggestion_id>/resolve-to-existing", methods=["POST"])
def resolve_suggestion_to_existing(suggestion_id):
    """Resolve a create-entity suggestion by linking to an existing entity.

    The third review action besides accept/dismiss: "this already exists".
    Instead of creating the proposed entity, the source note is linked to
    the existing match (defaulting to the near_match the reconciler found)
    and the suggestion is resolved.
    """
    suggestion = db.session.get(AiSuggestion, suggestion_id)
    if suggestion is None:
        return _error("suggestion not found", 404)
    if suggestion.status != "pending":
        return _error("suggestion is not pending", 409)
    if not _is_create_suggestion_operation(suggestion.operation_type):
        return _error("only create-entity suggestions can be resolved to an existing entity", 400)

    payload = suggestion.payload or {}
    body = request.get_json(silent=True) or {}
    target_id = body.get("target_id") or (payload.get("near_match") or {}).get("entity_id")
    if not target_id:
        return _error("target_id is required (no near_match on this suggestion)")

    target = db.session.get(Entity, target_id)
    if target is None or target.lifecycle == "deleted":
        return _error("target entity not found", 404)

    source_note = db.session.get(Entity, suggestion.source_entity_id)
    if source_note is None:
        return _error("source note not found", 404)
    if target.id == source_note.id:
        return _error("cannot resolve a suggestion to its own source note")

    relationship_type = payload.get("relationship_type") or _default_relationship_type(target.type)
    if relationship_type not in RELATIONSHIP_TYPES:
        relationship_type = _default_relationship_type(target.type)

    link_source, link_target = _candidate_link_endpoints(source_note, target, relationship_type)
    link = _create_entity_link(
        link_source,
        link_target,
        relationship_type,
        suggestion.confidence,
        payload.get("evidence") or suggestion.reason,
        source="ai_review",
    )
    if link is not None:
        _write_event(
            source_note,
            "relationship_added",
            new_value=link.to_dict(),
            actor="agent:v4-review",
            confidence=suggestion.confidence,
            reason=suggestion.reason,
        )

    suggestion.status = "accepted"
    suggestion.resolved_at = datetime.utcnow()
    new_payload = dict(payload)
    new_payload["resolved_to_existing_id"] = target.id
    suggestion.payload = new_payload
    flag_modified(suggestion, "payload")
    _write_event(
        source_note,
        "suggestion_accepted",
        new_value={
            "suggestion_id": suggestion.id,
            "resolved_to_existing_id": target.id,
            "relationship_id": link.id if link is not None else None,
        },
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        reason=f"resolved to existing {target.type} '{target.title}'",
    )
    db.session.commit()

    return jsonify({
        "suggestion": suggestion.to_dict(),
        "linked_entity": _load_entity(target.id).to_dict(),
        "relationship": link.to_dict() if link is not None else None,
    })


@api_v4_bp.route("/suggestions/<suggestion_id>/dismiss", methods=["POST"])
def dismiss_suggestion(suggestion_id):
    suggestion = db.session.get(AiSuggestion, suggestion_id)
    if suggestion is None:
        return _error("suggestion not found", 404)
    if suggestion.status != "pending":
        return _error("suggestion is not pending", 409)

    suggestion.status = "dismissed"
    suggestion.resolved_at = datetime.utcnow()
    source_entity = db.session.get(Entity, suggestion.source_entity_id)
    if source_entity is not None:
        _write_event(
            source_entity,
            "suggestion_dismissed",
            new_value={"suggestion_id": suggestion.id},
            actor="agent:v4-review",
            confidence=suggestion.confidence,
            reason=suggestion.reason,
        )
    db.session.commit()
    return jsonify({"data": suggestion.to_dict()})


@api_v4_bp.route("/entities/<entity_id>/review/resolve", methods=["POST"])
def resolve_entity_review(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    if entity.type != "note":
        return _error("review resolve is only supported for notes")

    pending = AiSuggestion.query.filter_by(source_entity_id=entity_id, status="pending").all()
    dismissed = 0
    for suggestion in pending:
        suggestion.status = "dismissed"
        suggestion.resolved_at = datetime.utcnow()
        dismissed += 1
        _write_event(
            entity,
            "suggestion_dismissed",
            new_value={"suggestion_id": suggestion.id},
            actor="agent:v4-review",
            confidence=suggestion.confidence,
            reason="review resolved without changes",
        )

    _mark_review_resolved(entity)
    _write_event(
        entity,
        "review_marked_resolved",
        new_value={"resolution": "no_change_needed", "dismissed_suggestions": dismissed},
        actor="agent:v4-review",
        reason="reviewed and kept as-is",
    )
    db.session.commit()
    return jsonify({"data": _load_entity(entity.id).to_dict(), "meta": {"dismissed_suggestions": dismissed}})


@api_v4_bp.route("/entities/<entity_id>/resolve", methods=["POST"])
def resolve_note(entity_id):
    """Mark a note as resolved (ai_status=done), clearing it from the inbox."""
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    if entity.type != "note":
        return _error("resolve is only supported for notes", 400)

    old_status = entity.ai_status
    entity.ai_status = "done"
    _write_event(
        entity,
        "updated",
        old_value={"ai_status": old_status},
        new_value={"ai_status": "done"},
        actor="mcp:resolve_note",
    )
    db.session.commit()
    return jsonify({"data": _load_entity(entity.id).to_dict()})


@api_v4_bp.route("/entities/<entity_id>/ingest_candidates", methods=["POST"])
def ingest_candidates(entity_id):
    """Accept pre-extracted candidates from a calling agent, bypassing LLM extraction."""
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    if entity.type != "note":
        return _error("ingest_candidates is only supported for notes")

    from services.v4_extraction import normalize_candidates
    extraction = normalize_candidates(request.get_json(silent=True) or {})
    _clear_review_resolution(entity)

    try:
        applied_changes, suggestions = _reconcile_capture_candidates(entity, extraction)
    except Exception as exc:
        db.session.rollback()
        return _error(f"reconciliation failed: {exc}", 500)

    db.session.commit()
    return jsonify({
        "source_note": _load_entity(entity.id).to_dict(),
        "applied_changes": applied_changes,
        "suggestions": suggestions,
        "warnings": [],
    })


@api_v4_bp.route("/entities/<entity_id>/reprocess", methods=["POST"])
def reprocess_entity(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    if entity.type != "note":
        return _error("reprocess is only supported for notes")

    pending = AiSuggestion.query.filter_by(
        source_entity_id=entity_id, status="pending"
    ).all()
    for s in pending:
        s.status = "dismissed"
        s.resolved_at = datetime.utcnow()
    db.session.flush()

    # Reset AI status so reconciliation's normal pending→done transition fires
    # cleanly. (Without this, an entity in `done` would stay `done` even if the
    # reprocess pass set no summary, which would still be fine, but resetting
    # makes the lifecycle explicit.)
    entity.ai_status = "pending"
    _clear_review_resolution(entity)

    applied_changes = []
    suggestions = []
    try:
        result = _run_basic_capture_extraction(entity, "auto")
        applied_changes, suggestions = _reconcile_capture_candidates(entity, result or {})
    except Exception as exc:
        entity.ai_status = "failed"
        db.session.commit()
        return _error(f"extraction failed: {exc}", 500)

    db.session.commit()
    return jsonify({"applied_changes": applied_changes, "suggestions": suggestions})


@api_v4_bp.route("/entities/<entity_id>/summarize", methods=["POST"])
def summarize_entity_endpoint(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    if entity.type == "note":
        return _error("notes are not summarized; summarize the entities they are linked to")

    from services.v4_summarization import summarize_entity
    summary = summarize_entity(entity_id)
    if summary is None:
        return _error("summarization failed or no linked notes found", 422)

    return jsonify({
        "entity_id": entity_id,
        "summary": summary,
        "summarized_at": _load_entity(entity_id).ai_summarized_at.isoformat(),
    })


@api_v4_bp.route("/entities/<entity_id>/canonical", methods=["GET"])
def get_entity_canonical(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)

    from services.canonical_document import generate_canonical_markdown
    return jsonify({"entity_id": entity.id, "canonical": generate_canonical_markdown(entity)})


@api_v4_bp.route("/entities/<entity_id>/relationships", methods=["GET"])
def get_relationships(entity_id):
    entity = db.session.get(Entity, entity_id)
    if entity is None:
        return _error("entity not found", 404)

    outgoing = EntityLink.query.filter_by(source_entity_id=entity_id).all()
    incoming = EntityLink.query.filter_by(target_entity_id=entity_id).all()
    return jsonify({
        "data": [link.to_dict() for link in outgoing + incoming],
        "outgoing": [link.to_dict() for link in outgoing],
        "incoming": [link.to_dict() for link in incoming],
    })


@api_v4_bp.route("/entities/<entity_id>/relationships", methods=["POST"])
def create_relationship(entity_id):
    source_entity = db.session.get(Entity, entity_id)
    if source_entity is None:
        return _error("source entity not found", 404)

    data = request.get_json(silent=True) or {}
    target_entity_id = data.get("target_entity_id")
    relationship_type = data.get("relationship_type") or "related"
    if relationship_type not in RELATIONSHIP_TYPES:
        return _error(f"invalid relationship_type: {relationship_type}")
    if not target_entity_id:
        return _error("target_entity_id is required")
    if target_entity_id == entity_id:
        return _error("self-link relationships are not allowed")
    if db.session.get(Entity, target_entity_id) is None:
        return _error("target entity not found", 404)
    if EntityLink.query.filter_by(
        source_entity_id=entity_id,
        target_entity_id=target_entity_id,
        relationship_type=relationship_type,
    ).first():
        return _error("duplicate relationship", 409)
    if relationship_type == "blocks" and _creates_blocks_cycle(entity_id, target_entity_id):
        return _error("relationship would create a blocks cycle", 409)

    link = EntityLink(
        source_entity_id=entity_id,
        target_entity_id=target_entity_id,
        relationship_type=relationship_type,
        source=data.get("source") or "manual",
        confidence=data.get("confidence"),
        evidence=data.get("evidence"),
    )
    db.session.add(link)
    db.session.flush()
    _write_event(source_entity, "relationship_added", new_value=link.to_dict())

    # When a task is parent-linked to a project, advance the project's updated_at
    if (relationship_type == "parent"
        and source_entity.type == "task"):
        target_entity = db.session.get(Entity, target_entity_id)
        if target_entity is not None and target_entity.type == "project":
            target_entity.updated_at = datetime.now(timezone.utc)

    db.session.commit()

    return jsonify({"data": link.to_dict()}), 201


@api_v4_bp.route("/relationships/<relationship_id>", methods=["PATCH"])
def update_relationship(relationship_id):
    link = db.session.get(EntityLink, relationship_id)
    if link is None:
        return _error("relationship not found", 404)

    data = request.get_json(silent=True) or {}
    old_value = link.to_dict()
    if "relationship_type" in data:
        relationship_type = data["relationship_type"]
        if relationship_type not in RELATIONSHIP_TYPES:
            return _error(f"invalid relationship_type: {relationship_type}")
        duplicate = EntityLink.query.filter(
            EntityLink.id != relationship_id,
            EntityLink.source_entity_id == link.source_entity_id,
            EntityLink.target_entity_id == link.target_entity_id,
            EntityLink.relationship_type == relationship_type,
        ).first()
        if duplicate:
            return _error("duplicate relationship", 409)
        if relationship_type == "blocks" and _creates_blocks_cycle(link.source_entity_id, link.target_entity_id):
            return _error("relationship would create a blocks cycle", 409)
        link.relationship_type = relationship_type
    for field in ("source", "confidence", "evidence"):
        if field in data:
            setattr(link, field, data[field])

    db.session.flush()
    source_entity = db.session.get(Entity, link.source_entity_id)
    if source_entity is not None:
        _write_event(source_entity, "relationship_updated", old_value=old_value, new_value=link.to_dict())
    db.session.commit()
    return jsonify({"data": link.to_dict()})


@api_v4_bp.route("/relationships/<relationship_id>", methods=["DELETE"])
def delete_relationship(relationship_id):
    link = db.session.get(EntityLink, relationship_id)
    if link is None:
        return _error("relationship not found", 404)

    old_value = link.to_dict()
    source_entity = db.session.get(Entity, link.source_entity_id)
    db.session.delete(link)
    if source_entity is not None:
        _write_event(source_entity, "relationship_removed", old_value=old_value)
    db.session.commit()
    return jsonify({"data": {"id": relationship_id, "deleted": True}})


def _entity_query():
    return Entity.query.options(
        selectinload(Entity.entity_tags).selectinload(EntityTag.tag),
        selectinload(Entity.incoming_links),
        selectinload(Entity.outgoing_links),
    )


def _load_entity(entity_id):
    return _entity_query().filter(Entity.id == entity_id).first()


def _relationship_detail_sections(entity):
    links = (
        EntityLink.query.filter(
            (EntityLink.source_entity_id == entity.id) | (EntityLink.target_entity_id == entity.id)
        )
        .order_by(EntityLink.created_at.asc())
        .all()
    )
    related_entities = _entity_map_for_links(entity.id, links)
    builders = {
        "task": _task_detail_sections,
        "project": _project_detail_sections,
        "area": _area_detail_sections,
        "note": _note_detail_sections,
        "person": _person_detail_sections,
        "resource": _resource_detail_sections,
    }
    return builders[entity.type](entity, links, related_entities)


def _task_detail_sections(entity, links, related_entities):
    return [
        _section("project", "Project", _link_items(entity, links, related_entities, "outgoing", {"parent"}, {"project"})),
        _section("area", "Area", _link_items(entity, links, related_entities, "outgoing", {"parent"}, {"area"})),
        _section("people", "People", _link_items(entity, links, related_entities, "outgoing", {"assigned_to"}, {"person"})),
        _section("people_mentioned", "People Mentioned", _link_items(entity, links, related_entities, "outgoing", {"mentions"}, {"person"})),
        _section("source_notes", "Source Notes", _link_items(entity, links, related_entities, "outgoing", {"derived_from"}, {"note"})),
        _section("related_notes", "Related Notes", _link_items(entity, links, related_entities, "both", {"related"}, {"note"})),
        _section("resources", "Resources", _link_items(entity, links, related_entities, "outgoing", {"references", "related"}, {"resource"})),
        _section("blocking", "Blocking / Blocked By", _link_items(entity, links, related_entities, "both", {"blocks"}, {"task"})),
        _section("related_tasks", "Related Tasks", _link_items(entity, links, related_entities, "both", {"related"}, {"task"})),
        _section("activity_updates", "Activity", _fetch_activity_updates(entity.id)),
    ]


def _fetch_activity_updates(entity_id, limit=5):
    """Fetch recent activity update notes for an entity."""
    updates = (
        Entity.query.join(
            EntityLink,
            (EntityLink.source_entity_id == Entity.id) & (EntityLink.target_entity_id == entity_id),
        )
        .filter(
            Entity.type == "note",
            Entity.source == "activity_update",
            EntityLink.relationship_type == "activity_update",
            Entity.lifecycle == "active",
        )
        .order_by(Entity.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {"id": u.id, "title": u.title, "content": u.content or "", "updated_at": u.updated_at.isoformat() if u.updated_at else None}
        for u in updates
    ]


def _project_detail_sections(entity, links, related_entities):
    return [
        _section("area", "Area", _link_items(entity, links, related_entities, "outgoing", {"parent"}, {"area"})),
        _section(
            "open_tasks",
            "Open Tasks",
            _link_items(entity, links, related_entities, "incoming", {"parent"}, {"task"}, exclude_statuses={"done", "cancelled"}),
        ),
        _section(
            "completed_tasks",
            "Completed Tasks",
            _link_items(entity, links, related_entities, "incoming", {"parent"}, {"task"}, statuses={"done"}),
        ),
        _section("notes", "Notes", _link_items(entity, links, related_entities, "both", {"related", "mentions", "references"}, {"note"})),
        _section("resources", "Resources", _link_items(entity, links, related_entities, "both", {"references", "related"}, {"resource"})),
        _section("people", "People", _link_items(entity, links, related_entities, "both", {"assigned_to", "mentions", "related"}, {"person"})),
        _section("related_projects", "Related Projects", _link_items(entity, links, related_entities, "both", {"related"}, {"project"})),
        _section("blocked_by_blocks", "Blocked By / Blocks", _link_items(entity, links, related_entities, "both", {"blocks"}, {"project"})),
        _section("activity_updates", "Activity", _fetch_activity_updates(entity.id)),
    ]


def _area_detail_sections(entity, links, related_entities):
    return [
        _section("projects", "Projects", _link_items(entity, links, related_entities, "incoming", {"parent", "related"}, {"project"})),
        _section("tasks", "Tasks", _link_items(entity, links, related_entities, "incoming", {"parent", "related"}, {"task"})),
        _section("notes", "Notes", _link_items(entity, links, related_entities, "both", {"related", "mentions"}, {"note"})),
        _section("resources", "Resources", _link_items(entity, links, related_entities, "both", {"references", "related"}, {"resource"})),
        _section("people", "People", _link_items(entity, links, related_entities, "both", {"mentions", "assigned_to", "related"}, {"person"})),
        _section("activity_updates", "Activity", _fetch_activity_updates(entity.id)),
    ]


def _note_detail_sections(entity, links, related_entities):
    return [
        # For activity-update notes: the task/project/area this note is an
        # update on. Standard {entity, relationship} item shape so the UI can
        # navigate from the update back to its target.
        _section("update_on", "Update on", _link_items(entity, links, related_entities, "outgoing", {"activity_update"}, {"task", "project", "area"})),
        _section("projects", "Projects", _link_items(entity, links, related_entities, "outgoing", {"related", "mentions"}, {"project"})),
        _section("areas", "Areas", _link_items(entity, links, related_entities, "outgoing", {"related", "mentions"}, {"area"})),
        _section("people_mentioned", "People Mentioned", _link_items(entity, links, related_entities, "outgoing", {"mentions"}, {"person"})),
        _section("derived_tasks", "Derived Tasks", _link_items(entity, links, related_entities, "incoming", {"derived_from"}, {"task"})),
        _section("referenced_resources", "Referenced Resources", _link_items(entity, links, related_entities, "outgoing", {"references"}, {"resource"})),
        _section("related_notes", "Related Notes", _link_items(entity, links, related_entities, "both", {"related"}, {"note"})),
    ]


def _person_detail_sections(entity, links, related_entities):
    return [
        _section("assigned_tasks", "Assigned Tasks", _link_items(entity, links, related_entities, "incoming", {"assigned_to"}, {"task"})),
        _section("mentioned_in_notes", "Mentioned In Notes", _link_items(entity, links, related_entities, "incoming", {"mentions"}, {"note"})),
        _section("projects", "Projects", _link_items(entity, links, related_entities, "both", {"assigned_to", "mentions", "related"}, {"project"})),
        _section("resources", "Resources", _link_items(entity, links, related_entities, "both", {"references", "related"}, {"resource"})),
        _section("related_people", "Related People", _link_items(entity, links, related_entities, "both", {"related"}, {"person"})),
    ]


def _resource_detail_sections(entity, links, related_entities):
    return [
        _section("referenced_by_notes", "Referenced By Notes", _link_items(entity, links, related_entities, "incoming", {"references"}, {"note"})),
        _section("projects", "Projects", _link_items(entity, links, related_entities, "both", {"references", "related"}, {"project"})),
        _section("tasks", "Tasks", _link_items(entity, links, related_entities, "both", {"references", "related"}, {"task"})),
        _section("areas", "Areas", _link_items(entity, links, related_entities, "both", {"references", "related"}, {"area"})),
        _section("people", "People", _link_items(entity, links, related_entities, "both", {"references", "related"}, {"person"})),
        _section("related_resources", "Related Resources", _link_items(entity, links, related_entities, "both", {"related"}, {"resource"})),
    ]


def _section(key, title, items):
    return {"key": key, "title": title, "items": items}


def _link_items(entity, links, related_entities, direction, relationship_types, related_types, statuses=None, exclude_statuses=None):
    items = []
    for link in links:
        related_entity, resolved_direction = _related_entity_for_link(entity, link, related_entities, direction)
        if related_entity is None or related_entity.lifecycle == "deleted":
            continue
        if link.relationship_type not in relationship_types:
            continue
        if related_entity.type not in related_types:
            continue
        if statuses is not None and related_entity.status not in statuses:
            continue
        if exclude_statuses is not None and related_entity.status in exclude_statuses:
            continue
        items.append(
            {
                "entity": related_entity.to_dict(),
                "relationship": link.to_dict(),
                "direction": resolved_direction,
            }
        )
    return items


def _related_entity_for_link(entity, link, related_entities, direction):
    if direction in {"outgoing", "both"} and link.source_entity_id == entity.id:
        return related_entities.get(link.target_entity_id), "outgoing"
    if direction in {"incoming", "both"} and link.target_entity_id == entity.id:
        return related_entities.get(link.source_entity_id), "incoming"
    return None, None


def _entity_map_for_links(entity_id, links):
    related_ids = {
        link.target_entity_id if link.source_entity_id == entity_id else link.source_entity_id
        for link in links
    }
    if not related_ids:
        return {}
    related_entities = _entity_query().filter(Entity.id.in_(related_ids)).all()
    _attach_project_task_counts(related_entities)
    return {related.id: related for related in related_entities}


def _attach_project_task_counts(entities):
    project_ids = [entity.id for entity in entities if entity.type == "project"]
    if not project_ids:
        return

    counts_by_project = {project_id: {"open": 0, "total": 0} for project_id in project_ids}
    rows = (
        db.session.query(EntityLink.target_entity_id, Entity.status)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "parent",
            EntityLink.target_entity_id.in_(project_ids),
            Entity.type == "task",
            Entity.lifecycle == "active",
        )
        .all()
    )
    for project_id, status in rows:
        counts = counts_by_project[project_id]
        counts["total"] += 1
        if status in OPEN_TASK_STATUSES:
            counts["open"] += 1

    for entity in entities:
        if entity.type == "project":
            entity._task_counts = counts_by_project.get(entity.id, {"open": 0, "total": 0})


def _attach_task_context(entities):
    """Attach parent project/area refs and assignee refs to task rows."""
    task_ids = [entity.id for entity in entities if entity.type == "task"]
    if not task_ids:
        return

    task_context = {
        task_id: {"projects": [], "areas": [], "people": []}
        for task_id in task_ids
    }
    parent_rows = (
        db.session.query(EntityLink.source_entity_id, Entity.id, Entity.title, Entity.type)
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.relationship_type == "parent",
            EntityLink.source_entity_id.in_(task_ids),
            Entity.type.in_(("project", "area")),
            Entity.lifecycle == "active",
        )
        .all()
    )
    for task_id, target_id, target_title, target_type in parent_rows:
        bucket = task_context.setdefault(task_id, {"projects": [], "areas": [], "people": []})
        if target_type == "project":
            bucket["projects"].append({"id": target_id, "title": target_title})
        elif target_type == "area":
            bucket["areas"].append({"id": target_id, "title": target_title})

    assignee_rows = (
        db.session.query(EntityLink.source_entity_id, Entity.id, Entity.title)
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.relationship_type == "assigned_to",
            EntityLink.source_entity_id.in_(task_ids),
            Entity.type == "person",
            Entity.lifecycle == "active",
        )
        .all()
    )
    for task_id, person_id, person_title in assignee_rows:
        bucket = task_context.setdefault(task_id, {"projects": [], "areas": [], "people": []})
        bucket["people"].append({"id": person_id, "title": person_title})

    for entity in entities:
        if entity.type == "task":
            context = task_context.get(entity.id, {"projects": [], "areas": [], "people": []})
            entity._projects = context["projects"]
            entity._areas = context["areas"]
            entity._people = context["people"]


def _attach_compact_link_counts(entities):
    """Attach lightweight note/task/project link counts to compact list rows."""
    compact_entities = [entity for entity in entities if entity.type in COMPACT_LINK_COUNT_RULES]
    if not compact_entities:
        return

    related_ids = set()
    links_by_entity_id = {}
    for entity in compact_entities:
        links = [*entity.incoming_links, *entity.outgoing_links]
        links_by_entity_id[entity.id] = links
        for link in links:
            related_ids.add(link.source_entity_id if link.target_entity_id == entity.id else link.target_entity_id)

    related_entities = {}
    if related_ids:
        related_entities = {
            related.id: related
            for related in Entity.query.filter(
                Entity.id.in_(related_ids),
                Entity.lifecycle != "deleted",
            ).all()
        }

    for entity in compact_entities:
        counts = {"notes": 0, "tasks": 0, "projects": 0}
        for bucket, (direction, relationship_types, related_types) in COMPACT_LINK_COUNT_RULES[entity.type].items():
            items = _link_items(
                entity,
                links_by_entity_id[entity.id],
                related_entities,
                direction,
                relationship_types,
                related_types,
            )
            counts[bucket] = len({item["entity"]["id"] for item in items})
        entity._linked_counts = counts


def _replace_tags(entity, tag_names):
    EntityTag.query.filter_by(entity_id=entity.id).delete(synchronize_session=False)
    for raw_name in tag_names:
        name = str(raw_name).strip()
        if not name:
            continue
        tag = Tag.query.filter_by(name=name).first()
        if tag is None:
            tag = Tag(name=name)
            db.session.add(tag)
            db.session.flush()
        db.session.add(EntityTag(entity_id=entity.id, tag_id=tag.id))


def _add_tag(entity, raw_name):
    name = str(raw_name or "").strip()
    if not name:
        return None
    tag = Tag.query.filter_by(name=name).first()
    if tag is None:
        tag = Tag(name=name)
        db.session.add(tag)
        db.session.flush()
    if EntityTag.query.filter_by(entity_id=entity.id, tag_id=tag.id).first() is None:
        db.session.add(EntityTag(entity_id=entity.id, tag_id=tag.id))
    return tag


def _write_event(entity, event_type, old_value=None, new_value=None, actor="user", confidence=None, reason=None, source_note_id=None):
    db.session.add(
        EntityEvent(
            entity_id=entity.id,
            event_type=event_type,
            actor=actor,
            old_value=old_value,
            new_value=new_value,
            confidence=confidence,
            reason=reason,
            source_note_id=source_note_id,
        )
    )


def _validate_status(entity_type, status):
    if status not in VALID_STATUS[entity_type]:
        return _error(f"invalid status for {entity_type}: {status}")
    return None


def _validate_lifecycle(lifecycle):
    if lifecycle not in VALID_LIFECYCLE:
        return _error(f"invalid lifecycle: {lifecycle}")
    return None


def _validate_properties(properties):
    if not isinstance(properties, dict):
        return _error("properties must be an object")
    bad_key = _find_relationship_property_key(properties)
    if bad_key:
        return _error(f"properties must not contain relationship IDs: {bad_key}")
    return None


def _find_relationship_property_key(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in RELATIONSHIP_PROPERTY_KEYS or key.endswith("_id") or key.endswith("_ids"):
                return key
            found = _find_relationship_property_key(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_relationship_property_key(child)
            if found:
                return found
    return None


def _parse_datetime(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"invalid datetime: {value}") from None


def _parse_datetime_or_error(value):
    try:
        return _parse_datetime(value), None
    except ValueError as exc:
        return None, _error(str(exc))


def _error(message, status=400):
    return jsonify({"error": message}), status


def _title_from_content(content):
    first_line = content.splitlines()[0].strip()
    return first_line[:80] if first_line else "Untitled note"


def _activity_update_title(target):
    """Deterministic title for an activity-update note.

    An update's identity is its target plus when it happened; a truncated
    first sentence ("There was no update on this during the week. Will ch…")
    is unreadable in note lists.
    """
    target_title = title_or_placeholder(target).strip()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"Update: {target_title[:130]} ({today})"


def _run_basic_capture_extraction(note, mode):
    from services.v4_extraction import extract_capture_candidates

    return extract_capture_candidates(note.content or "", mode=mode, exclude_note_id=note.id)


def _reconcile_capture_candidates(note, extraction):
    applied_changes = []
    suggestions = []

    summary = _clean_text(extraction.get("summary"))
    ai_title = _clean_text(extraction.get("title"))
    ai_meta = dict(note.ai_meta or {})
    title_auto = ai_meta.get("title_auto", False)

    if ai_title and title_auto and note.type == "note":
        old_title = note.title
        note.title = ai_title[:160]
        applied_changes.append({"type": "title_updated", "title": note.title})
        _write_event(
            note,
            "ai_updated",
            old_value={"title": old_title},
            new_value={"title": note.title},
            actor="agent:v4-capture",
            confidence=extraction.get("confidence"),
            reason="ai_title_set",
            source_note_id=note.id,
        )

    if summary:
        ai_meta["summary"] = summary
        if extraction.get("confidence") is not None:
            ai_meta["confidence"] = extraction.get("confidence")
        note.ai_meta = ai_meta
        note.ai_status = "done"
        flag_modified(note, "ai_meta")
        applied_changes.append({"type": "summary_updated", "summary": summary})
        _write_event(
            note,
            "ai_processed",
            new_value={"summary": summary},
            actor="agent:v4-capture",
            confidence=extraction.get("confidence"),
            source_note_id=note.id,
        )
    elif ai_title and title_auto:
        # Title set but no summary — still need to persist ai_meta if we touched it.
        note.ai_meta = ai_meta
        flag_modified(note, "ai_meta")

    _apply_capture_intent(note, extraction)

    for tag_candidate in extraction.get("tags") or []:
        name = _candidate_value(tag_candidate, "name")
        confidence = _candidate_confidence(tag_candidate)
        if not name or confidence < AUTO_APPLY_CONFIDENCE:
            continue
        tag = _add_tag(note, name)
        if tag is None:
            continue
        applied_changes.append({"type": "tag_added", "tag": tag.name, "confidence": confidence})
        _write_event(
            note,
            "tag_added",
            new_value={"tag_id": tag.id, "tag": tag.name},
            actor="agent:v4-capture",
            confidence=confidence,
            source_note_id=note.id,
        )

    # Flatten link and entity candidates into a single list for reconciliation.
    # Links carry an explicit relationship_type from extraction; entity candidates
    # get a default that the reconciliation model can override.
    all_candidates = []
    for lc in extraction.get("links") or []:
        target_type = _candidate_value(lc, "target_type") or _candidate_value(lc, "type")
        if target_type not in RISKY_ENTITY_CREATION_TYPES:
            continue
        all_candidates.append({
            **lc,
            "type": target_type,
            "_source": "link",
        })
    for ec in extraction.get("entities") or []:
        if _candidate_value(ec, "type") not in RISKY_ENTITY_CREATION_TYPES:
            continue
        all_candidates.append({**ec, "_source": "entity"})

    # Dedup within this capture by (type, normalized title). The model is
    # supposed to handle this itself (prompt rule), but defense-in-depth: a
    # link candidate and an entity candidate for the same real-world thing
    # would otherwise each trigger a create/update path independently. We
    # keep the link-sourced candidate when both exist (it carries an explicit
    # relationship_type from extraction); otherwise the first seen wins.
    deduped = []
    seen = {}
    for cand in all_candidates:
        title = _candidate_value(cand, "title") or ""
        ctype = _candidate_value(cand, "type") or ""
        key = (ctype, title.casefold())
        if not title or not ctype:
            deduped.append(cand)
            continue
        if key not in seen:
            seen[key] = len(deduped)
            deduped.append(cand)
        elif cand.get("_source") == "link" and deduped[seen[key]].get("_source") != "link":
            deduped[seen[key]] = cand
    all_candidates = deduped

    if all_candidates:
        from services.v4_reconciliation import reconcile_candidates
        decisions = reconcile_candidates(all_candidates)
        for candidate, decision in zip(all_candidates, decisions):
            _apply_reconciliation_decision(note, candidate, decision, applied_changes, suggestions)

    # Reconciliation ran to completion — mark the note as AI-processed regardless
    # of whether extraction produced a summary. Previously notes with empty
    # extraction stayed `ai_status="pending"` forever, polluting the Needs review
    # queue indefinitely.
    if note.ai_status == "pending":
        note.ai_status = "done"

    return applied_changes, suggestions


def _apply_reconciliation_decision(note, candidate, decision, applied_changes, suggestions):
    action = (decision.get("action") or "new").lower()
    confidence = _reconciliation_confidence(candidate, decision)
    evidence = _candidate_value(candidate, "evidence")
    entity_type = _candidate_value(candidate, "type")
    title = _candidate_value(candidate, "title")
    rel_from_decision = decision.get("relationship_type")
    if rel_from_decision is not None:
        relationship_type = rel_from_decision
    else:
        relationship_type = _default_relationship_type(entity_type)
    if relationship_type not in RELATIONSHIP_TYPES:
        relationship_type = _default_relationship_type(entity_type)
    # Tasks extracted from notes should always trace back to their source
    # note via derived_from for provenance/audit. The parent link to the
    # project is added separately by _link_task_to_note_projects. Applies
    # to both "new" (mint a task) and "link" (re-use existing task via
    # exact-title dedup) so the source note→task trace is preserved either
    # way. We override the LLM's suggestion of "mentions" or "related" for
    # tasks because notes aren't merely mentioning tasks — they're producing them.
    if entity_type == "task" and relationship_type in {"related", "mentions", None}:
        relationship_type = "derived_from"

    if action in ("update", "link"):
        target_id = decision.get("target_id")
        target = db.session.get(Entity, target_id) if target_id else None
        if target is None:
            # Match is gone or id was hallucinated — fall through to "new"
            action = "new"

    if action == "progress_update":
        target_id = decision.get("target_id")
        target = db.session.get(Entity, target_id) if target_id else None
        if target is None:
            # No entity to attach the update to — nothing safe to do. Unlike
            # "update"/"link", we don't fall through to "new": a progress
            # note about an existing thing shouldn't spawn a fresh
            # project/task just because the model hallucinated/lost the id.
            return
        update_text = _clean_text(decision.get("update_text")) or evidence
        if not update_text:
            return
        au_note, created = _create_activity_update_note(
            target, update_text, actor="agent:v4-capture", confidence=confidence, evidence=evidence, source_note_id=note.id
        )
        if au_note is None:
            return
        applied_changes.append({
            "type": "activity_update_added",
            "target_entity_id": target.id,
            "note_id": au_note.id,
            "content": update_text,
            "confidence": confidence,
            "created": created,
        })

        new_status = (decision.get("fields") or {}).get("status")
        if new_status in VALID_STATUS.get(target.type, set()) and new_status != target.status:
            if confidence >= AUTO_APPLY_CONFIDENCE:
                old_status = target.status
                target.status = new_status
                applied_changes.append({
                    "type": "entity_updated",
                    "entity_id": target.id,
                    "entity_type": target.type,
                    "title": target.title,
                    "changes": {"status": new_status},
                })
                _write_event(
                    target,
                    "ai_updated",
                    old_value={"status": old_status},
                    new_value={"status": new_status},
                    actor="agent:v4-capture",
                    confidence=confidence,
                    reason=decision.get("reason"),
                    source_note_id=note.id,
                )
                _queue_embed_job(target.id, "capture_auto_update")

                if new_status in {"blocked", "waiting"}:
                    blocker_id = decision.get("blocked_by_id")
                    blocker = db.session.get(Entity, blocker_id) if blocker_id else None
                    if blocker is not None and blocker.id != target.id:
                        link = _create_entity_link(blocker, target, "blocks", confidence, evidence)
                        if link is not None:
                            applied_changes.append({
                                "type": "relationship_added",
                                "source_entity_id": blocker.id,
                                "target_entity_id": target.id,
                                "relationship_type": "blocks",
                                "confidence": confidence,
                            })
                            _write_event(
                                target,
                                "relationship_added",
                                new_value=link.to_dict(),
                                actor="agent:v4-capture",
                                confidence=confidence,
                                reason=decision.get("reason"),
                                source_note_id=note.id,
                            )
            else:
                _append_capture_suggestion(
                    note,
                    candidate,
                    action="update",
                    entity_type=target.type,
                    relationship_type=relationship_type,
                    confidence=confidence,
                    evidence=evidence,
                    suggestions=suggestions,
                    suggestion_type=f"update_{target.type}",
                    operation_type="update_entity",
                    payload={
                        "target_entity_id": target.id,
                        "target_type": target.type,
                        "title": target.title,
                        "fields": {"status": new_status},
                        "relationship_type": relationship_type,
                        "assigned_to": _candidate_value(candidate, "assigned_to"),
                        "evidence": evidence,
                    },
                    reason=decision.get("reason"),
                )

        new_priority = (decision.get("fields") or {}).get("priority")
        if new_priority in PRIORITY_LEVELS:
            current_priority = (target.properties or {}).get("priority")
            if PRIORITY_ORDER.get(new_priority, 0) > PRIORITY_ORDER.get(current_priority, 0):
                _append_capture_suggestion(
                    note,
                    candidate,
                    action="update",
                    entity_type=target.type,
                    relationship_type=relationship_type,
                    confidence=confidence,
                    evidence=evidence,
                    suggestions=suggestions,
                    suggestion_type=f"update_{target.type}",
                    operation_type="update_entity",
                    payload={
                        "target_entity_id": target.id,
                        "target_type": target.type,
                        "title": target.title,
                        "fields": {"priority": new_priority},
                        "relationship_type": relationship_type,
                        "evidence": evidence,
                    },
                    reason=decision.get("reason"),
                )
        return

    if action == "update":
        if confidence >= AUTO_APPLY_CONFIDENCE:
            _apply_entity_update(note, target, candidate, decision, relationship_type, confidence, evidence, applied_changes)
        else:
            _append_capture_suggestion(
                note,
                candidate,
                action="update",
                entity_type=entity_type,
                relationship_type=relationship_type,
                confidence=confidence,
                evidence=evidence,
                suggestions=suggestions,
                suggestion_type=f"update_{entity_type}",
                operation_type="update_entity",
                payload={
                    "target_entity_id": target.id,
                    "target_type": entity_type,
                    "title": target.title,
                    "fields": decision.get("fields") or {},
                    "relationship_type": relationship_type,
                    "assigned_to": _candidate_value(candidate, "assigned_to"),
                    "evidence": evidence,
                },
                reason=decision.get("reason"),
            )
        return

    if action == "link":
        if confidence >= AUTO_APPLY_CONFIDENCE:
            link_source, link_target = _candidate_link_endpoints(note, target, relationship_type)
            link = _create_entity_link(link_source, link_target, relationship_type, confidence, evidence)
            if link is not None:
                applied_changes.append({
                    "type": "relationship_added",
                    "target_entity_id": target.id,
                    "relationship_type": relationship_type,
                    "confidence": confidence,
                })
                _write_event(note, "relationship_added", new_value=link.to_dict(), actor="agent:v4-capture", confidence=confidence, reason=evidence, source_note_id=note.id)
        else:
            _append_capture_suggestion(
                note,
                candidate,
                action="link",
                entity_type=target.type,
                relationship_type=relationship_type,
                confidence=confidence,
                evidence=evidence,
                suggestions=suggestions,
                suggestion_type="link_existing",
                operation_type="link_existing",
                payload={
                    "source_entity_id": note.id,
                    "target_entity_id": target.id,
                    "target_type": target.type,
                    "title": target.title,
                    "relationship_type": relationship_type,
                    "evidence": evidence,
                },
                reason=decision.get("reason"),
            )
        return

    # action == "new"
    if not title or not entity_type:
        return
    content = _candidate_value(candidate, "content")
    top_match_score = decision.get("top_match_score") or 0.0
    if (
        entity_type == "task"
        and confidence < AUTO_CREATE_ENTITY_CONFIDENCE
        and _task_candidate_looks_tentative(candidate)
    ):
        return
    if _can_auto_create_entity(entity_type, confidence, top_match_score):
        entity = _auto_create_entity(
            entity_type=entity_type,
            title=title,
            content=content,
            due_at=decision.get("fields", {}).get("due_at") or _candidate_value(candidate, "due_at"),
            follow_up_at=decision.get("fields", {}).get("follow_up_at") or _candidate_value(candidate, "follow_up_at"),
        )
        found_existing = getattr(entity, "_auto_create_found_existing", False)
        link_source, link_target = _candidate_link_endpoints(note, entity, relationship_type)
        link = _create_entity_link(link_source, link_target, relationship_type, confidence, evidence)
        if not found_existing:
            _write_event(entity, "created", new_value=entity.to_dict(), actor="agent:v4-capture", confidence=confidence, reason=evidence, source_note_id=note.id)
            applied_changes.append({
                "type": "entity_created",
                "entity_id": entity.id,
                "entity_type": entity_type,
                "title": title,
                "confidence": confidence,
            })
        if link is not None:
            _write_event(note, "relationship_added", new_value=link.to_dict(), actor="agent:v4-capture", confidence=confidence, reason=evidence, source_note_id=note.id)
            applied_changes.append({
                "type": "relationship_added",
                "target_entity_id": entity.id,
                "relationship_type": relationship_type,
                "confidence": confidence,
            })
        _apply_assignee_and_record(
            note,
            entity,
            _candidate_value(candidate, "assigned_to"),
            confidence,
            evidence,
            applied_changes,
            source="ai",
            actor="agent:v4-capture",
        )
        if entity_type == "task":
            _link_task_to_note_projects(note, entity, confidence, evidence, applied_changes)
    elif entity_type in {"project", "area"}:
        # Projects/areas proposed as "new" from a capture have never been a
        # useful suggestion in practice (0% acceptance) — they're almost
        # always either an existing project described slightly differently,
        # or a topic mentioned in passing within a multi-topic note (standup
        # digest, meeting transcript). If there's a plausible existing match,
        # offer that as a link suggestion instead; otherwise drop it silently
        # rather than adding to the review queue.
        top_match_id = decision.get("top_match_id")
        if top_match_id and top_match_score >= NEAR_DUPLICATE_SCORE:
            target = db.session.get(Entity, top_match_id)
            if target is not None:
                _append_capture_suggestion(
                    note,
                    candidate,
                    action="link",
                    entity_type=target.type,
                    relationship_type=relationship_type,
                    confidence=confidence,
                    evidence=evidence,
                    suggestions=suggestions,
                    suggestion_type="link_existing",
                    operation_type="link_existing",
                    payload={
                        "source_entity_id": note.id,
                        "target_entity_id": target.id,
                        "target_type": target.type,
                        "title": target.title,
                        "relationship_type": relationship_type,
                        "evidence": evidence,
                    },
                    reason=decision.get("reason"),
                )
    else:
        _append_capture_suggestion(
            note,
            candidate,
            action="new",
            entity_type=entity_type,
            relationship_type=relationship_type,
            confidence=confidence,
            evidence=evidence,
            suggestions=suggestions,
            suggestion_type=f"create_{entity_type}",
            operation_type="create_entity",
            payload={
                "type": entity_type,
                "title": title,
                "content": content,
                "due_at": _candidate_value(candidate, "due_at"),
                "assigned_to": _candidate_value(candidate, "assigned_to"),
                "source_entity_id": note.id,
                "evidence": evidence,
                "relationship_type": relationship_type,
                "near_match": {
                    "entity_id": decision.get("top_match_id"),
                    "title": decision.get("top_match_title"),
                    "score": top_match_score,
                } if decision.get("top_match_id") else None,
            },
            reason=decision.get("reason"),
        )


def _link_task_to_note_projects(note, task, confidence, evidence, applied_changes):
    """Create parent links from a newly auto-created task to every project
    the source note is linked to.

    When a task is extracted from a meeting note, it almost certainly belongs
    to one or more of the projects that note references. Without this step,
    tasks end up orphaned with only a derived_from link to the note, and
    projects show zero open tasks.
    """
    project_link_types = {"related", "mentions", "parent"}
    note_project_links = EntityLink.query.filter(
        EntityLink.source_entity_id == note.id,
        EntityLink.relationship_type.in_(project_link_types),
    ).all()

    project_ids = {
        link.target_entity_id
        for link in note_project_links
    }

    if not project_ids:
        return

    projects = Entity.query.filter(
        Entity.id.in_(project_ids),
        Entity.type == "project",
        Entity.lifecycle == "active",
    ).all()

    for project in projects:
        parent_link = _create_entity_link(
            task,
            project,
            "parent",
            confidence,
            evidence,
            source="ai",
        )
        if parent_link is not None:
            _write_event(
                task,
                "relationship_added",
                new_value=parent_link.to_dict(),
                actor="agent:v4-capture",
                confidence=confidence,
                reason=evidence or f"inherited from note {note.id}",
                source_note_id=note.id,
            )
            applied_changes.append({
                "type": "relationship_added",
                "target_entity_id": project.id,
                "relationship_type": "parent",
                "confidence": confidence,
            })


def _touch_parent_projects(task):
    """Advance updated_at on all active parent projects of a task.

    Called whenever a task is modified so project surfaces reflect
    current activity instead of going stale.
    """
    parent_links = EntityLink.query.filter_by(
        source_entity_id=task.id,
        relationship_type="parent",
    ).all()
    for link in parent_links:
        parent = db.session.get(Entity, link.target_entity_id)
        if parent is not None and parent.lifecycle == "active":
            parent.updated_at = datetime.now(timezone.utc)


def _apply_entity_update(note, entity, candidate, decision, relationship_type, confidence, evidence, applied_changes):
    fields = decision.get("fields") or {}
    changed = {}
    previous = {}

    new_status = fields.get("status")
    if new_status and new_status in VALID_STATUS.get(entity.type, set()):
        previous["status"] = entity.status
        entity.status = new_status
        changed["status"] = new_status

    raw_due = fields.get("due_at")
    if raw_due:
        parsed = _parse_iso_date(raw_due)
        if parsed:
            previous["due_at"] = entity.due_at.isoformat() if entity.due_at else None
            entity.due_at = parsed
            changed["due_at"] = raw_due

    raw_follow_up = fields.get("follow_up_at")
    if raw_follow_up:
        parsed = _parse_iso_date(raw_follow_up)
        if parsed:
            previous["follow_up_at"] = entity.follow_up_at.isoformat() if entity.follow_up_at else None
            entity.follow_up_at = parsed
            changed["follow_up_at"] = raw_follow_up

    link_source, link_target = _candidate_link_endpoints(note, entity, relationship_type)
    link = _create_entity_link(link_source, link_target, relationship_type, confidence, evidence)

    if changed:
        applied_changes.append({
            "type": "entity_updated",
            "entity_id": entity.id,
            "entity_type": entity.type,
            "title": entity.title,
            "changes": changed,
        })
        _write_event(
            entity, "ai_updated", old_value=previous, new_value=changed, actor="agent:v4-capture",
            confidence=confidence, reason=decision.get("reason"), source_note_id=note.id,
        )
        _queue_embed_job(entity.id, "capture_auto_update")
    if link is not None:
        applied_changes.append({
            "type": "relationship_added",
            "target_entity_id": entity.id,
            "relationship_type": relationship_type,
            "confidence": confidence,
        })
        _write_event(note, "relationship_added", new_value=link.to_dict(), actor="agent:v4-capture", confidence=confidence, reason=evidence, source_note_id=note.id)
    _apply_assignee_and_record(
        note,
        entity,
        _candidate_value(candidate, "assigned_to"),
        confidence,
        evidence,
        applied_changes,
        source="ai",
        actor="agent:v4-capture",
    )


def _get_app_setting(key, default=None):
    setting = db.session.get(AppSetting, key)
    return setting.value if setting is not None else default


def _app_setting_row(key):
    setting = db.session.get(AppSetting, key)
    if setting is None:
        setting = AppSetting(key=key, value=None)
        db.session.add(setting)
    return setting


def _set_app_setting(key, value):
    setting = _app_setting_row(key)
    setting.value = value
    flag_modified(setting, "value")
    db.session.commit()
    return value


def _owner_person_id():
    owner_person_id = _clean_text(_get_app_setting("owner_person_id"))
    return owner_person_id


def _owner_aliases():
    aliases = _get_app_setting("owner_aliases", DEFAULT_OWNER_ALIASES)
    return {str(a).strip().lower() for a in aliases}


def _is_owner(name, person_id=None):
    owner_person_id = _owner_person_id()
    if owner_person_id is not None:
        return person_id == owner_person_id
    cleaned = _clean_text(name)
    if cleaned is None:
        return False
    return cleaned.lower() in _owner_aliases()


def _record_owner_identity_change(previous_owner, next_owner, actor="user"):
    if previous_owner is not None and previous_owner.id != (next_owner.id if next_owner is not None else None):
        _write_event(
            previous_owner,
            "updated",
            old_value={"is_owner": True},
            new_value={"is_owner": False},
            actor=actor,
            reason="owner identity updated",
        )
    if next_owner is not None and next_owner.id != (previous_owner.id if previous_owner is not None else None):
        _write_event(
            next_owner,
            "updated",
            old_value={"is_owner": False},
            new_value={"is_owner": True},
            actor=actor,
            reason="owner identity updated",
        )


def _delegation_cadence_days(person_id=None):
    overrides = _get_app_setting("cadence_overrides", {}) or {}
    if person_id and person_id in overrides:
        return overrides[person_id]
    return _get_app_setting("default_cadence_days", DEFAULT_DELEGATION_CADENCE_DAYS)


def _add_working_days(start, days):
    """Add `days` working days (Mon-Fri) to `start`, skipping weekends."""
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _latest_activity_updates(entity_ids):
    """Map entity_id -> (created_at, content) of its most recent activity-update note."""
    if not entity_ids:
        return {}
    rows = (
        db.session.query(EntityLink.target_entity_id, Entity.created_at, Entity.content)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "activity_update",
            EntityLink.target_entity_id.in_(entity_ids),
        )
        .order_by(EntityLink.target_entity_id, Entity.created_at.desc())
        .all()
    )
    latest = {}
    for target_id, created_at, content in rows:
        if target_id not in latest:
            latest[target_id] = (created_at, content)
    return latest


def _ensure_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _days_since(reference, now):
    reference = _ensure_utc(reference)
    if reference is None:
        return None
    return max(0, (now - reference).days)


def _person_open_tasks(person):
    """Open tasks assigned to `person`."""
    return (
        _entity_query()
        .join(EntityLink, (EntityLink.source_entity_id == Entity.id) & (EntityLink.relationship_type == "assigned_to"))
        .filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
            EntityLink.target_entity_id == person.id,
        )
        .order_by(Entity.follow_up_at.asc().nullslast(), Entity.updated_at.desc())
        .limit(50)
        .all()
    )


def _project_open_tasks(project):
    """Open tasks parent-linked to `project`."""
    return (
        _entity_query()
        .join(EntityLink, (EntityLink.source_entity_id == Entity.id) & (EntityLink.relationship_type == "parent"))
        .filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
            EntityLink.target_entity_id == project.id,
        )
        .order_by(Entity.due_at.asc().nullslast(), Entity.follow_up_at.asc().nullslast(), Entity.updated_at.desc())
        .limit(50)
        .all()
    )


def _person_current_load(tasks, latest_update):
    """Open tasks assigned to a person, each with last-activity-update info."""
    if not tasks:
        return []

    results = []
    for task in tasks:
        last = latest_update.get(task.id)
        last_created, last_content = last if last else (None, None)
        results.append({
            "task": _entity_with_attention(task),
            "last_heard_at": _iso(last_created),
            "last_heard_preview": last_content[:160] if last_content else None,
        })
    return results


def _person_pulse(tasks, latest_update, now=None):
    """Transient 1:1 prep signal for a person's current work."""
    now = now or datetime.now(timezone.utc)
    summary = {
        "open_tasks": len(tasks),
        "stuck_tasks": 0,
        "overdue_follow_ups": 0,
        "quiet_tasks": 0,
    }
    focus_items = []

    for task in tasks:
        last_created, last_content = latest_update.get(task.id, (None, None))
        last_heard_preview = last_content[:160] if last_content else None
        is_stuck = task.status in {"blocked", "waiting"}
        follow_up_at = _ensure_utc(task.follow_up_at)
        overdue_days = max(1, (now.date() - follow_up_at.date()).days) if follow_up_at and follow_up_at < now else 0
        quiet_days = _days_since(last_created or task.created_at, now) or 0
        is_quiet = quiet_days >= PERSON_PULSE_QUIET_DAYS

        if is_stuck:
            summary["stuck_tasks"] += 1
        if overdue_days:
            summary["overdue_follow_ups"] += 1
        if is_quiet:
            summary["quiet_tasks"] += 1

        if is_stuck:
            focus = {
                "kind": "stuck",
                "label": "Blocked" if task.status == "blocked" else "Waiting",
            }
            rank = (0, 0)
        elif overdue_days:
            focus = {
                "kind": "overdue_follow_up",
                "label": f"Follow-up overdue by {overdue_days} day{'s' if overdue_days != 1 else ''}",
            }
            rank = (1, -overdue_days)
        elif is_quiet:
            focus = {
                "kind": "quiet",
                "label": f"No update in {quiet_days} day{'s' if quiet_days != 1 else ''}",
            }
            rank = (2, -quiet_days)
        else:
            continue

        focus_items.append((rank, {
            **focus,
            "entity": _entity_with_attention(task),
            "last_heard_at": _iso(last_created),
            "last_heard_preview": last_heard_preview,
        }))

    focus_items.sort(key=lambda item: item[0])
    return {
        "headline": _person_pulse_headline(summary),
        "summary": summary,
        "focus_items": [item for _, item in focus_items[:5]],
    }


def _person_pulse_headline(summary):
    parts = []
    if summary["stuck_tasks"]:
        parts.append(f"{summary['stuck_tasks']} stuck task{'s' if summary['stuck_tasks'] != 1 else ''}")
    if summary["overdue_follow_ups"]:
        parts.append(
            f"{summary['overdue_follow_ups']} overdue follow-up"
            f"{'s' if summary['overdue_follow_ups'] != 1 else ''}"
        )
    if summary["quiet_tasks"]:
        parts.append(f"{summary['quiet_tasks']} quiet task{'s' if summary['quiet_tasks'] != 1 else ''}")
    if not parts:
        return "No obvious follow-up risk right now."
    if len(parts) == 1:
        joined = parts[0]
    elif len(parts) == 2:
        joined = f"{parts[0]} and {parts[1]}"
    else:
        joined = f"{', '.join(parts[:-1])}, and {parts[-1]}"
    return f"Focus the next 1:1 on {joined}."


def _person_recent_notes(person):
    """Recent non-activity notes that mention `person`."""
    notes = (
        _entity_query()
        .join(EntityLink, (EntityLink.source_entity_id == Entity.id) & (EntityLink.relationship_type == "mentions"))
        .filter(
            Entity.type == "note",
            Entity.lifecycle == "active",
            Entity.source != "activity_update",
            EntityLink.target_entity_id == person.id,
        )
        .order_by(Entity.updated_at.desc(), Entity.created_at.desc())
        .limit(3)
        .all()
    )
    return [
        {
            "id": note.id,
            "type": note.type,
            "title": note.title,
            "updated_at": _iso(note.updated_at),
            "preview": (note.content or "")[:160] or None,
        }
        for note in notes
    ]


def _person_meeting_prep(person, tasks, latest_update, pulse, now=None):
    """Transient meeting-prep artifact for a person's detail page."""
    now = now or datetime.now(timezone.utc)
    agenda_items = []

    for item in pulse.get("focus_items", []):
        if item["kind"] == "stuck":
            title = f"Unblock {item['entity']['title']}"
        elif item["kind"] == "overdue_follow_up":
            title = f"Confirm next step for {item['entity']['title']}"
        elif item["kind"] == "quiet":
            title = f"Ask for status on {item['entity']['title']}"
        else:
            title = item["entity"]["title"]
        reason = item["label"]
        if item.get("last_heard_preview"):
            reason += f". Last heard: {item['last_heard_preview']}"
        agenda_items.append({
            "kind": item["kind"],
            "title": title,
            "reason": reason,
            "entity": item["entity"],
        })

    focused_ids = {item["entity"]["id"] for item in agenda_items}
    progress_candidates = []
    for task in tasks:
        if task.id in focused_ids:
            continue
        last_created, last_content = latest_update.get(task.id, (None, None))
        if last_created is None:
            continue
        if _days_since(last_created, now) is None or _days_since(last_created, now) > 7:
            continue
        progress_candidates.append({
            "kind": "recent_progress",
            "title": f"Acknowledge progress on {task.title}",
            "reason": (last_content or "")[:160] or "Recent update shared",
            "entity": _entity_with_attention(task),
            "_sort": _ensure_utc(last_created),
        })

    progress_candidates.sort(key=lambda item: item["_sort"], reverse=True)
    for item in progress_candidates[: max(0, 4 - len(agenda_items))]:
        item.pop("_sort", None)
        agenda_items.append(item)

    recent_notes = _person_recent_notes(person)
    return {
        "headline": _meeting_prep_headline(len(agenda_items), len(recent_notes)),
        "counts": {
            "agenda_items": len(agenda_items),
            "recent_notes": len(recent_notes),
        },
        "agenda_items": agenda_items[:4],
        "recent_notes": recent_notes,
    }


def _meeting_prep_headline(agenda_count, note_count):
    agenda_label = f"{agenda_count} agenda topic{'s' if agenda_count != 1 else ''}"
    note_label = f"{note_count} recent note{'s' if note_count != 1 else ''}"
    return f"Go in with {agenda_label} and {note_label}."


def _coordination_radar(now=None):
    now = now or datetime.now(timezone.utc)
    return {
        "people": _coordination_radar_people(now),
        "projects": _coordination_radar_projects(now),
    }


def _coordination_radar_people(now):
    owner_person_id = _owner_person_id()
    rows = (
        db.session.query(EntityLink.target_entity_id, Entity)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "assigned_to",
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
        )
        .order_by(
            EntityLink.target_entity_id,
            Entity.follow_up_at.asc().nullslast(),
            Entity.updated_at.desc(),
        )
        .all()
    )
    if not rows:
        return []

    tasks_by_person_id = {}
    task_ids = []
    for person_id, task in rows:
        tasks_by_person_id.setdefault(person_id, []).append(task)
        task_ids.append(task.id)

    people = (
        _entity_query()
        .filter(
            Entity.type == "person",
            Entity.lifecycle == "active",
            Entity.status == "active",
            Entity.id.in_(list(tasks_by_person_id)),
        )
        .all()
    )
    people_by_id = {person.id: person for person in people}
    latest_update = _latest_activity_updates(task_ids)

    radar_items = []
    for person_id, tasks in tasks_by_person_id.items():
        if owner_person_id is not None and person_id == owner_person_id:
            continue
        person = people_by_id.get(person_id)
        if person is None:
            continue
        if owner_person_id is None and _is_owner(person.title, person.id):
            continue
        pulse = _person_pulse(tasks[:50], latest_update, now=now)
        counts = pulse["summary"]
        if not (counts["stuck_tasks"] or counts["overdue_follow_ups"] or counts["quiet_tasks"]):
            continue
        radar_items.append({
            "entity_id": person.id,
            "entity_type": "person",
            "title": person.title,
            "headline": pulse["headline"],
            "counts": counts,
            "_rank": (
                counts["stuck_tasks"],
                counts["overdue_follow_ups"],
                counts["quiet_tasks"],
                counts["open_tasks"],
            ),
        })

    radar_items.sort(key=lambda item: item["_rank"], reverse=True)
    for item in radar_items:
        item.pop("_rank", None)
    return radar_items[:3]


def _today_dependency_interventions(now):
    tasks = (
        _entity_query()
        .filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
        )
        .order_by(Entity.updated_at.desc())
        .limit(200)
        .all()
    )
    latest_update = _latest_activity_updates([task.id for task in tasks])
    watch = _task_dependency_watch(tasks, latest_update, limit=10)
    return watch["focus_items"]


def _coordination_radar_projects(now):
    rows = (
        db.session.query(EntityLink.target_entity_id, Entity)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "parent",
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
        )
        .order_by(
            EntityLink.target_entity_id,
            Entity.due_at.asc().nullslast(),
            Entity.follow_up_at.asc().nullslast(),
            Entity.updated_at.desc(),
        )
        .all()
    )
    if not rows:
        return []

    tasks_by_project_id = {}
    task_ids = []
    for project_id, task in rows:
        tasks_by_project_id.setdefault(project_id, []).append(task)
        task_ids.append(task.id)

    projects = (
        _entity_query()
        .filter(
            Entity.type == "project",
            Entity.lifecycle == "active",
            Entity.status == "active",
            Entity.id.in_(list(tasks_by_project_id)),
        )
        .all()
    )
    projects_by_id = {project.id: project for project in projects}
    latest_update = _latest_activity_updates(task_ids)

    radar_items = []
    for project_id, tasks in tasks_by_project_id.items():
        project = projects_by_id.get(project_id)
        if project is None:
            continue
        pulse = _project_pulse(tasks[:50], latest_update, now=now)
        counts = pulse["summary"]
        if not (counts["stuck_tasks"] or counts["overdue_tasks"] or counts["quiet_tasks"]):
            continue
        radar_items.append({
            "entity_id": project.id,
            "entity_type": "project",
            "title": project.title,
            "headline": pulse["headline"],
            "counts": counts,
            "_rank": (
                counts["stuck_tasks"],
                counts["overdue_tasks"],
                counts["quiet_tasks"],
                counts["open_tasks"],
            ),
        })

    radar_items.sort(key=lambda item: item["_rank"], reverse=True)
    for item in radar_items:
        item.pop("_rank", None)
    return radar_items[:3]


def _project_pulse(tasks, latest_update, now=None):
    """Transient project pulse derived from open project tasks."""
    now = now or datetime.now(timezone.utc)
    summary = {
        "open_tasks": len(tasks),
        "stuck_tasks": 0,
        "overdue_tasks": 0,
        "quiet_tasks": 0,
    }
    focus_items = []

    for task in tasks:
        last_created, last_content = latest_update.get(task.id, (None, None))
        last_heard_preview = last_content[:160] if last_content else None
        is_stuck = task.status in {"blocked", "waiting"}
        due_refs = [dt for dt in (_ensure_utc(task.due_at), _ensure_utc(task.follow_up_at)) if dt is not None]
        overdue_at = min(due_refs) if due_refs else None
        overdue_days = max(1, (now.date() - overdue_at.date()).days) if overdue_at and overdue_at < now else 0
        quiet_days = _days_since(last_created or task.created_at, now) or 0
        is_quiet = quiet_days >= PERSON_PULSE_QUIET_DAYS

        if is_stuck:
            summary["stuck_tasks"] += 1
        if overdue_days:
            summary["overdue_tasks"] += 1
        if is_quiet:
            summary["quiet_tasks"] += 1

        if is_stuck:
            focus = {"kind": "stuck", "label": "Blocked" if task.status == "blocked" else "Waiting"}
            rank = (0, 0)
        elif overdue_days:
            focus = {
                "kind": "overdue",
                "label": f"Overdue by {overdue_days} day{'s' if overdue_days != 1 else ''}",
            }
            rank = (1, -overdue_days)
        elif is_quiet:
            focus = {
                "kind": "quiet",
                "label": f"No update in {quiet_days} day{'s' if quiet_days != 1 else ''}",
            }
            rank = (2, -quiet_days)
        else:
            continue

        focus_items.append((rank, {
            **focus,
            "entity": _entity_with_attention(task),
            "last_heard_at": _iso(last_created),
            "last_heard_preview": last_heard_preview,
        }))

    focus_items.sort(key=lambda item: item[0])
    return {
        "headline": _project_pulse_headline(summary),
        "summary": summary,
        "focus_items": [item for _, item in focus_items[:5]],
    }


def _task_dependency_watch(tasks, latest_update, limit=5):
    task_ids = [task.id for task in tasks]
    if not task_ids:
        return {
            "headline": "No active blockers or dependency chains right now.",
            "summary": {"blocked_tasks": 0, "external_blockers": 0, "blocking_tasks": 0},
            "focus_items": [],
        }

    task_id_set = set(task_ids)
    blocked_rows = (
        db.session.query(EntityLink.target_entity_id, Entity)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "blocks",
            EntityLink.target_entity_id.in_(task_ids),
            Entity.lifecycle == "active",
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(EntityLink.target_entity_id, Entity.updated_at.desc())
        .all()
    )
    blocking_rows = (
        db.session.query(EntityLink.source_entity_id, Entity)
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.relationship_type == "blocks",
            EntityLink.source_entity_id.in_(task_ids),
            Entity.lifecycle == "active",
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(EntityLink.source_entity_id, Entity.updated_at.desc())
        .all()
    )

    tasks_by_id = {task.id: task for task in tasks}
    blocking_counts = _blocking_impact_counts(tasks)
    blocked_task_ids = set()
    external_blockers = 0
    focus_items = []

    for target_id, blocker in blocked_rows:
        task = tasks_by_id.get(target_id)
        if task is None:
            continue
        if task.status not in {"blocked", "waiting"}:
            continue
        blocked_task_ids.add(target_id)
        last_created, last_content = latest_update.get(target_id, (None, None))
        is_external = blocker.id not in task_id_set
        if is_external:
            external_blockers += 1
        focus_items.append((
            (0 if is_external else 1, 0),
            {
                "kind": "external_blocker" if is_external else "blocked_by",
                "label": f"Blocked by {blocker.title or 'Untitled task'}",
                "entity": _entity_with_attention(task),
                "blocker": _entity_with_attention(blocker),
                "last_heard_at": _iso(last_created),
                "last_heard_preview": last_content[:160] if last_content else None,
            },
        ))

    first_blocked_target = {}
    for source_id, target in blocking_rows:
        first_blocked_target.setdefault(source_id, target)

    for source_id, count in blocking_counts.items():
        task = tasks_by_id.get(source_id)
        if task is None or count <= 0:
            continue
        focus_items.append((
            (2, -count),
            {
                "kind": "blocking",
                "label": f"Blocking {count} open task{'s' if count != 1 else ''}",
                "entity": _entity_with_attention(task),
                "blocked_count": count,
                "blocked_preview": first_blocked_target.get(source_id).title if first_blocked_target.get(source_id) else None,
            },
        ))

    focus_items.sort(key=lambda item: item[0])
    summary = {
        "blocked_tasks": len(blocked_task_ids),
        "external_blockers": external_blockers,
        "blocking_tasks": len([count for count in blocking_counts.values() if count > 0]),
    }
    return {
        "headline": _project_dependency_watch_headline(summary),
        "summary": summary,
        "focus_items": [item for _, item in focus_items[:limit]],
    }


def _project_dependency_watch_headline(summary):
    parts = []
    if summary["blocked_tasks"]:
        parts.append(f"{summary['blocked_tasks']} blocked task{'s' if summary['blocked_tasks'] != 1 else ''}")
    if summary["external_blockers"]:
        parts.append(
            f"{summary['external_blockers']} external dependenc"
            f"{'ies' if summary['external_blockers'] != 1 else 'y'}"
        )
    if summary["blocking_tasks"]:
        parts.append(
            f"{summary['blocking_tasks']} task"
            f"{'s' if summary['blocking_tasks'] != 1 else ''} blocking others"
        )
    if not parts:
        return "No active blockers or dependency chains right now."
    if len(parts) == 1:
        joined = parts[0]
    elif len(parts) == 2:
        joined = f"{parts[0]} and {parts[1]}"
    else:
        joined = f"{', '.join(parts[:-1])}, and {parts[-1]}"
    return f"Watch {joined}."


def _project_pulse_headline(summary):
    parts = []
    if summary["stuck_tasks"]:
        parts.append(f"{summary['stuck_tasks']} stuck task{'s' if summary['stuck_tasks'] != 1 else ''}")
    if summary["overdue_tasks"]:
        parts.append(f"{summary['overdue_tasks']} overdue task{'s' if summary['overdue_tasks'] != 1 else ''}")
    if summary["quiet_tasks"]:
        parts.append(f"{summary['quiet_tasks']} quiet task{'s' if summary['quiet_tasks'] != 1 else ''}")
    if not parts:
        return "No obvious delivery risk right now."
    if len(parts) == 1:
        joined = parts[0]
    elif len(parts) == 2:
        joined = f"{parts[0]} and {parts[1]}"
    else:
        joined = f"{', '.join(parts[:-1])}, and {parts[-1]}"
    return f"Focus this project on {joined}."


def _delegations_quiet(now):
    """Tasks delegated to a non-owner person whose follow_up_at has passed
    with no activity update since. Batched (no N+1)."""
    from sqlalchemy.orm import aliased

    PersonEntity = aliased(Entity)
    owner_person_id = _owner_person_id()
    owner_aliases = _owner_aliases() if owner_person_id is None else set()

    tasks = (
        _entity_query()
        .join(EntityLink, (EntityLink.source_entity_id == Entity.id) & (EntityLink.relationship_type == "assigned_to"))
        .join(PersonEntity, PersonEntity.id == EntityLink.target_entity_id)
        .filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            ~Entity.status.in_(DONE_TASK_STATUSES),
            Entity.follow_up_at.isnot(None),
            Entity.follow_up_at < now,
            PersonEntity.type == "person",
        )
    )
    if owner_person_id is not None:
        tasks = tasks.filter(PersonEntity.id != owner_person_id)
    elif owner_aliases:
        tasks = tasks.filter(~func.lower(PersonEntity.title).in_(owner_aliases))
    tasks = tasks.order_by(Entity.follow_up_at.asc()).limit(50).all()
    if not tasks:
        return []

    task_ids = [task.id for task in tasks]
    latest_update = _latest_activity_updates(task_ids)

    results = []
    for task in tasks:
        last = latest_update.get(task.id)
        last_created, last_content = last if last else (None, None)
        if last_created is not None:
            reference = last_created
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=timezone.utc)
            if reference >= task.follow_up_at:
                continue
        else:
            reference = task.follow_up_at

        item = _entity_with_attention(task, context=["delegation_quiet"])
        item["days_silent"] = (now - reference).days
        item["last_update"] = last_content[:160] if last_content else None
        results.append(item)
    return results


def _parse_iso_date(value):
    """Parse an ISO 8601 date string into a timezone-aware datetime, or None."""
    if not value:
        return None
    try:
        from datetime import datetime, timezone
        s = str(value).strip()[:10]
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None




def _auto_create_entity(entity_type, title, content=None, properties=None, due_at=None, follow_up_at=None):
    existing = _find_existing_entity(entity_type, title)
    if existing is not None:
        existing._auto_create_found_existing = True
        return existing
    entity = Entity(
        type=entity_type,
        title=title,
        content=content,
        status="open" if entity_type == "task" else "active",
        lifecycle="active",
        source="ai_capture",
        properties=properties or {},
        ai_meta={},
        ai_status="pending",
        due_at=_parse_iso_date(due_at),
        follow_up_at=_parse_iso_date(follow_up_at),
    )
    db.session.add(entity)
    db.session.flush()
    _queue_embed_job(entity.id, "capture_auto_create")
    return entity


def _create_suggestion(note, suggestion_type, operation_type, payload, confidence=None, reason=None):
    fingerprint = _suggestion_fingerprint(suggestion_type, operation_type, payload)
    existing_pending = _existing_pending_suggestion(fingerprint)
    if existing_pending is not None:
        if existing_pending.source_entity_id == note.id:
            if confidence is not None and (existing_pending.confidence is None or confidence > existing_pending.confidence):
                existing_pending.confidence = confidence
            if reason:
                existing_pending.reason = reason
            return existing_pending
        return None

    if _recently_resolved_duplicate(fingerprint, confidence):
        return None

    _clear_review_resolution(note)
    suggestion = AiSuggestion(
        source_entity_id=note.id,
        suggestion_type=suggestion_type,
        operation_type=operation_type,
        payload={**(payload or {}), "_fingerprint": fingerprint},
        confidence=confidence,
        reason=reason,
        status="pending",
    )
    db.session.add(suggestion)
    db.session.flush()
    return suggestion


def _creates_blocks_cycle(source_entity_id, target_entity_id):
    """True if adding source --blocks--> target would create a cycle, i.e. if
    target can already (transitively) reach source via 'blocks' links."""
    if source_entity_id == target_entity_id:
        return True
    visited = set()
    frontier = [target_entity_id]
    while frontier:
        current = frontier.pop()
        if current == source_entity_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        next_ids = [
            row[0] for row in db.session.query(EntityLink.target_entity_id)
            .filter(
                EntityLink.source_entity_id == current,
                EntityLink.relationship_type == "blocks",
            )
            .all()
        ]
        frontier.extend(next_ids)
    return False


# Matches markdown links produced by the inline @/[[ mention picker, e.g.
# "[Ship the feature](/tasks/3e6c...-...)". Capturing the plural type segment
# lets us resolve straight back to an entity without any LLM involvement.
EXPLICIT_MENTION_PATTERN = re.compile(
    r"\[[^\]\n]+\]\(/(?P<plural>[a-z]+)/(?P<id>[0-9a-fA-F-]{36})\)"
)


def _apply_explicit_mentions(note, content):
    """Create direct `mentions` links for entities picked via the inline
    @/[[ picker while typing `content`.

    These references are explicit user choices, so they bypass extraction
    and reconciliation entirely — confidence 1.0, no review needed.
    """
    if not content:
        return []
    applied = []
    seen_ids = set()
    for match in EXPLICIT_MENTION_PATTERN.finditer(content):
        entity_type = ENTITY_TYPE_BY_PLURAL.get(match.group("plural"))
        if entity_type is None:
            continue
        target_id = match.group("id")
        if target_id == note.id or target_id in seen_ids:
            continue
        target = db.session.get(Entity, target_id)
        if target is None or target.type != entity_type or target.lifecycle == "deleted":
            continue
        seen_ids.add(target_id)
        link = _create_entity_link(note, target, "mentions", 1.0, "explicit mention", source="user")
        if link is not None:
            _write_event(
                target,
                "relationship_added",
                new_value=link.to_dict(),
                actor="user",
                reason="explicit mention",
                source_note_id=note.id,
            )
            applied.append({
                "type": "relationship_added",
                "source_entity_id": note.id,
                "target_entity_id": target.id,
                "relationship_type": "mentions",
                "confidence": 1.0,
            })
    return applied


def _create_entity_link(source_entity, target_entity, relationship_type, confidence, evidence, source="ai"):
    existing = EntityLink.query.filter_by(
        source_entity_id=source_entity.id,
        target_entity_id=target_entity.id,
        relationship_type=relationship_type,
    ).first()
    if existing is not None:
        return None
    if relationship_type == "blocks" and _creates_blocks_cycle(source_entity.id, target_entity.id):
        return None
    link = EntityLink(
        source_entity_id=source_entity.id,
        target_entity_id=target_entity.id,
        relationship_type=relationship_type,
        source=source,
        confidence=confidence,
        evidence=evidence,
    )
    db.session.add(link)
    db.session.flush()

    # When a note is linked to any non-note entity, queue a summarize job so
    # the entity's summary reflects the new information, regardless of link direction.
    if getattr(source_entity, "type", None) == "note" and getattr(target_entity, "type", None) != "note":
        from services.v4_summarization import queue_summarize_if_needed
        queue_summarize_if_needed(target_entity.id, has_existing_summary=bool(target_entity.ai_summary))
    elif getattr(target_entity, "type", None) == "note" and getattr(source_entity, "type", None) != "note":
        from services.v4_summarization import queue_summarize_if_needed
        queue_summarize_if_needed(source_entity.id, has_existing_summary=bool(source_entity.ai_summary))

    # When a task is parent-linked to a project, advance the project's
    # updated_at so surfaces reflect current activity.
    if (relationship_type == "parent"
        and getattr(source_entity, "type", None) == "task"
        and getattr(target_entity, "type", None) == "project"):
        target_entity.updated_at = datetime.now(timezone.utc)

    return link


def _find_existing_entity(entity_type, title):
    return Entity.query.filter(
        Entity.type == entity_type,
        func.lower(Entity.title) == title.lower(),
        Entity.lifecycle != "deleted",
    ).first()


def _default_relationship_type(entity_type):
    if entity_type == "person":
        return "mentions"
    return "related"


def _is_create_suggestion_operation(operation_type):
    return operation_type in {"create_entity", "create_new_entity"}


def _accepted_suggestion_link(source_note, entity, payload=None):
    payload = payload or {}
    target_entity_id = payload.get("target_entity_id")
    relationship_type = payload.get("relationship_type")
    if target_entity_id and relationship_type == "derived_from" and entity.type == "task":
        target = db.session.get(Entity, target_entity_id)
        if target is not None and target.lifecycle != "deleted" and target.id != entity.id:
            return entity, target, relationship_type
    if entity.type == "task":
        return entity, source_note, "derived_from"
    if entity.type == "person":
        return source_note, entity, "mentions"
    if entity.type == "resource":
        return source_note, entity, "references"
    return source_note, entity, "related"


def _candidate_link_endpoints(source_note, entity, relationship_type):
    if source_note.type == "note" and entity.type == "task" and relationship_type == "derived_from":
        return entity, source_note
    return source_note, entity


def _candidate_value(candidate, key):
    if isinstance(candidate, dict):
        value = candidate.get(key)
    else:
        value = candidate
    return _clean_text(value)


def _candidate_confidence(candidate):
    if isinstance(candidate, dict):
        value = candidate.get("confidence")
    else:
        value = None
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _apply_capture_intent(note, extraction):
    ai_meta = dict(note.ai_meta or {})
    intent, confidence = _capture_intent(note.content or "", extraction or {})
    ai_meta["intent"] = intent
    ai_meta["intent_confidence"] = confidence
    note.ai_meta = ai_meta
    flag_modified(note, "ai_meta")


def _capture_intent(content, extraction):
    explicit_intent = extraction.get("intent")
    explicit_confidence = _candidate_confidence({"confidence": extraction.get("intent_confidence")})
    if explicit_intent in CAPTURE_INTENTS:
        return explicit_intent, explicit_confidence or _candidate_confidence(extraction)

    lowered = (content or "").strip().casefold()
    entities = extraction.get("entities") or []
    links = extraction.get("links") or []
    entity_types = {item.get("type") for item in entities}
    has_tasks = "task" in entity_types
    has_resources = "resource" in entity_types or any(link.get("relationship_type") == "references" for link in links)
    has_follow_up = any(item.get("follow_up_at") for item in entities)
    has_assignee = any(item.get("assigned_to") for item in entities)
    has_blocker = any(link.get("relationship_type") == "blocks" for link in links)

    if lowered in {"test", "testing", "asdf", "n/a", "na"}:
        return "junk", 0.78
    if has_blocker or any(phrase in lowered for phrase in ("blocked by", "blocked on", "waiting on", "stuck on", "dependency")):
        return "blocker", 0.82
    if has_assignee or (has_tasks and any(phrase in lowered for phrase in ("owner:", "assigned to", "delegate to", "have ", "ask "))):
        return "delegation", 0.8
    if has_follow_up or any(phrase in lowered for phrase in ("follow up", "follow-up", "circle back", "remind me", "check back")):
        return "follow_up", 0.8
    if has_resources or any(phrase in lowered for phrase in ("http://", "https://", "doc:", "see also", "reference", "read this", "link:")):
        return "reference", 0.76
    if has_tasks or any(phrase in lowered for phrase in ("todo", "to do", "next steps", "action items", "we should", "need to", "please", "ship ", "draft ", "review ", "send ", "schedule ")):
        return "task_signal", 0.74
    if any(phrase in lowered for phrase in ("update:", "fyi", "for visibility", "progress", "shipped", "completed", "done with", "status update")):
        return "update", 0.72
    if len(lowered) < 12 and not entities and not links:
        return "junk", 0.55
    return "note", 0.6


def _sort_inbox_notes(notes, pending_counts, mode):
    return sorted(
        notes,
        key=lambda note: _inbox_sort_key(note, pending_counts.get(note.id, 0), mode),
    )


def _inbox_sort_key(note, pending_suggestion_count, mode):
    ai_meta = note.ai_meta or {}
    intent = ai_meta.get("intent") if ai_meta.get("intent") in CAPTURE_INTENTS else "note"
    intent_rank = INBOX_INTENT_PRIORITY.get(intent, INBOX_INTENT_PRIORITY["note"])
    updated_at = note.updated_at or note.created_at or datetime.min.replace(tzinfo=timezone.utc)
    created_at = note.created_at or updated_at
    timestamp_rank = -updated_at.timestamp()
    created_rank = -created_at.timestamp()

    if mode == "needs_review":
        if note.ai_status == "failed":
            review_rank = 0
        elif pending_suggestion_count > 0:
            review_rank = 1
        elif note.ai_status == "pending":
            review_rank = 2
        else:
            review_rank = 3
        return (review_rank, intent_rank, -pending_suggestion_count, timestamp_rank, created_rank)

    return (intent_rank, created_rank, timestamp_rank)


def _append_capture_suggestion(note, candidate, action, entity_type, relationship_type, confidence, evidence, suggestions, suggestion_type, operation_type, payload, reason):
    if not _should_emit_capture_suggestion(note, candidate, action, entity_type, relationship_type, confidence):
        return
    suggestion = _create_suggestion(
        note,
        suggestion_type=suggestion_type,
        operation_type=operation_type,
        payload=payload,
        confidence=confidence,
        reason=reason,
    )
    if suggestion is not None:
        suggestions.append(suggestion.to_dict())


def _should_emit_capture_suggestion(note, candidate, action, entity_type, relationship_type, confidence):
    intent = ((note.ai_meta or {}).get("intent") or "note")
    if intent == "junk" and confidence < INTENT_SUGGESTION_CONFIDENCE_FLOOR:
        return False
    if (
        intent == "reference"
        and entity_type == "task"
        and action in {"new", "update"}
        and confidence < INTENT_SUGGESTION_CONFIDENCE_FLOOR
    ):
        return False
    if (
        entity_type == "task"
        and action == "new"
        and confidence < AUTO_CREATE_ENTITY_CONFIDENCE
        and _task_candidate_looks_tentative(candidate)
    ):
        return False
    return True


def _task_candidate_looks_tentative(candidate):
    """Return True for obviously tentative task phrasing that should stay out of review.

    We still allow concrete low-confidence tasks like "Follow up with Henry" or
    "Review the rollout doc" to surface for review, but we suppress hedged
    wording that usually represents musing rather than an actionable task.
    """
    title = (_candidate_value(candidate, "title") or "").casefold()
    if not title:
        return False

    tentative_prefixes = (
        "maybe ",
        "possibly ",
        "perhaps ",
        "might ",
        "could ",
        "consider ",
        "think about ",
        "look into ",
        "we should maybe ",
        "let's maybe ",
    )
    return title.startswith(tentative_prefixes)


def _expire_stale_suggestion_if_needed(suggestion):
    source_note = db.session.get(Entity, suggestion.source_entity_id)
    payload = suggestion.payload or {}
    relationship_type = payload.get("relationship_type")

    if source_note is None or source_note.lifecycle != "active":
        return _expire_suggestion(suggestion, None, "source note is no longer active")

    if suggestion.operation_type == "link_existing":
        target = db.session.get(Entity, payload.get("target_entity_id"))
        if target is None or target.lifecycle == "deleted":
            return _expire_suggestion(suggestion, source_note, "target entity no longer exists")
        if _relationship_exists_between(source_note, target, relationship_type or _default_relationship_type(target.type)):
            return _expire_suggestion(suggestion, source_note, "relationship already exists")
        return None

    if suggestion.operation_type == "update_entity":
        target = db.session.get(Entity, payload.get("target_entity_id"))
        if target is None or target.lifecycle == "deleted":
            return _expire_suggestion(suggestion, source_note, "target entity no longer exists")
        fields = payload.get("fields") or {}
        link_exists = _relationship_exists_between(
            source_note,
            target,
            relationship_type or _default_relationship_type(target.type),
        )
        if not _suggested_fields_would_change(target, fields) and link_exists:
            return _expire_suggestion(suggestion, source_note, "suggestion no longer changes the target")
        return None

    if _is_create_suggestion_operation(suggestion.operation_type):
        entity_type = payload.get("type")
        title = _clean_text(payload.get("title"))
        if not entity_type or not title:
            return _expire_suggestion(suggestion, source_note, "suggestion payload is incomplete")
        existing = _find_existing_entity(entity_type, title)
        if existing is None or existing.lifecycle == "deleted":
            return None
        rel_type = relationship_type or _default_relationship_type(entity_type)
        if _relationship_exists_between(source_note, existing, rel_type):
            return _expire_suggestion(suggestion, source_note, "matching entity and relationship already exist")
    return None


def _expire_suggestion(suggestion, source_note, reason):
    suggestion.status = "expired"
    suggestion.resolved_at = datetime.utcnow()
    if source_note is not None:
        _write_event(
            source_note,
            "suggestion_expired",
            new_value={"suggestion_id": suggestion.id},
            actor="agent:v4-reconcile",
            confidence=suggestion.confidence,
            reason=reason,
        )
    return suggestion.to_dict()


def _suggested_fields_would_change(target_entity, fields):
    if not isinstance(fields, dict):
        return False
    if "status" in fields and fields["status"] != target_entity.status:
        return True
    if "due_at" in fields:
        due_at, _ = _parse_datetime_or_error(fields["due_at"])
        if due_at != target_entity.due_at:
            return True
    if "follow_up_at" in fields:
        follow_up_at, _ = _parse_datetime_or_error(fields["follow_up_at"])
        if follow_up_at != target_entity.follow_up_at:
            return True
    return False


def _relationship_exists_between(source_note, entity, relationship_type):
    link_source, link_target = _candidate_link_endpoints(source_note, entity, relationship_type)
    return EntityLink.query.filter_by(
        source_entity_id=link_source.id,
        target_entity_id=link_target.id,
        relationship_type=relationship_type,
    ).first() is not None


def _suggestion_fingerprint(suggestion_type, operation_type, payload):
    normalized = {
        "suggestion_type": suggestion_type,
        "operation_type": operation_type,
        "payload": _normalized_suggestion_payload(operation_type, payload or {}),
    }
    raw = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _normalized_suggestion_payload(operation_type, payload):
    if _is_create_suggestion_operation(operation_type):
        return {
            "type": _clean_text(payload.get("type")),
            "title": _clean_text(payload.get("title")),
            "content": _clean_text(payload.get("content")),
            "due_at": _clean_text(payload.get("due_at")),
            "follow_up_at": _clean_text(payload.get("follow_up_at")),
            "assigned_to": _clean_text(payload.get("assigned_to")),
            "relationship_type": _clean_text(payload.get("relationship_type")),
            "target_entity_id": _clean_text(payload.get("target_entity_id")),
        }
    if operation_type == "update_entity":
        fields = payload.get("fields") or {}
        return {
            "target_entity_id": _clean_text(payload.get("target_entity_id")),
            "relationship_type": _clean_text(payload.get("relationship_type")),
            "assigned_to": _clean_text(payload.get("assigned_to")),
            "fields": {
                "status": _clean_text(fields.get("status")),
                "due_at": _clean_text(fields.get("due_at")),
                "follow_up_at": _clean_text(fields.get("follow_up_at")),
            },
        }
    return {
        "target_entity_id": _clean_text(payload.get("target_entity_id")),
        "relationship_type": _clean_text(payload.get("relationship_type")),
    }


def _existing_pending_suggestion(fingerprint):
    return AiSuggestion.query.filter(
        AiSuggestion.status == "pending",
        AiSuggestion.payload["_fingerprint"].as_string() == fingerprint,
    ).first()


def _recently_resolved_duplicate(fingerprint, confidence):
    cutoff = datetime.now(timezone.utc) - timedelta(days=SUGGESTION_DUPLICATE_MEMORY_DAYS)
    existing = AiSuggestion.query.filter(
        AiSuggestion.status.in_(("dismissed", "expired")),
        AiSuggestion.updated_at >= cutoff,
        AiSuggestion.payload["_fingerprint"].as_string() == fingerprint,
    ).order_by(AiSuggestion.updated_at.desc()).first()
    if existing is None:
        return False
    previous_confidence = existing.confidence or 0.0
    next_confidence = confidence or 0.0
    return next_confidence <= previous_confidence + 0.05


def _can_auto_create_entity(entity_type, confidence, top_match_score=0.0):
    if entity_type not in RISKY_ENTITY_CREATION_TYPES:
        return False
    # Projects and areas are low-volume and expensive to dedupe after the
    # fact — creation always goes through the review queue.
    if entity_type in SUGGEST_ONLY_CREATION_TYPES:
        return False
    # A plausible near-duplicate exists: route to review instead of creating
    # a sibling, regardless of how confident the model is that this is "new".
    if (top_match_score or 0.0) >= NEAR_DUPLICATE_SCORE:
        return False
    return confidence >= AUTO_CREATE_ENTITY_CONFIDENCE


def _reconciliation_confidence(candidate, decision):
    candidate_confidence = _candidate_confidence(candidate)
    decision_confidence = _candidate_confidence(decision)
    if decision_confidence <= 0:
        return candidate_confidence
    if candidate_confidence <= 0:
        return decision_confidence
    return min(candidate_confidence, decision_confidence)


def _find_duplicate_capture_note(content):
    return Entity.query.filter(
        Entity.type == "note",
        Entity.lifecycle != "deleted",
        Entity.content == content,
    ).order_by(Entity.updated_at.desc(), Entity.created_at.desc()).first()


def _apply_assignee_and_record(note, entity, assigned_to, confidence, evidence, applied_changes, source, actor):
    person, link, person_created = _apply_assignee(note, entity, assigned_to, confidence, evidence, source=source, actor=actor)
    if person_created:
        _write_event(
            person,
            "created",
            new_value=person.to_dict(),
            actor=actor,
            confidence=confidence,
            reason=evidence,
            source_note_id=note.id,
        )
        applied_changes.append({
            "type": "entity_created",
            "entity_id": person.id,
            "entity_type": person.type,
            "title": person.title,
            "confidence": confidence,
        })
    if link is not None:
        applied_changes.append({
            "type": "relationship_added",
            "target_entity_id": person.id,
            "relationship_type": "assigned_to",
            "confidence": confidence,
        })


def _apply_assignee(note, entity, assigned_to, confidence, evidence, source, actor):
    assignee_name = _clean_text(assigned_to)
    if assignee_name is None or entity.type not in {"task", "project"}:
        return None, None, False

    person = _find_existing_entity("person", assignee_name)
    person_created = False
    if person is None:
        person_source = "ai_capture" if source == "ai" else "ai_suggestion"
        person = Entity(
            type="person",
            title=assignee_name,
            content=None,
            status=DEFAULT_STATUS["person"],
            lifecycle="active",
            source=person_source,
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        db.session.add(person)
        db.session.flush()
        _queue_embed_job(person.id, "assignee_auto_create")
        person_created = True

    link = _create_entity_link(
        entity,
        person,
        "assigned_to",
        confidence,
        evidence,
        source=source,
    )
    if link is not None:
        _write_event(
            entity,
            "relationship_added",
            new_value=link.to_dict(),
            actor=actor,
            confidence=confidence,
            reason=evidence,
        )
        if entity.type == "task" and entity.follow_up_at is None and not _is_owner(assignee_name, person.id):
            cadence_days = _delegation_cadence_days(person.id)
            entity.follow_up_at = _add_working_days(datetime.now(timezone.utc), cadence_days)
            _write_event(
                entity,
                "ai_updated",
                old_value={"follow_up_at": None},
                new_value={"follow_up_at": entity.follow_up_at.isoformat()},
                actor=actor,
                confidence=confidence,
                reason="delegation cadence",
                source_note_id=note.id if note is not None else None,
            )
    return person, link, person_created


def _queue_embed_job(entity_id, reason):
    db.session.add(Job(
        job_type="embed",
        entity_id=entity_id,
        payload={"entity_id": entity_id, "reason": reason},
    ))


def _clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _archive_incoming_activity_updates(entity):
    activity_notes = (
        Entity.query.join(
            EntityLink,
            (EntityLink.source_entity_id == Entity.id) & (EntityLink.target_entity_id == entity.id),
        )
        .filter(
            Entity.type == "note",
            Entity.source == "activity_update",
            EntityLink.relationship_type == "activity_update",
            Entity.lifecycle == "active",
        )
        .all()
    )
    for note in activity_notes:
        note.lifecycle = "archived"
        _write_event(
            note,
            "archived",
            old_value={"lifecycle": "active"},
            new_value={"lifecycle": "archived"},
        )


def _delete_incoming_activity_updates(entity):
    activity_note_ids = (
        Entity.query.join(
            EntityLink,
            (EntityLink.source_entity_id == Entity.id) & (EntityLink.target_entity_id == entity.id),
        )
        .filter(
            Entity.type == "note",
            Entity.source == "activity_update",
            EntityLink.relationship_type == "activity_update",
        )
        .with_entities(Entity.id)
        .all()
    )
    for (note_id,) in activity_note_ids:
        db.session.delete(db.session.get(Entity, note_id))
