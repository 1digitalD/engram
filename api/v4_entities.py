"""Engram v4 canonical entity API."""

from datetime import datetime, time, timezone

from flask import jsonify, request
from sqlalchemy import func, or_
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import selectinload

from api import api_v4_bp
from extensions import db
from models import AiSuggestion, Entity, EntityEvent, EntityLink, EntityTag, Job, Tag


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
}
AUTO_APPLY_CONFIDENCE = 0.8
RISKY_ENTITY_CREATION_TYPES = {"task", "project", "area", "resource", "person"}


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
    status = request.args.get("status")
    lifecycle = request.args.get("lifecycle")
    limit = max(1, min(request.args.get("limit", 50, type=int), 200))

    if entity_type:
        if entity_type not in ENTITY_TYPES:
            return _error(f"invalid entity type: {entity_type}")
        query = query.filter(Entity.type == entity_type)
    if status:
        query = query.filter(Entity.status == status)
    if lifecycle:
        if lifecycle not in VALID_LIFECYCLE:
            return _error(f"invalid lifecycle: {lifecycle}")
        query = query.filter(Entity.lifecycle == lifecycle)
    else:
        query = query.filter(Entity.lifecycle != "deleted")

    rows = query.order_by(Entity.updated_at.desc(), Entity.created_at.desc()).limit(limit).all()
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

    return jsonify({
        "overdue": [entity.to_dict() for entity in overdue],
        "due_today": [entity.to_dict() for entity in due_today],
        "overdue_follow_ups": [entity.to_dict() for entity in overdue_follow_ups],
        "follow_ups": [entity.to_dict() for entity in follow_ups],
        "blocked_tasks": [entity.to_dict() for entity in blocked_tasks],
        "waiting_tasks": [entity.to_dict() for entity in waiting_tasks],
        "projects_without_open_tasks": [entity.to_dict() for entity in projects_without_open_tasks],
        "pending_suggestions": [suggestion.to_dict() for suggestion in pending_suggestions],
        # Retained for any external callers; matches the new bucket structure semantically.
        "blocked_or_waiting_tasks": [e.to_dict() for e in (blocked_tasks + waiting_tasks)],
    })


@api_v4_bp.route("/inbox", methods=["GET"])
def inbox():
    limit = max(1, min(request.args.get("limit", 30, type=int), 200))

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
            or_(
                Entity.ai_status == "pending",
                Entity.ai_status == "failed",
                Entity.id.in_(notes_with_suggestions) if notes_with_suggestions else Entity.id.is_(None),
            ),
        )
        .order_by(Entity.updated_at.desc(), Entity.created_at.desc())
        .limit(limit)
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
        .limit(limit)
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

    def annotate(note):
        d = note.to_dict()
        d["pending_suggestion_count"] = pending_counts.get(note.id, 0)
        return d

    return jsonify({
        "needs_review": [annotate(n) for n in needs_review],
        "recent": [annotate(n) for n in recent],
    })


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
        _write_event(
            entity,
            "archived",
            old_value={"lifecycle": old_snapshot["lifecycle"]},
            new_value={"lifecycle": entity.lifecycle},
        )
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


