"""AI Operation Applier — applies approved AI operations to the system.

Responsibilities:
- Apply safe high-confidence operations
- Create suggestions for review-required operations
- Create entity events for every mutation
- Create links to source note
- Respect data integrity rules
- Return applied change batch
"""

import logging
from datetime import datetime, timezone

from extensions import db
from models import Entity, EntityLink, EntityEvent, AiSuggestion
from services.entity_service import create_entity, _write_event
from services.link_service import create_link

logger = logging.getLogger(__name__)

# Confidence thresholds
AUTO_APPLY_THRESHOLD = 0.92
SUGGESTION_THRESHOLD_MIN = 0.70


def _build_batch_summary(proposed_changes, suggestions):
    ops = [c.get("operation") for c in proposed_changes] + [s.get("operation") for s in suggestions]
    op_counts = {}
    for op in ops:
        op_counts[op] = op_counts.get(op, 0) + 1
    parts = [f"{v} {k}" for k, v in op_counts.items()]
    return "; ".join(parts) if parts else "no changes"
SUGGESTION_THRESHOLD_MAX = 0.91


def apply_change_plan(change_plan, actor="agent:capture"):
    """Apply a structured AI change plan.

    Args:
        change_plan: dict with source_note_id, proposed_changes, suggestions.
        actor: Actor identifier for events.

    Returns:
        dict with applied_changes, suggestions, and change_batch_id.
    """
    source_note_id = change_plan.get("source_note_id")
    proposed_changes = change_plan.get("proposed_changes", [])
    plan_suggestions = change_plan.get("suggestions", [])

    applied_changes = []
    new_suggestions = []

    batch = None
    if proposed_changes or plan_suggestions:
        from models import ChangeBatch
        batch = ChangeBatch(
            source_note_id=source_note_id,
            actor=actor,
            source="ai",
            summary=_build_batch_summary(proposed_changes, plan_suggestions),
        )
        db.session.add(batch)
        db.session.flush()
        batch.applied_at = datetime.now(timezone.utc)
        db.session.flush()

    for change in proposed_changes:
        confidence = change.get("confidence", 0.0)
        operation = change.get("operation")
        current_batch_id = batch.id if batch else None

        if confidence >= AUTO_APPLY_THRESHOLD:
            result = _apply_operation(change, source_note_id, actor, batch_id=current_batch_id)
            if result:
                result["change_batch_id"] = current_batch_id
                applied_changes.append(result)
        elif confidence >= SUGGESTION_THRESHOLD_MIN:
            suggestion = _create_suggestion(change, source_note_id, batch_id=batch.id if batch else None)
            if suggestion:
                new_suggestions.append(suggestion)
        else:
            # Below threshold: log but don't mutate
            logger.info(
                "Skipping low-confidence operation %s (confidence=%.2f)",
                operation, confidence,
            )

    # Persist pre-defined suggestions from the change plan
    for s in plan_suggestions:
        suggestion_payload = dict(s or {})
        if "confidence" not in suggestion_payload:
            suggestion_payload["confidence"] = SUGGESTION_THRESHOLD_MIN
        suggestion = _create_suggestion(
            suggestion_payload,
            source_note_id,
            batch_id=batch.id if batch else None,
        )
        if suggestion:
            new_suggestions.append(suggestion)

    db.session.commit()

    return {
        "applied_changes": applied_changes,
        "suggestions": new_suggestions,
        "change_batch_id": batch.id if batch else None,
    }


def _apply_operation(change, source_note_id, actor, batch_id=None):
    """Apply a single approved operation."""
    operation = change.get("operation")

    try:
        if operation == "link_entity":
            return _apply_link_entity(change, source_note_id, actor, batch_id=batch_id)
        elif operation == "create_task":
            return _apply_create_task(change, source_note_id, actor, batch_id=batch_id)
        elif operation == "create_person":
            return _apply_create_person(change, source_note_id, actor, batch_id=batch_id)
        elif operation == "create_project":
            return _apply_create_project(change, source_note_id, actor, batch_id=batch_id)
        elif operation == "create_area":
            return _apply_create_area(change, source_note_id, actor, batch_id=batch_id)
        elif operation == "create_resource":
            return _apply_create_resource(change, source_note_id, actor, batch_id=batch_id)
        elif operation == "append_context":
            return _apply_append_context(change, source_note_id, actor, batch_id=batch_id)
        elif operation == "complete_task":
            return _apply_complete_task(change, actor, batch_id=batch_id)
        elif operation == "reopen_task":
            return _apply_reopen_task(change, actor, batch_id=batch_id)
        elif operation == "add_follow_up":
            return _apply_add_follow_up(change, source_note_id, actor, batch_id=batch_id)
        elif operation == "change_status":
            return _apply_change_status(change, source_note_id, actor, batch_id=batch_id)
        else:
            logger.warning("Unknown operation: %s", operation)
            return None
    except Exception as e:
        logger.error("Failed to apply operation %s: %s", operation, e)
        return None


