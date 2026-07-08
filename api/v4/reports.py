"""Engram v4 distillation reports API.

Endpoints:
  GET  /reports?status=pending
  GET  /reports/<id>
  POST /reports/<id>/resolve
  POST /reports/<id>/undo
"""

from services.v4_trust import check_pin, record_pin

from datetime import datetime, timezone

from api import api_v4_bp
from api.v4._shared import *
from api.v4._shared import _record_relationship_pin_event
from extensions import db
from models import ChangeBatch, DistillationReport

logger = logging.getLogger(__name__)

VALID_RESOLVE_ACTIONS = {"accept", "edit", "dismiss", "later"}
VALID_EDIT_FIELDS_CREATE = {"title", "content", "type", "status", "due_at", "follow_up_at", "assigned_to", "properties"}
VALID_EDIT_FIELDS_UPDATE = {"status", "due_at", "follow_up_at", "priority"}
VALID_EDIT_FIELDS_DECISION = {"statement", "context", "decided_by", "decided_at"}


@api_v4_bp.route("/reports", methods=["GET"])
def list_reports():
    status = request.args.get("status", "pending")
    if status not in {"pending", "partial", "reviewed", "superseded", "all"}:
        return _error(f"invalid status: {status}")

    limit = max(1, min(request.args.get("limit", 50, type=int), 200))
    query = DistillationReport.query
    if status != "all":
        query = query.filter(DistillationReport.status == status)

    total = query.count()
    rows = query.order_by(DistillationReport.created_at.desc()).limit(limit).all()
    return jsonify({"data": [row.to_dict() for row in rows], "meta": {"total": total, "limit": limit}})


@api_v4_bp.route("/reports/<report_id>", methods=["GET"])
def get_report(report_id):
    report = db.session.get(DistillationReport, report_id)
    if report is None:
        return _error("report not found", 404)

    note = db.session.get(Entity, report.source_note_id)
    suggestions = (
        AiSuggestion.query.filter_by(report_id=report_id)
        .order_by(AiSuggestion.created_at.asc())
        .all()
    )

    return jsonify({
        "data": report.to_dict(),
        "source_note": note.to_dict() if note is not None else None,
        "suggestions": [s.to_dict() for s in suggestions],
    })


