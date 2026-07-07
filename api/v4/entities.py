"""Engram v4 entities API."""

from api import api_v4_bp
from api import v4_entities as _v4e
from api.v4._shared import *

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
    _attach_project_context(rows)
    _attach_task_context(rows)
    _attach_compact_link_counts(rows)
    return jsonify({"data": [row.to_dict() for row in rows]})


# Path segment used for each entity type, e.g. /tasks/<id>, /people/<id>.
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
    # Attach project/area/people context for detail pages
    if entity.type == "task":
        _attach_task_context([entity])
    if entity.type == "project":
        _attach_project_context([entity])
    entity_data = entity.to_dict()
    if entity.type == "person":
        entity_data["is_owner"] = _is_owner(entity.title, entity.id)
    detail = {
        "entity": entity_data,
        "sections": _relationship_detail_sections(entity),
        "decisions_count": _decisions_count_for_entity(entity.id),
    }
    if entity.type == "person":
        tasks = _person_open_tasks(entity)
        _attach_task_context(tasks)
        latest_update = _latest_activity_updates([task.id for task in tasks])
        pulse = _person_pulse(tasks, latest_update)
        detail["current_load"] = _person_current_load(tasks, latest_update)
        detail["pulse"] = pulse
        detail["dependency_watch"] = _task_dependency_watch(tasks, latest_update)
        detail["meeting_prep"] = _person_meeting_prep(entity, tasks, latest_update, pulse)
    if entity.type == "project":
        tasks = _project_open_tasks(entity)
        _attach_task_context(tasks)
        latest_update = _latest_activity_updates([task.id for task in tasks])
        detail["project_pulse"] = _project_pulse(tasks, latest_update)
        detail["dependency_watch"] = _task_dependency_watch(tasks, latest_update)
    return jsonify(detail)


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
    data = []
    for event in events:
        event_dict = event.to_dict()
        event_dict["narration"] = narrate_event(event)
        data.append(event_dict)
    return jsonify({"data": data})


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