@api_v4_bp.route("/suggestions", methods=["GET"])
def list_suggestions():
    status = request.args.get("status", "pending")
    query = AiSuggestion.query.options(selectinload(AiSuggestion.source_entity))
    if status != "all":
        query = query.filter(AiSuggestion.status == status)
    rows = query.order_by(AiSuggestion.created_at.desc()).limit(200).all()

    def _serialize(s):
        d = s.to_dict()
        d["source_note_title"] = s.source_entity.title if s.source_entity else None
        return d

    return jsonify({"data": [_serialize(row) for row in rows]})


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
        "relationship": link.to_dict() if link is not None else None,
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

    link = _create_entity_link(
        source_entity,
        target_entity,
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
        _write_event(source_entity, "relationship_added", old_value=old_value, new_value=link.to_dict())
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


def _project_has_open_task(entity_id):
    open_statuses = {"open", "in_progress", "waiting", "blocked"}
    links = EntityLink.query.filter_by(target_entity_id=entity_id, relationship_type="parent").all()
    for link in links:
        task = db.session.get(Entity, link.source_entity_id)
        if task is not None and task.type == "task" and task.lifecycle == "active" and task.status in open_statuses:
            return True
    return False


def _relationship_detail_sections(entity):
    links = (
        EntityLink.query.filter(
            (EntityLink.source_entity_id == entity.id) | (EntityLink.target_entity_id == entity.id)
        )
        .order_by(EntityLink.created_at.asc())
        .all()
    )
    builders = {
        "task": _task_detail_sections,
        "project": _project_detail_sections,
        "area": _area_detail_sections,
        "note": _note_detail_sections,
        "person": _person_detail_sections,
        "resource": _resource_detail_sections,
    }
    return builders[entity.type](entity, links)


def _task_detail_sections(entity, links):
    return [
        _section("project", "Project", _link_items(entity, links, "outgoing", {"parent"}, {"project"})),
        _section("area", "Area", _link_items(entity, links, "outgoing", {"parent"}, {"area"})),
        _section("people", "People", _link_items(entity, links, "outgoing", {"assigned_to", "mentions"}, {"person"})),
        _section("source_notes", "Source Notes", _link_items(entity, links, "outgoing", {"derived_from"}, {"note"})),
        _section("related_notes", "Related Notes", _link_items(entity, links, "both", {"related"}, {"note"})),
        _section("resources", "Resources", _link_items(entity, links, "outgoing", {"references", "related"}, {"resource"})),
        _section("blocking", "Blocking / Blocked By", _link_items(entity, links, "both", {"blocks"}, {"task"})),
        _section("related_tasks", "Related Tasks", _link_items(entity, links, "both", {"related"}, {"task"})),
    ]


def _project_detail_sections(entity, links):
    return [
        _section("area", "Area", _link_items(entity, links, "outgoing", {"parent"}, {"area"})),
        _section(
            "open_tasks",
            "Open Tasks",
            _link_items(entity, links, "incoming", {"parent"}, {"task"}, exclude_statuses={"done", "cancelled"}),
        ),
        _section(
            "completed_tasks",
            "Completed Tasks",
            _link_items(entity, links, "incoming", {"parent"}, {"task"}, statuses={"done"}),
        ),
        _section("notes", "Notes", _link_items(entity, links, "both", {"related", "mentions", "references"}, {"note"})),
        _section("resources", "Resources", _link_items(entity, links, "both", {"references", "related"}, {"resource"})),
        _section("people", "People", _link_items(entity, links, "both", {"assigned_to", "mentions", "related"}, {"person"})),
        _section("related_projects", "Related Projects", _link_items(entity, links, "both", {"related"}, {"project"})),
        _section("blocked_by_blocks", "Blocked By / Blocks", _link_items(entity, links, "both", {"blocks"}, {"project"})),
    ]


def _area_detail_sections(entity, links):
    return [
        _section("projects", "Projects", _link_items(entity, links, "incoming", {"parent", "related"}, {"project"})),
        _section("tasks", "Tasks", _link_items(entity, links, "incoming", {"parent", "related"}, {"task"})),
        _section("notes", "Notes", _link_items(entity, links, "both", {"related", "mentions"}, {"note"})),
        _section("resources", "Resources", _link_items(entity, links, "both", {"references", "related"}, {"resource"})),
        _section("people", "People", _link_items(entity, links, "both", {"mentions", "assigned_to", "related"}, {"person"})),
    ]


def _note_detail_sections(entity, links):
    return [
        _section("projects", "Projects", _link_items(entity, links, "outgoing", {"related", "mentions"}, {"project"})),
        _section("areas", "Areas", _link_items(entity, links, "outgoing", {"related", "mentions"}, {"area"})),
        _section("people_mentioned", "People Mentioned", _link_items(entity, links, "outgoing", {"mentions"}, {"person"})),
        _section("derived_tasks", "Derived Tasks", _link_items(entity, links, "incoming", {"derived_from"}, {"task"})),
        _section("referenced_resources", "Referenced Resources", _link_items(entity, links, "outgoing", {"references"}, {"resource"})),
        _section("related_notes", "Related Notes", _link_items(entity, links, "both", {"related"}, {"note"})),
    ]


def _person_detail_sections(entity, links):
    return [
        _section("assigned_tasks", "Assigned Tasks", _link_items(entity, links, "incoming", {"assigned_to"}, {"task"})),
        _section("mentioned_in_notes", "Mentioned In Notes", _link_items(entity, links, "incoming", {"mentions"}, {"note"})),
        _section("projects", "Projects", _link_items(entity, links, "both", {"assigned_to", "mentions", "related"}, {"project"})),
        _section("resources", "Resources", _link_items(entity, links, "both", {"references", "related"}, {"resource"})),
        _section("related_people", "Related People", _link_items(entity, links, "both", {"related"}, {"person"})),
    ]


def _resource_detail_sections(entity, links):
    return [
        _section("referenced_by_notes", "Referenced By Notes", _link_items(entity, links, "incoming", {"references"}, {"note"})),
        _section("projects", "Projects", _link_items(entity, links, "both", {"references", "related"}, {"project"})),
        _section("tasks", "Tasks", _link_items(entity, links, "both", {"references", "related"}, {"task"})),
        _section("areas", "Areas", _link_items(entity, links, "both", {"references", "related"}, {"area"})),
        _section("people", "People", _link_items(entity, links, "both", {"references", "related"}, {"person"})),
        _section("related_resources", "Related Resources", _link_items(entity, links, "both", {"related"}, {"resource"})),
    ]


def _section(key, title, items):
    return {"key": key, "title": title, "items": items}


def _link_items(entity, links, direction, relationship_types, related_types, statuses=None, exclude_statuses=None):
    items = []
    for link in links:
        related_entity, resolved_direction = _related_entity_for_link(entity, link, direction)
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


def _related_entity_for_link(entity, link, direction):
    if direction in {"outgoing", "both"} and link.source_entity_id == entity.id:
        return db.session.get(Entity, link.target_entity_id), "outgoing"
    if direction in {"incoming", "both"} and link.target_entity_id == entity.id:
        return db.session.get(Entity, link.source_entity_id), "incoming"
    return None, None


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


def _write_event(entity, event_type, old_value=None, new_value=None, actor="user", confidence=None, reason=None):
    db.session.add(
        EntityEvent(
            entity_id=entity.id,
            event_type=event_type,
            actor=actor,
            old_value=old_value,
            new_value=new_value,
            confidence=confidence,
            reason=reason,
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
        )
    elif ai_title and title_auto:
        # Title set but no summary — still need to persist ai_meta if we touched it.
        note.ai_meta = ai_meta
        flag_modified(note, "ai_meta")

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
    confidence = _candidate_confidence(candidate)
    evidence = _candidate_value(candidate, "evidence")
    entity_type = _candidate_value(candidate, "type")
    title = _candidate_value(candidate, "title")
    relationship_type = decision.get("relationship_type") or _default_relationship_type(entity_type)
    if relationship_type not in RELATIONSHIP_TYPES:
        relationship_type = _default_relationship_type(entity_type)

    if action in ("update", "link"):
        target_id = decision.get("target_id")
        target = db.session.get(Entity, target_id) if target_id else None
        if target is None:
            # Match is gone or id was hallucinated — fall through to "new"
            action = "new"

    if action == "update":
        if confidence >= AUTO_APPLY_CONFIDENCE:
            _apply_entity_update(note, target, decision, relationship_type, confidence, evidence, applied_changes)
        else:
            suggestions.append(_create_suggestion(
                note,
                suggestion_type=f"update_{entity_type}",
                operation_type="update_entity",
                payload={
                    "target_entity_id": target.id,
                    "target_type": entity_type,
                    "title": target.title,
                    "fields": decision.get("fields") or {},
                    "relationship_type": relationship_type,
                    "evidence": evidence,
                },
                confidence=confidence,
                reason=decision.get("reason"),
            ).to_dict())
        return

    if action == "link":
        if confidence >= AUTO_APPLY_CONFIDENCE:
            link = _create_entity_link(note, target, relationship_type, confidence, evidence)
            if link is not None:
                applied_changes.append({
                    "type": "relationship_added",
                    "target_entity_id": target.id,
                    "relationship_type": relationship_type,
                    "confidence": confidence,
                })
                _write_event(note, "relationship_added", new_value=link.to_dict(), actor="agent:v4-capture", confidence=confidence, reason=evidence)
        else:
            suggestions.append(_create_suggestion(
                note,
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
                confidence=confidence,
                reason=decision.get("reason"),
            ).to_dict())
        return

    # action == "new"
    if not title or not entity_type:
        return
    content = _candidate_value(candidate, "content")
    if confidence >= AUTO_APPLY_CONFIDENCE:
        entity = _auto_create_entity(
            entity_type=entity_type,
            title=title,
            content=content,
            due_at=decision.get("fields", {}).get("due_at") or _candidate_value(candidate, "due_at"),
            follow_up_at=decision.get("fields", {}).get("follow_up_at") or _candidate_value(candidate, "follow_up_at"),
        )
        link = _create_entity_link(note, entity, relationship_type, confidence, evidence)
        _write_event(entity, "created", new_value=entity.to_dict(), actor="agent:v4-capture", confidence=confidence, reason=evidence)
        applied_changes.append({
            "type": "entity_created",
            "entity_id": entity.id,
            "entity_type": entity_type,
            "title": title,
            "confidence": confidence,
        })
        if link is not None:
            _write_event(note, "relationship_added", new_value=link.to_dict(), actor="agent:v4-capture", confidence=confidence, reason=evidence)
            applied_changes.append({
                "type": "relationship_added",
                "target_entity_id": entity.id,
                "relationship_type": relationship_type,
                "confidence": confidence,
            })
    else:
        suggestions.append(_create_suggestion(
            note,
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
            confidence=confidence,
            reason=decision.get("reason"),
        ).to_dict())


def _apply_entity_update(note, entity, decision, relationship_type, confidence, evidence, applied_changes):
    fields = decision.get("fields") or {}
    changed = {}

    new_status = fields.get("status")
    if new_status and new_status in VALID_STATUS.get(entity.type, set()):
        entity.status = new_status
        changed["status"] = new_status

    raw_due = fields.get("due_at")
    if raw_due:
        parsed = _parse_iso_date(raw_due)
        if parsed:
            entity.due_at = parsed
            changed["due_at"] = raw_due

    raw_follow_up = fields.get("follow_up_at")
    if raw_follow_up:
        parsed = _parse_iso_date(raw_follow_up)
        if parsed:
            entity.follow_up_at = parsed
            changed["follow_up_at"] = raw_follow_up

    link = _create_entity_link(note, entity, relationship_type, confidence, evidence)

    if changed:
        applied_changes.append({
            "type": "entity_updated",
            "entity_id": entity.id,
            "entity_type": entity.type,
            "title": entity.title,
            "changes": changed,
        })
        _write_event(entity, "ai_updated", new_value=changed, actor="agent:v4-capture", confidence=confidence, reason=decision.get("reason"))
    if link is not None:
        applied_changes.append({
            "type": "relationship_added",
            "target_entity_id": entity.id,
            "relationship_type": relationship_type,
            "confidence": confidence,
        })
        _write_event(note, "relationship_added", new_value=link.to_dict(), actor="agent:v4-capture", confidence=confidence, reason=evidence)


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
    return entity


def _create_suggestion(note, suggestion_type, operation_type, payload, confidence=None, reason=None):
    suggestion = AiSuggestion(
        source_entity_id=note.id,
        suggestion_type=suggestion_type,
        operation_type=operation_type,
        payload=payload,
        confidence=confidence,
        reason=reason,
        status="pending",
    )
    db.session.add(suggestion)
    db.session.flush()
    return suggestion


def _create_entity_link(note, target, relationship_type, confidence, evidence, source="ai"):
    existing = EntityLink.query.filter_by(
        source_entity_id=note.id,
        target_entity_id=target.id,
        relationship_type=relationship_type,
    ).first()
    if existing is not None:
        return None
    link = EntityLink(
        source_entity_id=note.id,
        target_entity_id=target.id,
        relationship_type=relationship_type,
        source=source,
        confidence=confidence,
        evidence=evidence,
    )
    db.session.add(link)
    db.session.flush()

    # When a note is linked to any non-note entity, queue a summarize job so
    # the entity's summary reflects the new information.
    if getattr(note, "type", None) == "note" and getattr(target, "type", None) != "note":
        from services.v4_summarization import queue_summarize_if_needed
        queue_summarize_if_needed(target.id, has_existing_summary=bool(target.ai_summary))

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


def _clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None