def _apply_link_entity(change, source_note_id, actor, batch_id=None):
    link = create_link(
        src_id=change["src_id"],
        dst_id=change["dst_id"],
        link_type=change.get("link_type", "related"),
        source="ai",
        confidence=change.get("confidence"),
        evidence=change.get("evidence"),
        actor=actor,
        batch_id=batch_id,
    )
    return {
        "operation": "link_entity",
        "link_id": link.id,
        "src_id": change["src_id"],
        "dst_id": change["dst_id"],
        "link_type": change.get("link_type", "related"),
        "confidence": change.get("confidence"),
    }


def _apply_create_task(change, source_note_id, actor, batch_id=None):
    task = create_entity(
        entity_type="task",
        title=change["title"],
        content=change.get("content"),
        source="ai",
        actor=actor,
        properties={},
        batch_id=batch_id,
    )

    if source_note_id:
        create_link(
            src_id=task.id,
            dst_id=source_note_id,
            link_type="derived_from",
            source="ai",
            confidence=change.get("confidence"),
            actor=actor,
            batch_id=batch_id,
        )

    # Link to project if specified
    project_id = change.get("linked_project_id")
    if project_id:
        create_link(
            src_id=task.id,
            dst_id=project_id,
            link_type="parent",
            source="ai",
            confidence=change.get("confidence"),
            actor=actor,
            batch_id=batch_id,
        )

    # Link to people if specified
    for person_id in (change.get("linked_people") or []):
        create_link(
            src_id=task.id,
            dst_id=person_id,
            link_type="assigned_to",
            source="ai",
            confidence=change.get("confidence"),
            actor=actor,
            batch_id=batch_id,
        )

    return {
        "operation": "create_task",
        "entity_id": task.id,
        "title": change["title"],
        "confidence": change.get("confidence"),
    }


def _apply_create_person(change, source_note_id, actor, batch_id=None):
    person = create_entity(
        entity_type="person",
        title=change["name"],
        source="ai",
        actor=actor,
        properties={},
        batch_id=batch_id,
    )

    if source_note_id:
        create_link(
            src_id=person.id,
            dst_id=source_note_id,
            link_type="derived_from",
            source="ai",
            confidence=change.get("confidence"),
            actor=actor,
            batch_id=batch_id,
        )

    return {
        "operation": "create_person",
        "entity_id": person.id,
        "title": change["name"],
        "confidence": change.get("confidence"),
    }


def _apply_create_project(change, source_note_id, actor, batch_id=None):
    project = create_entity(
        entity_type="project",
        title=change["title"],
        content=change.get("content"),
        source="ai",
        actor=actor,
        properties={},
        batch_id=batch_id,
    )

    if source_note_id:
        create_link(
            src_id=source_note_id,
            dst_id=project.id,
            link_type="related",
            source="ai",
            confidence=change.get("confidence"),
            actor=actor,
            batch_id=batch_id,
        )

    return {
        "operation": "create_project",
        "entity_id": project.id,
        "title": change["title"],
        "confidence": change.get("confidence"),
    }


def _apply_create_area(change, source_note_id, actor, batch_id=None):
    area = create_entity(
        entity_type="area",
        title=change["title"],
        source="ai",
        actor=actor,
        properties={},
        batch_id=batch_id,
    )

    if source_note_id:
        create_link(
            src_id=source_note_id,
            dst_id=area.id,
            link_type="related",
            source="ai",
            confidence=change.get("confidence"),
            actor=actor,
            batch_id=batch_id,
        )

    return {
        "operation": "create_area",
        "entity_id": area.id,
        "title": change["title"],
        "confidence": change.get("confidence"),
    }