@api_v4_bp.route("/reports/<report_id>/resolve", methods=["POST"])
def resolve_report(report_id):
    report = db.session.get(DistillationReport, report_id)
    if report is None:
        return _error("report not found", 404)
    if report.status == "superseded":
        return _error("report is superseded", 409)

    source_note = db.session.get(Entity, report.source_note_id)
    if source_note is None:
        return _error("source note not found", 404)

    data = request.get_json(silent=True) or {}
    decisions = data.get("decisions") or []
    if not isinstance(decisions, list):
        return _error("decisions must be a list")

    accept_rest = bool(data.get("accept_rest"))

    # Map suggestion_id -> decision for quick lookup.
    decision_by_id = {}
    for decision in decisions:
        suggestion_id = decision.get("suggestion_id")
        if not suggestion_id:
            return _error("each decision must have a suggestion_id")
        if suggestion_id in decision_by_id:
            return _error(f"duplicate decision for suggestion {suggestion_id}")
        action = decision.get("action")
        if action not in VALID_RESOLVE_ACTIONS:
            return _error(f"invalid action: {action}")
        decision_by_id[suggestion_id] = decision

    # Lock suggestions to this report.
    pending_suggestions = (
        AiSuggestion.query.filter_by(report_id=report_id, status="pending")
        .order_by(AiSuggestion.created_at.asc())
        .all()
    )
    pending_by_id = {s.id: s for s in pending_suggestions}

    # Validate all referenced suggestions belong to the report and are pending.
    for suggestion_id in decision_by_id:
        if suggestion_id not in pending_by_id:
            return _error(f"suggestion {suggestion_id} is not pending in this report", 409)

    try:
        batch = ChangeBatch(
            source_note_id=source_note.id,
            actor="user",
            source="review",
            summary=f"resolve report {report.id}",
        )
        db.session.add(batch)
        db.session.flush()

        applied_count = 0
        dismissed_count = 0
        later_count = 0
        errors = []

        # Process explicit decisions first.
        for suggestion_id, decision in decision_by_id.items():
            suggestion = pending_by_id[suggestion_id]
            action = decision.get("action")
            if action == "later":
                later_count += 1
                continue

            result = _apply_resolve_decision(
                suggestion,
                source_note,
                action,
                decision.get("edits") or {},
                decision.get("dismissal_reason"),
                batch.id,
            )
            if result.get("error"):
                errors.append({"suggestion_id": suggestion_id, "error": result["error"]})
            elif action == "dismiss":
                dismissed_count += 1
            else:
                applied_count += 1

        if errors:
            raise ValueError(f"resolve failed: {errors[0]['error']}")

        # Accept remaining pending suggestions if requested.
        if accept_rest:
            for suggestion in pending_suggestions:
                if suggestion.status != "pending":
                    continue
                if suggestion.id in decision_by_id and decision_by_id[suggestion.id].get("action") == "later":
                    continue
                result = _apply_resolve_decision(
                    suggestion,
                    source_note,
                    "accept",
                    {},
                    None,
                    batch.id,
                )
                if result.get("error"):
                    raise ValueError(f"resolve failed on accept_rest: {result['error']}")
                applied_count += 1

        # Determine final report status.
        remaining_pending = (
            AiSuggestion.query.filter_by(report_id=report_id, status="pending").count()
        )
        now = datetime.now(timezone.utc)
        report.reviewed_at = now
        if remaining_pending > 0:
            report.status = "partial"
        else:
            report.status = "reviewed"

        # Mark source note review as resolved when report is fully reviewed.
        if report.status == "reviewed":
            _mark_review_resolved(source_note)

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception("resolve report %s failed", report_id)
        return _error(f"resolve failed: {exc}", 500)

    return jsonify({
        "data": report.to_dict(),
        "change_batch": batch.to_dict(),
        "meta": {
            "applied": applied_count,
            "dismissed": dismissed_count,
            "later": later_count,
        },
    })


@api_v4_bp.route("/reports/<report_id>/undo", methods=["POST"])
def undo_report(report_id):
    report = db.session.get(DistillationReport, report_id)
    if report is None:
        return _error("report not found", 404)

    batch = (
        ChangeBatch.query.filter_by(source_note_id=report.source_note_id)
        .filter(ChangeBatch.undone_at.is_(None))
        .order_by(ChangeBatch.applied_at.desc())
        .first()
    )
    if batch is None:
        return _error("no active change batch for this report", 409)

    try:
        _undo_change_batch(batch)

        # Re-open accepted/edited suggestions so they can be reviewed again.
        for suggestion in AiSuggestion.query.filter_by(report_id=report_id).all():
            if suggestion.status in {"accepted", "edited"}:
                suggestion.status = "pending"
                suggestion.resolved_at = None

        report.status = "pending"
        report.reviewed_at = None
        _clear_review_resolution(report.source_note)

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception("undo report %s failed", report_id)
        return _error(f"undo failed: {exc}", 500)

    return jsonify({"data": report.to_dict(), "change_batch": batch.to_dict()})


def _apply_resolve_decision(suggestion, source_note, action, edits, dismissal_reason, change_batch_id):
    """Apply a single resolve decision. Returns {"error": ...} on failure."""
    if action == "dismiss":
        return _resolve_dismiss(suggestion, dismissal_reason, change_batch_id)

    if action == "edit":
        validation_error = _validate_edits(suggestion, edits)
        if validation_error:
            return {"error": validation_error}
        _merge_edits(suggestion, edits)

    if suggestion.operation_type == "create_entity" or suggestion.operation_type == "create_new_entity":
        return _resolve_create(suggestion, source_note, change_batch_id)
    if suggestion.operation_type == "update_entity":
        return _resolve_update(suggestion, source_note, change_batch_id)
    if suggestion.operation_type == "link_existing":
        return _resolve_link(suggestion, source_note, change_batch_id)
    if suggestion.operation_type == "create_decision":
        return _resolve_decision(suggestion, source_note, change_batch_id)
    if suggestion.operation_type == "update_unresolved":
        return _resolve_update_unresolved(suggestion, source_note, change_batch_id)

    return {"error": f"unsupported suggestion operation: {suggestion.operation_type}"}


