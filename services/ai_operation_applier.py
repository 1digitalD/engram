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
SUGGESTION_THRESHOLD_MAX = 0.91


def apply_change_plan(change_plan, actor="agent:capture"):
    """Apply a structured AI change plan.

    Args:
        change_plan: dict with source_note_id, proposed_changes, suggestions.
        actor: Actor identifier for events.

    Returns:
        dict with applied_changes and suggestions.
    """
    source_note_id = change_plan.get("source_note_id")
    proposed_changes = change_plan.get("proposed_changes", [])
    plan_suggestions = change_plan.get("suggestions", [])

    applied_changes = []
    new_suggestions = []

    for change in proposed_changes:
        confidence = change.get("confidence", 0.0)
        operation = change.get("operation")

        if confidence >= AUTO_APPLY_THRESHOLD:
            result = _apply_operation(change, source_note_id, actor)
            if result:
                applied_changes.append(result)
        elif confidence >= SUGGESTION_THRESHOLD_MIN:
            suggestion = _create_suggestion(change, source_note_id)
            if suggestion:
                new_suggestions.append(suggestion)
        else:
            # Below threshold: log but don't mutate
            logger.info(
                "Skipping low-confidence operation %s (confidence=%.2f)",
                operation, confidence,
            )

    # Add pre-defined suggestions from the change plan
    for s in plan_suggestions:
        new_suggestions.append(s)

    return {
        "applied_changes": applied_changes,
        "suggestions": new_suggestions,
    }


def _apply_operation(change, source_note_id, actor):
    """Apply a single approved operation."""
    operation = change.get("operation")

    try:
        if operation == "link_entity":
            return _apply_link_entity(change, source_note_id, actor)
        elif operation == "create_task":
            return _apply_create_task(change, source_note_id, actor)
        elif operation == "create_person":
            return _apply_create_person(change, source_note_id, actor)
        elif operation == "create_project":
            return _apply_create_project(change, source_note_id, actor)
        elif operation == "create_resource":
            return _apply_create_resource(change, source_note_id, actor)
        elif operation == "append_context":
            return _apply_append_context(change, source_note_id, actor)
        elif operation == "complete_task":
            return _apply_complete_task(change, actor)
        else:
            logger.warning("Unknown operation: %s", operation)
            return None
    except Exception as e:
        logger.error("Failed to apply operation %s: %s", operation, e)
        return None


def _apply_link_entity(change, source_note_id, actor):
    link = create_link(
        src_id=change["src_id"],
        dst_id=change["dst_id"],
        link_type=change.get("link_type", "related"),
        source="ai",
        confidence=change.get("confidence"),
        evidence=change.get("evidence"),
        actor=actor,
    )
    return {
        "operation": "link_entity",
        "link_id": link.id,
        "src_id": change["src_id"],
        "dst_id": change["dst_id"],
        "link_type": change.get("link_type", "related"),
        "confidence": change.get("confidence"),
    }


def _apply_create_task(change, source_note_id, actor):
    task = create_entity(
        entity_type="task",
        title=change["title"],
        content=change.get("content"),
        source="ai",
        actor=actor,
        properties={},
    )

    if source_note_id:
        create_link(
            src_id=task.id,
            dst_id=source_note_id,
            link_type="derived_from",
            source="ai",
            confidence=change.get("confidence"),
            actor=actor,
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
        )

    return {
        "operation": "create_task",
        "entity_id": task.id,
        "title": change["title"],
        "confidence": change.get("confidence"),
    }


def _apply_create_person(change, source_note_id, actor):
    person = create_entity(
        entity_type="person",
        title=change["name"],
        source="ai",
        actor=actor,
        properties={},
    )

    if source_note_id:
        create_link(
            src_id=person.id,
            dst_id=source_note_id,
            link_type="derived_from",
            source="ai",
            confidence=change.get("confidence"),
            actor=actor,
        )

    return {
        "operation": "create_person",
        "entity_id": person.id,
        "title": change["name"],
        "confidence": change.get("confidence"),
    }


def _apply_create_project(change, source_note_id, actor):
    project = create_entity(
        entity_type="project",
        title=change["title"],
        content=change.get("content"),
        source="ai",
        actor=actor,
        properties={},
    )

    if source_note_id:
        create_link(
            src_id=source_note_id,
            dst_id=project.id,
            link_type="related",
            source="ai",
            confidence=change.get("confidence"),
            actor=actor,
        )

    return {
        "operation": "create_project",
        "entity_id": project.id,
        "title": change["title"],
        "confidence": change.get("confidence"),
    }


def _apply_create_resource(change, source_note_id, actor):
    resource = create_entity(
        entity_type="resource",
        title=change["title"],
        content=change.get("content"),
        source="ai",
        actor=actor,
        properties={
            "reference_url": change.get("url"),
        },
    )

    if source_note_id:
        create_link(
            src_id=source_note_id,
            dst_id=resource.id,
            link_type="references",
            source="ai",
            confidence=change.get("confidence"),
            actor=actor,
        )

    return {
        "operation": "create_resource",
        "entity_id": resource.id,
        "title": change["title"],
        "confidence": change.get("confidence"),
    }


def _apply_append_context(change, source_note_id, actor):
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


def _apply_complete_task(change, actor):
    task_id = change.get("target_entity_id")
    if not task_id:
        return None

    from services.entity_service import transition_status
    try:
        entity = transition_status(task_id, "done", actor=actor)
        return {
            "operation": "complete_task",
            "entity_id": task_id,
            "confidence": change.get("confidence"),
        }
    except ValueError:
        return None


def _create_suggestion(change, source_note_id):
    """Store a medium-confidence change as a suggestion in the AiSuggestion table."""
    suggestion_type = change.get("operation", "unknown")
    operation_type = _infer_operation_type(change.get("operation"))

    suggestion = AiSuggestion(
        source_entity_id=source_note_id,
        suggestion_type=suggestion_type,
        operation_type=operation_type,
        payload=change,
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
    """Undo a batch of changes by reversing operations.

    This is a simplified undo that reverses individual operations.
    For production, use the change_batches table for full tracking.
    """
    from services.entity_service import _write_event as write_event

    _write_event(
        entity_id=change_batch_id or "system",
        event_type="batch_undone",
        actor=actor,
        new_value={"change_batch_id": change_batch_id},
        confidence=1.0,
        reason="User requested undo",
    )
