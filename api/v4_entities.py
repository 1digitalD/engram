"""Engram v4 canonical entity API."""

from datetime import datetime, time, timezone

from flask import jsonify, request
from sqlalchemy import func
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
    "follow_up_at",
    "source",
    "reference_url",
    "properties",
}
RELATIONSHIP_PROPERTY_KEYS = {
    "project_id",
    "project_ids",
    "area_id",
    "area_ids",
    "person_id",
    "person_ids",
    "note_id",
    "note_ids",
    "source_note_id",
    "source_note_ids",
    "parent_id",
    "parent_ids",
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

    note = Entity(
        type="note",
        title=data.get("title") or _title_from_content(content),
        content=content,
        status="active",
        lifecycle="active",
        source=data.get("source") or "quick_capture",
        properties={},
        ai_meta={},
        ai_status="pending",
    )
    db.session.add(note)
    db.session.flush()
    _write_event(note, "created", new_value=note.to_dict())
    db.session.add(Job(job_type="embed", entity_id=note.id, payload={"reason": "capture"}))

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

    rows = query.order_by(Entity.updated_at.desc(), Entity.created_at.desc()).limit(limit).all()
    return jsonify({"data": [row.to_dict() for row in rows]})


@api_v4_bp.route("/search", methods=["GET"])
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return _error("q parameter is required")
    mode = request.args.get("mode", "hybrid")
    entity_type = request.args.get("type")
    status = request.args.get("status")
    lifecycle = request.args.get("lifecycle")
    limit = request.args.get("limit", 20, type=int)

    if entity_type and entity_type not in ENTITY_TYPES:
        return _error(f"invalid entity type: {entity_type}")
    if lifecycle and lifecycle not in VALID_LIFECYCLE:
        return _error(f"invalid lifecycle: {lifecycle}")

    from services.v4_search import search_entities
    results = search_entities(
        q,
        mode=mode,
        entity_type=entity_type,
        status=status,
        lifecycle=lifecycle,
        limit=limit,
    )
    resolved_mode = mode if mode in {"keyword", "semantic", "hybrid"} else "hybrid"
    return jsonify({"query": q, "mode": resolved_mode, "results": results})


@api_v4_bp.route("/today", methods=["GET"])
def today():
    now = datetime.now(timezone.utc)
    end_of_today = datetime.combine(now.date(), time.max, tzinfo=timezone.utc)
    follow_ups = (
        _entity_query()
        .filter(
            Entity.lifecycle == "active",
            Entity.follow_up_at.isnot(None),
            Entity.follow_up_at <= end_of_today,
        )
        .order_by(Entity.follow_up_at.asc())
        .limit(50)
        .all()
    )
    blocked_or_waiting_tasks = (
        _entity_query()
        .filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(["blocked", "waiting"]),
        )
        .order_by(Entity.updated_at.desc())
        .limit(50)
        .all()
    )
    projects = (
        _entity_query()
        .filter(Entity.type == "project", Entity.lifecycle == "active", Entity.status == "active")
        .order_by(Entity.updated_at.desc())
        .limit(100)
        .all()
    )
    projects_without_open_tasks = [
        project for project in projects
        if not _project_has_open_task(project.id)
    ][:25]
    recent_notes = (
        _entity_query()
        .filter(Entity.type == "note", Entity.lifecycle == "active")
        .order_by(Entity.updated_at.desc(), Entity.created_at.desc())
        .limit(10)
        .all()
    )
    pending_suggestions = (
        AiSuggestion.query.filter_by(status="pending")
        .order_by(AiSuggestion.created_at.desc())
        .limit(25)
        .all()
    )

    return jsonify({
        "follow_ups": [entity.to_dict() for entity in follow_ups],
        "blocked_or_waiting_tasks": [entity.to_dict() for entity in blocked_or_waiting_tasks],
        "projects_without_open_tasks": [entity.to_dict() for entity in projects_without_open_tasks],
        "recent_notes": [entity.to_dict() for entity in recent_notes],
        "pending_suggestions": [suggestion.to_dict() for suggestion in pending_suggestions],
    })


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

    entity = Entity(
        type=entity_type,
        title=data.get("title"),
        content=data.get("content"),
        status=status,
        lifecycle=data.get("lifecycle") or "active",
        follow_up_at=_parse_datetime(data.get("follow_up_at")),
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
    if "follow_up_at" in data:
        entity.follow_up_at = _parse_datetime(data["follow_up_at"])
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
    query = AiSuggestion.query
    if status != "all":
        query = query.filter(AiSuggestion.status == status)
    rows = query.order_by(AiSuggestion.created_at.desc()).limit(200).all()
    return jsonify({"data": [row.to_dict() for row in rows]})


@api_v4_bp.route("/suggestions/<suggestion_id>/accept", methods=["POST"])
def accept_suggestion(suggestion_id):
    suggestion = db.session.get(AiSuggestion, suggestion_id)
    if suggestion is None:
        return _error("suggestion not found", 404)
    if suggestion.status != "pending":
        return _error("suggestion is not pending", 409)
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

    source_note = db.session.get(Entity, suggestion.source_entity_id)
    if source_note is None:
        return _error("source note not found", 404)

    entity = Entity(
        type=entity_type,
        title=payload.get("title"),
        content=payload.get("content"),
        status=status,
        lifecycle="active",
        follow_up_at=_parse_datetime(payload.get("follow_up_at")),
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


def _project_has_open_task(project_id):
    open_statuses = {"open", "in_progress", "waiting", "blocked"}
    links = EntityLink.query.filter_by(target_entity_id=project_id, relationship_type="parent").all()
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
    if summary:
        ai_meta = dict(note.ai_meta or {})
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

    for link_candidate in extraction.get("links") or []:
        suggestions.extend(_reconcile_link_candidate(note, link_candidate, applied_changes))

    for entity_candidate in extraction.get("entities") or []:
        suggestion = _suggest_entity_creation(note, entity_candidate)
        if suggestion is not None:
            suggestions.append(suggestion.to_dict())

    return applied_changes, suggestions


def _reconcile_link_candidate(note, candidate, applied_changes):
    target_type = _candidate_value(candidate, "target_type") or _candidate_value(candidate, "type")
    title = _candidate_value(candidate, "title")
    if target_type not in RISKY_ENTITY_CREATION_TYPES or not title:
        return []

    confidence = _candidate_confidence(candidate)
    relationship_type = _candidate_value(candidate, "relationship_type") or _default_relationship_type(target_type)
    if relationship_type not in RELATIONSHIP_TYPES:
        relationship_type = _default_relationship_type(target_type)
    evidence = _candidate_value(candidate, "evidence")
    target = _find_existing_entity(target_type, title)

    if target is None:
        suggestion = _create_suggestion(
            note,
            suggestion_type=f"create_{target_type}",
            operation_type="create_entity",
            payload={
                "type": target_type,
                "title": title,
                "content": _candidate_value(candidate, "content"),
                "source_note_id": note.id,
                "evidence": evidence,
                "relationship_type": relationship_type,
            },
            confidence=confidence,
            reason=evidence,
        )
        return [suggestion.to_dict()]

    if confidence < AUTO_APPLY_CONFIDENCE:
        suggestion = _create_suggestion(
            note,
            suggestion_type="link_existing",
            operation_type="link_existing",
            payload={
                "source_note_id": note.id,
                "target_entity_id": target.id,
                "target_type": target.type,
                "title": target.title,
                "relationship_type": relationship_type,
                "evidence": evidence,
            },
            confidence=confidence,
            reason=evidence,
        )
        return [suggestion.to_dict()]

    link = _create_entity_link(note, target, relationship_type, confidence, evidence)
    if link is None:
        return []
    applied_changes.append(
        {
            "type": "relationship_added",
            "target_entity_id": target.id,
            "relationship_type": relationship_type,
            "confidence": confidence,
        }
    )
    _write_event(
        note,
        "relationship_added",
        new_value=link.to_dict(),
        actor="agent:v4-capture",
        confidence=confidence,
        reason=evidence,
    )
    return []


def _suggest_entity_creation(note, candidate):
    entity_type = _candidate_value(candidate, "type")
    title = _candidate_value(candidate, "title")
    if entity_type not in RISKY_ENTITY_CREATION_TYPES or not title:
        return None

    evidence = _candidate_value(candidate, "evidence")
    payload = {
        "type": entity_type,
        "title": title,
        "content": _candidate_value(candidate, "content"),
        "source_note_id": note.id,
        "evidence": evidence,
    }
    properties = candidate.get("properties") if isinstance(candidate, dict) else None
    if isinstance(properties, dict) and _find_relationship_property_key(properties) is None:
        payload["properties"] = properties
    return _create_suggestion(
        note,
        suggestion_type=f"create_{entity_type}",
        operation_type="create_entity",
        payload=payload,
        confidence=_candidate_confidence(candidate),
        reason=evidence,
    )


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