def _validate_edits(suggestion, edits):
    if not isinstance(edits, dict):
        return "edits must be an object"

    if suggestion.operation_type in {"create_entity", "create_new_entity"}:
        invalid = set(edits) - VALID_EDIT_FIELDS_CREATE
    elif suggestion.operation_type == "update_entity":
        invalid = set(edits) - VALID_EDIT_FIELDS_UPDATE
    elif suggestion.operation_type == "create_decision":
        invalid = set(edits) - VALID_EDIT_FIELDS_DECISION
    else:
        invalid = set(edits)

    if invalid:
        return f"invalid edit fields: {', '.join(sorted(invalid))}"
    return None


def _merge_edits(suggestion, edits):
    payload = dict(suggestion.payload or {})
    if suggestion.operation_type in {"create_entity", "create_new_entity"}:
        for field in VALID_EDIT_FIELDS_CREATE:
            if field in edits:
                payload[field] = edits[field]
    elif suggestion.operation_type == "update_entity":
        fields = dict(payload.get("fields") or {})
        for field in VALID_EDIT_FIELDS_UPDATE:
            if field in edits:
                fields[field] = edits[field]
        payload["fields"] = fields
    elif suggestion.operation_type == "create_decision":
        for field in VALID_EDIT_FIELDS_DECISION:
            if field in edits:
                payload[field] = edits[field]

    suggestion.payload = payload
    flag_modified(suggestion, "payload")


def _resolve_create(suggestion, source_note, change_batch_id):
    payload = suggestion.payload or {}
    entity_type = payload.get("type")
    if entity_type not in RISKY_ENTITY_CREATION_TYPES:
        return {"error": f"invalid entity type: {entity_type}"}

    properties_error = _validate_properties(payload.get("properties") or {})
    if properties_error:
        return {"error": properties_error[0].get_json()["error"]}

    status = payload.get("status") or DEFAULT_STATUS[entity_type]
    validation_error = _validate_status(entity_type, status)
    if validation_error:
        return {"error": validation_error[0].get_json()["error"]}

    follow_up_at, follow_up_error = _parse_datetime_or_error(payload.get("follow_up_at"))
    if follow_up_error:
        return {"error": follow_up_error[0].get_json()["error"]}
    due_at, due_error = _parse_datetime_or_error(payload.get("due_at"))
    if due_error:
        return {"error": due_error[0].get_json()["error"]}

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
        properties=payload.get("properties") or {},
        ai_meta={},
        ai_status="pending",
    )
    db.session.add(entity)
    db.session.flush()
    _write_event(
        entity,
        "created",
        new_value=entity.to_dict(),
        actor="agent:v4-review",
        change_batch_id=change_batch_id,
    )
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
            change_batch_id=change_batch_id,
        )

    assigned_person, assignment_link, assigned_person_created = _apply_assignee(
        source_note,
        entity,
        payload.get("assigned_to"),
        suggestion.confidence,
        payload.get("evidence") or suggestion.reason,
        source="ai_review",
        actor="agent:v4-review",
        change_batch_id=change_batch_id,
        on_behalf="user",
    )
    if assigned_person_created:
        _write_event(
            assigned_person,
            "created",
            new_value=assigned_person.to_dict(),
            actor="agent:v4-review",
            confidence=suggestion.confidence,
            reason=suggestion.reason,
            change_batch_id=change_batch_id,
        )

    if entity_type == "task" and source_note.type in THREAD_INGEST_SOURCE_TYPES:
        parent_changes = []
        _link_task_to_note_projects(
            source_note,
            entity,
            suggestion.confidence,
            payload.get("evidence") or suggestion.reason,
            parent_changes,
            actor="agent:v4-review",
            change_batch_id=change_batch_id,
            on_behalf="user",
        )
        for parent_change in parent_changes:
            parent_link = EntityLink.query.filter_by(
                source_entity_id=entity.id,
                target_entity_id=parent_change["target_entity_id"],
                relationship_type="parent",
            ).first()
            if parent_link is not None:
                _write_event(
                    entity,
                    "relationship_added",
                    new_value=parent_link.to_dict(),
                    actor="agent:v4-review",
                    confidence=suggestion.confidence,
                    reason=suggestion.reason,
                    change_batch_id=change_batch_id,
                )

    suggestion.status = "accepted"
    suggestion.resolved_at = datetime.now(timezone.utc)
    _write_event(
        source_note,
        "suggestion_accepted",
        new_value={"suggestion_id": suggestion.id, "created_entity_id": entity.id},
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        reason=suggestion.reason,
        change_batch_id=change_batch_id,
    )
    return {"entity": entity.to_dict()}