def _apply_reopen_task(change, actor, batch_id=None):
    task_id = change.get("entity_id")
    if not task_id:
        return None
    task = db.session.get(Entity, task_id)
    if not task or task.type != "task":
        return None
    task.status = "pending"
    _write_event(
        entity_id=task.id,
        event_type="status_changed",
        actor=actor,
        new_value={"status": "pending", "reason": change.get("reason", "Reopened by AI")},
        confidence=change.get("confidence"),
        batch_id=batch_id,
    )
    return {
        "operation": "reopen_task",
        "entity_id": task.id,
        "confidence": change.get("confidence"),
    }


def _apply_add_follow_up(change, source_note_id, actor, batch_id=None):
    title = change.get("title", "Follow-up")
    follow_up = create_entity(
        entity_type="task",
        title=title,
        source="ai",
        actor=actor,
        properties={"follow_up_of": change.get("task_id")},
        batch_id=batch_id,
    )

    if source_note_id:
        create_link(
            src_id=source_note_id,
            dst_id=follow_up.id,
            link_type="related",
            source="ai",
            confidence=change.get("confidence"),
            actor=actor,
            batch_id=batch_id,
        )

    if change.get("task_id"):
        create_link(
            src_id=change["task_id"],
            dst_id=follow_up.id,
            link_type="subtask",
            source="ai",
            confidence=change.get("confidence"),
            actor=actor,
            batch_id=batch_id,
        )

    return {
        "operation": "add_follow_up",
        "entity_id": follow_up.id,
        "title": title,
        "confidence": change.get("confidence"),
    }


def _apply_change_status(change, source_note_id, actor, batch_id=None):
    entity_id = change.get("entity_id")
    new_status = change.get("status")
    if not entity_id or not new_status:
        return None
    entity = db.session.get(Entity, entity_id)
    if not entity:
        return None
    old_status = entity.status
    entity.status = new_status
    _write_event(
        entity_id=entity.id,
        event_type="status_changed",
        actor=actor,
        new_value={"old": old_status, "new": new_status, "reason": change.get("reason")},
        confidence=change.get("confidence"),
        batch_id=batch_id,
    )
    return {
        "operation": "change_status",
        "entity_id": entity.id,
        "old_status": old_status,
        "new_status": new_status,
        "confidence": change.get("confidence"),
    }


def _apply_create_resource(change, source_note_id, actor, batch_id=None):
    resource = create_entity(
        entity_type="resource",
        title=change["title"],
        content=change.get("content"),
        source="ai",
        actor=actor,
        properties={
            "reference_url": change.get("url"),
        },
        batch_id=batch_id,
    )

    if source_note_id:
        create_link(
            src_id=source_note_id,
            dst_id=resource.id,
            link_type="references",
            source="ai",
            confidence=change.get("confidence"),
            actor=actor,
            batch_id=batch_id,
        )

    return {
        "operation": "create_resource",
        "entity_id": resource.id,
        "title": change["title"],
        "confidence": change.get("confidence"),
    }


def _apply_append_context(change, source_note_id, actor, batch_id=None):
    target_id = change.get("target_entity_id")
    if not target_id:
        return None

    entity = db.session.get(Entity, target_id)
    if not entity:
        return None

    # Link source note to target entity
    if source_note_id:
        create_link(
            src_id=source_note_id,
            dst_id=target_id,
            link_type="related",
            source="ai",
            confidence=change.get("confidence"),
            actor=actor,
        )

    return {
        "operation": "append_context",
        "entity_id": target_id,
        "confidence": change.get("confidence"),
    }


def _apply_complete_task(change, actor, batch_id=None):
    task_id = change.get("target_entity_id")
    if not task_id:
        return None

    from services.entity_service import transition_status
    try:
        entity = transition_status(task_id, "done", actor=actor, batch_id=batch_id)
        return {
            "operation": "complete_task",
            "entity_id": task_id,
            "confidence": change.get("confidence"),
        }
    except ValueError:
        return None