@api_v4_bp.route("/entities/<entity_id>/activity_updates", methods=["GET"])
def get_activity_updates(entity_id):
    target = db.session.get(Entity, entity_id)
    if target is None:
        return _error("entity not found", 404)

    limit = max(1, min(request.args.get("limit", DEFAULT_ACTIVITY_UPDATES_PAGE_SIZE, type=int), MAX_ACTIVITY_UPDATES_PAGE_SIZE))
    offset = max(0, request.args.get("offset", 0, type=int))

    base_query = _activity_updates_query(entity_id)
    total = base_query.count()
    notes = (
        base_query.order_by(*_activity_updates_order())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return jsonify({
        "data": [note.to_dict() for note in notes],
        "meta": {"total": total, "limit": limit, "offset": offset},
    })


@api_v4_bp.route("/entities/<entity_id>/activity_updates", methods=["POST"])
def create_activity_update(entity_id):
    target = db.session.get(Entity, entity_id)
    if target is None:
        return _error("entity not found", 404)

    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return _error("content is required")

    skip_extraction = bool(data.get("skip_extraction"))

    note, created, skip_reason = _create_activity_update_note(target, content, actor="user")
    if not created:
        reason = "duplicate within 24h" if skip_reason == "exact_duplicate" else skip_reason or "duplicate"
        return jsonify({"data": note.to_dict(), "skipped": True, "reason": reason})

    applied_mentions = _apply_explicit_mentions(note, content)

    suggestions = []
    if skip_extraction:
        extracted = {}
    else:
        # Lightweight extraction: scan for dates and new tasks (no full capture cycle).
        from services.v4_extraction import extract_dates_and_tasks_from_update

        parent_context = {"type": target.type, "title": target.title} if target.title else None
        extraction = extract_dates_and_tasks_from_update(content, parent_context=parent_context)
        extracted = _apply_activity_update_policy(note, target, content, extraction, suggestions)

    _queue_embed_job(note.id, "activity_update")
    from services.v4_summarization import queue_summarize_if_needed

    queue_summarize_if_needed(target.id, has_existing_summary=bool(target.ai_summary))

    db.session.commit()

    return jsonify({
        "data": _load_entity(note.id).to_dict(),
        "target": _load_entity(target.id).to_dict(),
        "extracted": extracted,
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
    if suggestion.operation_type == "create_decision":
        return _accept_create_decision_suggestion(suggestion)
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

    if entity_type == "task" and source_note.type in THREAD_INGEST_SOURCE_TYPES:
        parent_changes = []
        _link_task_to_note_projects(
            source_note,
            entity,
            suggestion.confidence,
            payload.get("evidence") or suggestion.reason,
            parent_changes,
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


def _accept_create_decision_suggestion(suggestion):
    """Accept a create_decision suggestion and persist the decision record."""
    payload = suggestion.payload or {}
    thread_id = payload.get("thread_id")
    if not thread_id:
        return _error("thread_id is required")
    thread = db.session.get(Entity, thread_id)
    if thread is None or thread.lifecycle == "deleted":
        return _error("thread entity not found", 404)

    statement = _clean_text(payload.get("statement"))
    if not statement:
        return _error("statement is required")

    decided_by = _clean_text(payload.get("decided_by")) or "user"
    if not _valid_decided_by(decided_by):
        return _error("decided_by must be 'user' or 'agent:<name>'")

    decided_at, decided_at_error = _parse_datetime_or_error(payload.get("decided_at"))
    if decided_at_error:
        return decided_at_error
    if decided_at is None:
        decided_at = datetime.now(timezone.utc)

    source_note_id = payload.get("source_note_id")
    if source_note_id:
        source_note = db.session.get(Entity, source_note_id)
        if source_note is None:
            return _error("source note not found", 404)

    decision = Decision(
        thread_id=thread_id,
        statement=statement,
        context=_clean_text(payload.get("context")),
        decided_at=decided_at,
        decided_by=decided_by,
        source_note_id=source_note_id,
    )
    db.session.add(decision)
    db.session.flush()

    _write_event(
        thread,
        "decision_recorded",
        new_value=decision.to_dict(),
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        reason=suggestion.reason,
        source_note_id=source_note_id,
    )

    suggestion.status = "accepted"
    suggestion.resolved_at = datetime.utcnow()
    _write_event(
        thread,
        "suggestion_accepted",
        new_value={"suggestion_id": suggestion.id, "decision_id": decision.id},
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        reason=suggestion.reason,
    )
    db.session.commit()

    return jsonify({
        "suggestion": suggestion.to_dict(),
        "decision": decision.to_dict(),
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
    if suggestion.operation_type == "update_unresolved":
        return _resolve_update_unresolved_suggestion(suggestion)
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


def _resolve_update_unresolved_suggestion(suggestion):
    """Resolve an update_unresolved suggestion (SQ-05) to a chosen target.

    Creates the activity-update note on the target and applies the stored
    extraction (status/follow-up/spin-off tasks) with the same policy as the
    Add update endpoint.
    """
    payload = suggestion.payload or {}
    body = request.get_json(silent=True) or {}
    target_id = body.get("target_id")
    if not target_id:
        return _error("target_id is required")

    target = db.session.get(Entity, target_id)
    if target is None or target.lifecycle == "deleted":
        return _error("target entity not found", 404)

    source_note = db.session.get(Entity, suggestion.source_entity_id)
    if source_note is None:
        return _error("source note not found", 404)
    if target.id == source_note.id:
        return _error("cannot resolve a suggestion to its own source note")

    content = payload.get("content") or (source_note.content or "")[:300]
    follow_on_suggestions = []
    au_note, created, _skip_reason = _create_activity_update_note(
        target,
        content,
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        source_note_id=source_note.id,
    )
    if au_note is not None:
        extraction = {
            "status": payload.get("status"),
            "confidence": payload.get("status_confidence") or 0.0,
            "follow_up_at": payload.get("follow_up_at"),
            "tasks": payload.get("tasks") or [],
        }
        _apply_activity_update_policy(
            source_note, target, content, extraction, follow_on_suggestions,
            actor="agent:v4-review",
        )
        from services.v4_summarization import queue_summarize_if_needed

        queue_summarize_if_needed(target.id, has_existing_summary=bool(target.ai_summary))

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
            "activity_update_note_id": au_note.id if au_note is not None else None,
        },
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        reason=f"resolved update to existing {target.type} '{target.title}'",
    )
    db.session.commit()

    return jsonify({
        "suggestion": suggestion.to_dict(),
        "linked_entity": _load_entity(target.id).to_dict(),
        "relationship": None,
        "suggestions": follow_on_suggestions,
    })


@api_v4_bp.route("/suggestions/<suggestion_id>/dismiss", methods=["POST"])
def dismiss_suggestion(suggestion_id):
    suggestion = db.session.get(AiSuggestion, suggestion_id)
    if suggestion is None:
        return _error("suggestion not found", 404)
    if suggestion.status != "pending":
        return _error("suggestion is not pending", 409)

    data = request.get_json(silent=True) or {}
    dismiss_reason = data.get("dismiss_reason")
    if dismiss_reason is not None and dismiss_reason not in VALID_DISMISS_REASONS:
        return _error(
            "dismiss_reason must be one of: " + ", ".join(sorted(VALID_DISMISS_REASONS))
        )

    suggestion.status = "dismissed"
    suggestion.resolved_at = datetime.utcnow()
    payload = dict(suggestion.payload or {})
    if dismiss_reason:
        payload["dismiss_reason"] = dismiss_reason
        suggestion.payload = payload
        flag_modified(suggestion, "payload")
    source_entity = db.session.get(Entity, suggestion.source_entity_id)
    if source_entity is not None:
        _write_event(
            source_entity,
            "suggestion_dismissed",
            new_value={"suggestion_id": suggestion.id, "dismiss_reason": dismiss_reason},
            actor="agent:v4-review",
            confidence=suggestion.confidence,
            reason=suggestion.reason,
        )
    db.session.commit()
    return jsonify({"data": suggestion.to_dict()})


@api_v4_bp.route("/decisions", methods=["GET"])
def list_decisions():
    """List decisions for a thread, ordered by decided_at desc."""
    thread_id = request.args.get("thread_id")
    if not thread_id:
        return _error("thread_id is required")
    if db.session.get(Entity, thread_id) is None:
        return _error("thread entity not found", 404)

    limit = max(1, min(request.args.get("limit", 50, type=int), 200))
    superseded_filter = request.args.get("superseded", "exclude").lower()

    query = Decision.query.filter(Decision.thread_id == thread_id)
    if superseded_filter == "exclude":
        query = query.filter(Decision.superseded_by.is_(None))
    elif superseded_filter == "only":
        query = query.filter(Decision.superseded_by.isnot(None))
    # "all" returns both superseded and active

    rows = query.order_by(Decision.decided_at.desc()).limit(limit).all()
    return jsonify({"data": [row.to_dict() for row in rows], "meta": {"limit": limit}})


@api_v4_bp.route("/decisions", methods=["POST"])
def create_decision():
    """Manually record a decision against a thread."""
    data = request.get_json(silent=True) or {}
    thread_id = data.get("thread_id")
    if not thread_id:
        return _error("thread_id is required")
    thread = db.session.get(Entity, thread_id)
    if thread is None or thread.lifecycle == "deleted":
        return _error("thread entity not found", 404)

    statement = _clean_text(data.get("statement"))
    if not statement:
        return _error("statement is required")

    decided_by = _clean_text(data.get("decided_by")) or "user"
    if not _valid_decided_by(decided_by):
        return _error("decided_by must be 'user' or 'agent:<name>'")

    decided_at, decided_at_error = _parse_datetime_or_error(data.get("decided_at"))
    if decided_at_error:
        return decided_at_error
    if decided_at is None:
        decided_at = datetime.now(timezone.utc)

    source_note_id = data.get("source_note_id")
    if source_note_id:
        source_note = db.session.get(Entity, source_note_id)
        if source_note is None:
            return _error("source note not found", 404)

    superseded_by = data.get("superseded_by")
    if superseded_by:
        superseding = db.session.get(Decision, superseded_by)
        if superseding is None:
            return _error("superseded_by decision not found", 404)
        if superseding.thread_id != thread_id:
            return _error("superseded_by decision belongs to a different thread", 400)

    decision = Decision(
        thread_id=thread_id,
        statement=statement,
        context=_clean_text(data.get("context")),
        decided_at=decided_at,
        decided_by=decided_by,
        source_note_id=source_note_id,
        superseded_by=superseded_by,
    )
    db.session.add(decision)
    db.session.flush()

    _write_event(
        thread,
        "decision_recorded",
        new_value=decision.to_dict(),
        actor=decided_by if decided_by.startswith("agent:") else "user",
        reason="manual decision recorded",
    )
    db.session.commit()

    return jsonify({"data": decision.to_dict()}), 201


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