def _resolve_update(suggestion, source_note, change_batch_id):
    payload = suggestion.payload or {}
    target_entity_id = payload.get("target_entity_id")
    if not target_entity_id:
        return {"error": "target_entity_id is required"}

    target_entity = db.session.get(Entity, target_entity_id)
    if target_entity is None or target_entity.lifecycle == "deleted":
        return {"error": "target entity not found"}

    target_type = payload.get("target_type")
    if target_type and target_type != target_entity.type:
        return {"error": "target_type does not match target entity"}

    fields = payload.get("fields") or {}
    if not isinstance(fields, dict):
        return {"error": "fields must be an object"}

    unsupported = set(fields) - {"status", "due_at", "follow_up_at", "priority"}
    if unsupported:
        return {"error": f"unsupported update fields: {', '.join(sorted(unsupported))}"}

    old_snapshot = target_entity.to_dict()
    changed = {}
    pin_event_needed = False

    if "status" in fields:
        check_pin(target_entity, "status", "agent:v4-review", on_behalf="user")
        validation_error = _validate_status(target_entity.type, fields["status"])
        if validation_error:
            return {"error": validation_error[0].get_json()["error"]}
        if fields["status"] != target_entity.status:
            target_entity.status = fields["status"]
            changed["status"] = fields["status"]
            pin_event_needed = record_pin(target_entity, "status", "agent:v4-review", on_behalf="user") or pin_event_needed

    if "due_at" in fields:
        check_pin(target_entity, "due_at", "agent:v4-review", on_behalf="user")
        due_at, due_error = _parse_datetime_or_error(fields["due_at"])
        if due_error:
            return {"error": due_error[0].get_json()["error"]}
        if due_at != target_entity.due_at:
            target_entity.due_at = due_at
            changed["due_at"] = due_at.isoformat() if due_at else None
            pin_event_needed = record_pin(target_entity, "due_at", "agent:v4-review", on_behalf="user") or pin_event_needed

    if "follow_up_at" in fields:
        follow_up_at, follow_up_error = _parse_datetime_or_error(fields["follow_up_at"])
        if follow_up_error:
            return {"error": follow_up_error[0].get_json()["error"]}
        if follow_up_at != target_entity.follow_up_at:
            target_entity.follow_up_at = follow_up_at
            changed["follow_up_at"] = follow_up_at.isoformat() if follow_up_at else None

    if "priority" in fields:
        priority = fields["priority"]
        if priority not in PRIORITY_LEVELS:
            return {"error": f"invalid priority: {priority}"}
        if priority != (target_entity.properties or {}).get("priority"):
            properties = dict(target_entity.properties or {})
            properties["priority"] = priority
            target_entity.properties = properties
            changed["priority"] = priority

    relationship_type = payload.get("relationship_type") or _default_relationship_type(target_entity.type)
    if relationship_type not in RELATIONSHIP_TYPES:
        return {"error": f"invalid relationship_type: {relationship_type}"}
    parent_target_id = payload.get("parent_target_id")
    parent_link = None
    if parent_target_id:
        parent_entity = db.session.get(Entity, parent_target_id)
        if parent_entity is None or parent_entity.lifecycle == "deleted":
            return {"error": "parent target entity not found"}
        parent_link = _create_entity_link(
            target_entity,
            parent_entity,
            "parent",
            suggestion.confidence,
            payload.get("evidence") or suggestion.reason,
            source="ai_review",
        )

    link_source, link_target = _candidate_link_endpoints(source_note, target_entity, relationship_type)
    link = _create_entity_link(
        link_source,
        link_target,
        relationship_type,
        suggestion.confidence,
        payload.get("evidence") or suggestion.reason,
        source="ai_review",
    )

    if not changed and link is None and parent_link is None:
        return {"error": "suggestion no longer applies"}

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
            change_batch_id=change_batch_id,
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
                change_batch_id=change_batch_id,
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
            change_batch_id=change_batch_id,
        )
    if parent_link is not None:
        _write_event(
            target_entity,
            "relationship_added",
            new_value=parent_link.to_dict(),
            actor="agent:v4-review",
            confidence=suggestion.confidence,
            reason=suggestion.reason,
            change_batch_id=change_batch_id,
        )
        _record_relationship_pin_event(
            target_entity,
            "parent",
            actor="agent:v4-review",
            reason="accepted suggestion pinned parent",
            confidence=suggestion.confidence,
            change_batch_id=change_batch_id,
            on_behalf="user",
        )

    assigned_person, assignment_link, assigned_person_created = _apply_assignee(
        source_note,
        target_entity,
        payload.get("assigned_to"),
        suggestion.confidence,
        payload.get("evidence") or suggestion.reason,
        source="ai_review",
        actor="agent:v4-review",
        change_batch_id=change_batch_id,
        on_behalf="user",
    )
    if assigned_person_created:
        _write_event(
            assigned_person,
            "created",
            new_value=assigned_person.to_dict(),
            actor="agent:v4-review",
            confidence=suggestion.confidence,
            reason=suggestion.reason,
            change_batch_id=change_batch_id,
        )

    suggestion.status = "accepted"
    suggestion.resolved_at = datetime.now(timezone.utc)
    _write_event(
        source_note,
        "suggestion_accepted",
        new_value={
            "suggestion_id": suggestion.id,
            "updated_entity_id": target_entity.id,
            "relationship_id": link.id if link is not None else None,
        },
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        reason=suggestion.reason,
        change_batch_id=change_batch_id,
    )
    return {"entity": target_entity.to_dict()}


