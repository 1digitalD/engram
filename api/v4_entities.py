"""Engram v4 canonical entity API."""

from datetime import datetime, time, timezone, timedelta
import hashlib
import json

from flask import jsonify, request
from sqlalchemy import func, or_
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import selectinload

from api import api_v4_bp
from extensions import db
from models import AiSuggestion, Entity, EntityEvent, EntityLink, EntityTag, Job, Tag
from services.v4_attention import attention_for_entity

STATUS_BY_TYPE = {
    "note": ["active", "processed", "archived"],
    "task": ["open", "in_progress", "waiting", "blocked", "done", "cancelled"],
    "project": ["active", "on_hold", "completed", "cancelled"],
    "area": ["active", "archived"],
    "person": ["active", "archived"],
    "resource": ["active", "archived"],
}

ENTITY_TYPES = {"note", "task", "project", "area", "resource", "person"}
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
AUTO_APPLY_CONFIDENCE = 0.8
AUTO_CREATE_ENTITY_CONFIDENCE = 0.9
RISKY_ENTITY_CREATION_TYPES = {"task", "project", "area", "resource", "person"}
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


@api_v4_bp.route("/health", methods=["GET"])
def health():
    db.session.execute(db.text("SELECT 1"))
    return jsonify({"status": "ok", "api": "v4"})


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
    return jsonify({"data": [row.to_dict() for row in rows]})


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


@api_v4_bp.route("/today", methods=["GET"])
def today():
    now = datetime.now(timezone.utc)
    start_of_today = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    end_of_today = datetime.combine(now.date(), time.max, tzinfo=timezone.utc)

    overdue = (
        _entity_query()
        .filter(
            Entity.lifecycle == "active",
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
            Entity.follow_up_at.isnot(None),
            Entity.follow_up_at > end_of_today,
            Entity.follow_up_at <= end_of_week,
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(Entity.follow_up_at.asc())
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

    return jsonify({
        "overdue": [_entity_with_attention(entity) for entity in overdue],
        "due_today": [_entity_with_attention(entity) for entity in due_today],
        "overdue_follow_ups": [_entity_with_attention(entity) for entity in overdue_follow_ups],
        "follow_ups": [_entity_with_attention(entity) for entity in follow_ups],
        "upcoming_follow_ups": [_entity_with_attention(entity) for entity in upcoming_follow_ups],
        "blocked_tasks": [_entity_with_attention(entity) for entity in blocked_tasks],
        "waiting_tasks": [_entity_with_attention(entity) for entity in waiting_tasks],
        "projects_without_open_tasks": [
            _entity_with_attention(entity, context=["project_without_open_tasks"])
            for entity in projects_without_open_tasks
        ],
        "recent_notes": [_entity_with_attention(entity) for entity in recent_notes],
        "pending_suggestions": [suggestion.to_dict() for suggestion in pending_suggestions],
        # Retained for any external callers; matches the new bucket structure semantically.
        "blocked_or_waiting_tasks": [_entity_with_attention(e) for e in (blocked_tasks + waiting_tasks)],
    })


@api_v4_bp.route("/inbox", methods=["GET"])
def inbox():
    limit = max(1, min(request.args.get("limit", 30, type=int), 200))
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

    needs_review = (
        _entity_query()
        .filter(
            Entity.type == "note",
            Entity.lifecycle == "active",
            unresolved_review,
            or_(
                Entity.ai_status == "pending",
                Entity.ai_status == "failed",
                Entity.id.in_(notes_with_suggestions) if notes_with_suggestions else Entity.id.is_(None),
            ),
        )
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


def _entity_with_attention(entity, *, pending_suggestion_count=0, context=None):
    data = entity.to_dict()
    data["attention"] = attention_for_entity(
        entity,
        pending_suggestion_count=pending_suggestion_count,
        context=context,
    )
    return data


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
    return jsonify({"entity": entity.to_dict(), "sections": _relationship_detail_sections(entity)})


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
        title=_title_from_content(content),
        content=content,
        status="active",
        source="activity_update",
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
    return note, True


@api_v4_bp.route("/entities/<entity_id>/activity_updates", methods=["POST"])
def create_activity_update(entity_id):
    target = db.session.get(Entity, entity_id)
    if target is None:
        return _error("entity not found", 404)

    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return _error("content is required")

    note, created = _create_activity_update_note(target, content, actor="user")
    if note is None:
        return _error(
            f"maximum {MAX_ACTIVITY_UPDATES_PER_TARGET} activity updates per entity",
            409,
        )
    if not created:
        return jsonify({"data": note.to_dict(), "skipped": True, "reason": "duplicate within 24h"})

    db.session.commit()

    return jsonify({"data": _load_entity(note.id).to_dict()}), 201


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
    if suggestion.operation_type != "create_entity":
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
    if suggestion.operation_type != "create_entity":
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

    link_source, link_target, relationship_type = _accepted_suggestion_link(source_note, entity)
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

    unsupported = set(fields) - {"status", "due_at", "follow_up_at"}
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


def _run_basic_capture_extraction(note, mode):
    from services.v4_extraction import extract_capture_candidates

    return extract_capture_candidates(note.content or "", mode=mode)


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
    # project is added separately by _link_task_to_note_projects.
    if action == "new" and entity_type == "task":
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
    if _can_auto_create_entity(entity_type, confidence):
        entity = _auto_create_entity(
            entity_type=entity_type,
            title=title,
            content=content,
            due_at=decision.get("fields", {}).get("due_at") or _candidate_value(candidate, "due_at"),
            follow_up_at=decision.get("fields", {}).get("follow_up_at") or _candidate_value(candidate, "follow_up_at"),
        )
        link_source, link_target = _candidate_link_endpoints(note, entity, relationship_type)
        link = _create_entity_link(link_source, link_target, relationship_type, confidence, evidence)
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


def _create_entity_link(source_entity, target_entity, relationship_type, confidence, evidence, source="ai"):
    existing = EntityLink.query.filter_by(
        source_entity_id=source_entity.id,
        target_entity_id=target_entity.id,
        relationship_type=relationship_type,
    ).first()
    if existing is not None:
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


def _accepted_suggestion_link(source_note, entity):
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
    return True


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

    if suggestion.operation_type == "create_entity":
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
    if operation_type == "create_entity":
        return {
            "type": _clean_text(payload.get("type")),
            "title": _clean_text(payload.get("title")),
            "content": _clean_text(payload.get("content")),
            "due_at": _clean_text(payload.get("due_at")),
            "follow_up_at": _clean_text(payload.get("follow_up_at")),
            "assigned_to": _clean_text(payload.get("assigned_to")),
            "relationship_type": _clean_text(payload.get("relationship_type")),
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


def _can_auto_create_entity(entity_type, confidence):
    return entity_type in RISKY_ENTITY_CREATION_TYPES and confidence >= AUTO_CREATE_ENTITY_CONFIDENCE


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