def _create_suggestion(change, source_note_id, batch_id=None):
    """Store a medium-confidence change as a suggestion in the AiSuggestion table."""
    suggestion_type = change.get("operation", "unknown")
    operation_type = _infer_operation_type(change.get("operation"))

    suggestion = AiSuggestion(
        source_entity_id=source_note_id,
        suggestion_type=suggestion_type,
        operation_type=operation_type,
        payload={**change, "change_batch_id": batch_id},
        confidence=change.get("confidence"),
        reason=change.get("reason", "Confidence below auto-apply threshold"),
        status="pending",
    )
    db.session.add(suggestion)
    db.session.flush()
    return {
        "id": suggestion.id,
        "source_note_id": source_note_id,
        "suggestion_type": suggestion_type,
        "operation_type": operation_type,
        "confidence": change.get("confidence"),
        "status": "pending",
        "change_batch_id": batch_id,
    }


def _infer_operation_type(operation):
    """Map operation string to operation_type enum value."""
    mapping = {
        "create_task": "create_new_entity",
        "create_project": "create_new_entity",
        "create_person": "create_new_entity",
        "create_resource": "create_new_entity",
        "link_entity": "link_existing",
        "append_context": "link_existing",
        "complete_task": "update_entity",
    }
    return mapping.get(operation, "create_new_entity")


def batch_undo(change_batch_id, actor="user"):
    """Undo a batch of changes by reversing operations tracked in entity_events.

    Reversal strategy:
    - create_* → delete the created entity (if still exists)
    - link_entity → delete the entity_link
    - complete_task → reopen the task
    - add_follow_up → delete the follow-up task
    - change_status → revert status (using old_value from event)
    """
    from services.entity_service import _write_event as write_event
    from models import ChangeBatch, Entity, EntityLink, EntityEvent

    batch = db.session.get(ChangeBatch, change_batch_id)
    if not batch:
        return None

    if batch.undone_at:
        logger.warning("ChangeBatch %s already undone", change_batch_id)
        return {"error": "already undone", "change_batch_id": change_batch_id}

    undone_entities = []
    undone_links = []

    events = EntityEvent.query.filter(
        EntityEvent.reason.like(f"%change_batch_id={change_batch_id}%")
    ).all()

    if not events:
        events = EntityEvent.query.filter(
            EntityEvent.actor == batch.actor,
            EntityEvent.created_at >= batch.applied_at,
            EntityEvent.created_at <= batch.applied_at,
        ).all()

    for event in events:
        if event.event_type == "created":
            entity_id = event.entity_id
            if entity_id:
                entity = db.session.get(Entity, entity_id)
                if entity and entity.lifecycle == "active":
                    entity.lifecycle = "deleted"
                    undone_entities.append(entity_id)
                    write_event(
                        entity_id=entity_id,
                        event_type="entity_deleted",
                        actor=actor,
                        old_value={"id": entity_id},
                        new_value=None,
                        confidence=1.0,
                        reason=f"undo batch {change_batch_id}",
                    )
        elif event.event_type == "link_added":
            src_id = event.new_value.get("src_id") if event.new_value else None
            dst_id = event.new_value.get("dst_id") if event.new_value else None
            link_type = event.new_value.get("link_type") if event.new_value else None
            if src_id and dst_id:
                link = EntityLink.query.filter_by(
                    src_id=src_id, dst_id=dst_id, link_type=link_type
                ).first()
                if link:
                    db.session.delete(link)
                    undone_links.append({"src_id": src_id, "dst_id": dst_id})
                    write_event(
                        entity_id=src_id,
                        event_type="link_removed",
                        actor=actor,
                        old_value={"src": src_id, "dst": dst_id, "type": link_type},
                        new_value=None,
                        confidence=1.0,
                        reason=f"undo batch {change_batch_id}",
                    )
        elif event.event_type == "status_changed" and event.old_value:
            entity_id = event.entity_id
            old_status = event.old_value.get("status") or event.old_value.get("new")
            if old_status and entity_id:
                entity = db.session.get(Entity, entity_id)
                if entity:
                    entity.status = old_status
                    undone_entities.append(entity_id)
                    write_event(
                        entity_id=entity_id,
                        event_type="status_changed",
                        actor=actor,
                        old_value={"status": entity.status},
                        new_value={"status": old_status},
                        confidence=1.0,
                        reason=f"undo batch {change_batch_id}",
                    )

    batch.undone_at = datetime.now(timezone.utc)
    db.session.commit()

    return {
        "change_batch_id": change_batch_id,
        "undone": True,
        "undone_entities": undone_entities,
        "undone_links": undone_links,
    }