def _resolve_link(suggestion, source_note, change_batch_id):
    payload = suggestion.payload or {}
    target_entity_id = payload.get("target_entity_id")
    if not target_entity_id:
        return {"error": "target_entity_id is required"}
    if target_entity_id == source_note.id:
        return {"error": "self-link relationships are not allowed"}

    target_entity = db.session.get(Entity, target_entity_id)
    if target_entity is None or target_entity.lifecycle == "deleted":
        return {"error": "target entity not found"}

    relationship_type = payload.get("relationship_type") or _default_relationship_type(target_entity.type)
    if relationship_type not in RELATIONSHIP_TYPES:
        return {"error": f"invalid relationship_type: {relationship_type}"}

    if EntityLink.query.filter_by(
        source_entity_id=source_note.id,
        target_entity_id=target_entity.id,
        relationship_type=relationship_type,
    ).first():
        return {"error": "duplicate relationship"}

    link_source, link_target = _candidate_link_endpoints(source_note, target_entity, relationship_type)
    link = _create_entity_link(
        link_source,
        link_target,
        relationship_type,
        suggestion.confidence,
        payload.get("evidence") or suggestion.reason,
        source="ai_review",
    )
    _write_event(
        source_note,
        "relationship_added",
        new_value=link.to_dict(),
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        reason=suggestion.reason,
        change_batch_id=change_batch_id,
    )
    _record_relationship_pin_event(
        link_source,
        relationship_type,
        actor="agent:v4-review",
        reason="accepted suggestion pinned relationship field",
        confidence=suggestion.confidence,
        change_batch_id=change_batch_id,
        on_behalf="user",
    )

    suggestion.status = "accepted"
    suggestion.resolved_at = datetime.now(timezone.utc)
    _write_event(
        source_note,
        "suggestion_accepted",
        new_value={"suggestion_id": suggestion.id, "relationship_id": link.id},
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        reason=suggestion.reason,
        change_batch_id=change_batch_id,
    )
    return {"relationship": link.to_dict()}


def _resolve_decision(suggestion, source_note, change_batch_id):
    payload = suggestion.payload or {}
    thread_id = payload.get("thread_id")
    if not thread_id:
        return {"error": "thread_id is required"}
    thread = db.session.get(Entity, thread_id)
    if thread is None or thread.lifecycle == "deleted":
        return {"error": "thread entity not found"}

    statement = _clean_text(payload.get("statement"))
    if not statement:
        return {"error": "statement is required"}

    decided_by = _clean_text(payload.get("decided_by")) or "user"
    if not _valid_decided_by(decided_by):
        return {"error": "decided_by must be 'user' or 'agent:<name>'"}

    decided_at, decided_at_error = _parse_datetime_or_error(payload.get("decided_at"))
    if decided_at_error:
        return {"error": decided_at_error[0].get_json()["error"]}
    if decided_at is None:
        decided_at = datetime.now(timezone.utc)

    source_note_id = payload.get("source_note_id")
    if source_note_id:
        note = db.session.get(Entity, source_note_id)
        if note is None:
            return {"error": "source note not found"}

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
        change_batch_id=change_batch_id,
    )

    suggestion.status = "accepted"
    suggestion.resolved_at = datetime.now(timezone.utc)
    _write_event(
        thread,
        "suggestion_accepted",
        new_value={"suggestion_id": suggestion.id, "decision_id": decision.id},
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        reason=suggestion.reason,
        change_batch_id=change_batch_id,
    )
    return {"decision": decision.to_dict()}


def _resolve_update_unresolved(suggestion, source_note, change_batch_id):
    payload = suggestion.payload or {}
    target_id = payload.get("target_entity_id")
    if not target_id:
        return {"error": "target_entity_id is required"}

    target = db.session.get(Entity, target_id)
    if target is None or target.lifecycle == "deleted":
        return {"error": "target entity not found"}
    if target.id == source_note.id:
        return {"error": "cannot resolve a suggestion to its own source note"}

    content = payload.get("content") or (source_note.content or "")[:300]
    follow_on_suggestions = []
    au_note, created, _skip_reason = _create_activity_update_note(
        target,
        content,
        actor="agent:v4-review",
        confidence=suggestion.confidence,
        source_note_id=source_note.id,
        change_batch_id=change_batch_id,
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
            change_batch_id=change_batch_id,
        )
        from services.v4_summarization import queue_summarize_if_needed
        queue_summarize_if_needed(target.id, has_existing_summary=bool(target.ai_summary))

    suggestion.status = "accepted"
    suggestion.resolved_at = datetime.now(timezone.utc)
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
        change_batch_id=change_batch_id,
    )
    return {"entity": target.to_dict()}


def _resolve_dismiss(suggestion, dismissal_reason, change_batch_id):
    if dismissal_reason is not None and dismissal_reason not in VALID_DISMISS_REASONS:
        return {"error": f"dismiss_reason must be one of: {', '.join(sorted(VALID_DISMISS_REASONS))}"}

    suggestion.status = "dismissed"
    suggestion.resolved_at = datetime.now(timezone.utc)
    payload = dict(suggestion.payload or {})
    if dismissal_reason:
        payload["dismiss_reason"] = dismissal_reason
        suggestion.payload = payload
        flag_modified(suggestion, "payload")

    source_entity = db.session.get(Entity, suggestion.source_entity_id)
    if source_entity is not None:
        _write_event(
            source_entity,
            "suggestion_dismissed",
            new_value={"suggestion_id": suggestion.id, "dismiss_reason": dismissal_reason},
            actor="agent:v4-review",
            confidence=suggestion.confidence,
            reason=suggestion.reason,
            change_batch_id=change_batch_id,
        )
    return {"dismissed": True}


def _undo_change_batch(batch):
    """Revert all state-changing events in a ChangeBatch. Caller commits."""
    events = (
        EntityEvent.query.filter_by(change_batch_id=batch.id)
        .filter(EntityEvent.reverted_at.is_(None))
        .order_by(EntityEvent.created_at.desc())
        .all()
    )

    for event in events:
        if event.event_type == "suggestion_dismissed":
            # Dismissals are retained; do not revert.
            continue
        if event.event_type == "suggestion_accepted":
            # Marker event only; the state change is recorded in separate events.
            event.reverted_at = datetime.now(timezone.utc)
            continue

        _revert_event(event, batch.id)

    batch.undone_at = datetime.now(timezone.utc)


def _revert_event(event, change_batch_id):
    """Revert a single state-changing event. Caller must flush/commit."""
    if event.reverted_at is not None:
        return

    entity = db.session.get(Entity, event.entity_id)
    if entity is None:
        return

    if event.event_type == "ai_updated":
        old_value = event.old_value or {}
        new_value = event.new_value or {}
        for field in new_value:
            if field == "status":
                status = old_value.get("status")
                if status in VALID_STATUS.get(entity.type, set()):
                    entity.status = status
            elif field == "title":
                entity.title = old_value.get("title")
            elif field in ("due_at", "follow_up_at"):
                parsed, _ = _parse_datetime_or_error(old_value.get(field))
                setattr(entity, field, parsed)
        _write_event(
            entity,
            "reverted",
            old_value=new_value,
            new_value=old_value,
            reason=f"revert of event {event.id}",
            change_batch_id=change_batch_id,
        )

    elif event.event_type == "created":
        old_lifecycle = entity.lifecycle
        entity.lifecycle = "deleted"
        _write_event(
            entity,
            "reverted",
            old_value={"lifecycle": old_lifecycle},
            new_value={"lifecycle": "deleted"},
            reason=f"revert of event {event.id}",
            change_batch_id=change_batch_id,
        )

    elif event.event_type == "decision_recorded":
        decision_id = (event.new_value or {}).get("id")
        decision = db.session.get(Decision, decision_id) if decision_id else None
        if decision is not None:
            db.session.delete(decision)
            _write_event(
                entity,
                "reverted",
                old_value=event.new_value,
                new_value=None,
                reason=f"revert of event {event.id}",
                change_batch_id=change_batch_id,
            )

    elif event.event_type == "activity_update_added":
        note_id = (event.new_value or {}).get("note_id")
        au_note = db.session.get(Entity, note_id) if note_id else None
        if au_note is not None:
            old_lifecycle = au_note.lifecycle
            au_note.lifecycle = "archived"
            _write_event(
                au_note,
                "reverted",
                old_value={"lifecycle": old_lifecycle},
                new_value={"lifecycle": "archived"},
                reason=f"revert of event {event.id}",
                change_batch_id=change_batch_id,
            )

    elif event.event_type == "relationship_added":
        link_id = (event.new_value or {}).get("id")
        link = db.session.get(EntityLink, link_id) if link_id else None
        if link is not None:
            link_snapshot = link.to_dict()
            db.session.delete(link)
            _write_event(
                entity,
                "reverted",
                old_value=link_snapshot,
                new_value=None,
                reason=f"revert of event {event.id}",
                change_batch_id=change_batch_id,
            )

    elif event.event_type == "updated":
        old_value = event.old_value or {}
        new_value = event.new_value or {}
        restored = {}
        for field in new_value:
            if field == "status":
                status = old_value.get("status")
                if status in VALID_STATUS.get(entity.type, set()):
                    entity.status = status
                    restored["status"] = status
            elif field == "title":
                entity.title = old_value.get("title")
                restored["title"] = entity.title
            elif field in ("due_at", "follow_up_at"):
                parsed, _ = _parse_datetime_or_error(old_value.get(field))
                setattr(entity, field, parsed)
                restored[field] = old_value.get(field)
            elif field == "priority":
                properties = dict(entity.properties or {})
                old_priority = (old_value or {}).get("properties", {}).get("priority")
                if old_priority is not None:
                    properties["priority"] = old_priority
                elif "priority" in properties:
                    del properties["priority"]
                entity.properties = properties
                restored["priority"] = old_priority
        _write_event(
            entity,
            "reverted",
            old_value=new_value,
            new_value=restored,
            reason=f"revert of event {event.id}",
            change_batch_id=change_batch_id,
        )

    elif event.event_type == "status_changed":
        old_status = (event.old_value or {}).get("status")
        if old_status in VALID_STATUS.get(entity.type, set()):
            entity.status = old_status
            _write_event(
                entity,
                "reverted",
                old_value=event.new_value,
                new_value=event.old_value,
                reason=f"revert of event {event.id}",
                change_batch_id=change_batch_id,
            )

    event.reverted_at = datetime.now(timezone.utc)
