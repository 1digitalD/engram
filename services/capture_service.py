"""Capture service — processes natural-language captures through the AI pipeline.

Produces structured change plans linking everything back to the source note.
"""

import logging

from extensions import db
from models import Entity
from services.entity_service import create_entity, _write_event
from services.ai_pipeline import enqueue_classify, enqueue_embed
from services.entity_reconciliation_service import reconcile_all
from services.ai_operation_applier import apply_change_plan
from services.extractor import inline_extract

logger = logging.getLogger(__name__)


def _build_change_plan(source_note_id, reconciled, content):
    """Build a change plan from reconciliation results."""
    proposed_changes = []
    suggestions = []

    for r in reconciled:
        detected = r.get("detected", {})
        recon = r.get("reconciliation")

        if detected.get("type") == "task":
            name = detected.get("name", "")
            priority = detected.get("priority", "MEDIUM")
            deadline_hint = detected.get("deadline_hint")
            project_hint = detected.get("project_hint")

            if recon:
                confidence = recon.get("confidence", 0.88)
                matched = recon.get("matched_entity")
            else:
                confidence = 0.75
                matched = None

            if matched:
                change = {
                    "operation": "link_entity",
                    "src_id": source_note_id,
                    "dst_id": matched.id,
                    "link_type": "related",
                    "confidence": confidence,
                    "reason": f"Task '{name}' matched existing",
                    "title": name,
                    "type": "task",
                    "label": "Linked existing",
                }
            else:
                change = {
                    "operation": "create_task",
                    "title": name,
                    "content": None,
                    "confidence": confidence,
                    "reason": f"New task extracted from capture",
                    "priority": priority,
                    "type": "task",
                    "label": "Created",
                }
                if deadline_hint:
                    change["deadline_hint"] = deadline_hint
                if project_hint:
                    change["project_hint"] = project_hint

            if confidence >= 0.92:
                proposed_changes.append(change)
            else:
                suggestions.append(change)

    return {
        "source_note_id": source_note_id,
        "proposed_changes": proposed_changes,
        "suggestions": suggestions,
    }


def process_capture(content, mode="auto", source="quick_capture"):
    """Process a natural-language capture through the AI pipeline.

    Args:
        content: Raw natural-language text.
        mode: capture mode (auto, note, task, resource, person).
        source: Origin identifier.

    Returns:
        dict with source_note, applied_changes, suggestions, warnings.
    """
    if mode in ("auto", "note"):
        return _capture_as_note(content, source)
    elif mode == "task":
        return _capture_as_task(content, source)
    elif mode == "resource":
        return _capture_as_resource(content, source)
    elif mode == "person":
        return _capture_as_person(content, source)
    else:
        return _capture_as_note(content, source)


def _capture_as_note(content, source):
    """Save as source note, trigger AI pipeline, return structured result."""
    note = _create_source_note(content, source)

    applied_changes = [{
        "operation": "create_entity",
        "type": "note",
        "entity_id": note.id,
        "title": _first_line(content),
        "confidence": 1.0,
    }]

    detected = inline_extract(content)
    if detected:
        reconciled = reconcile_all(detected)
        change_plan = _build_change_plan(note.id, reconciled, content)
        if change_plan["proposed_changes"] or change_plan["suggestions"]:
            result = apply_change_plan(change_plan, actor="agent:capture")
            applied_changes.extend(result["applied_changes"])

    enqueue_classify(note.id)
    enqueue_embed(note.id)
    db.session.commit()

    return {
        "source_note": _safe_to_dict(note),
        "applied_changes": applied_changes,
        "suggestions": [],
        "warnings": [],
    }


def _capture_as_task(content, source):
    """Create task directly, with entity reconciliation."""
    title = _first_line(content) or content[:80]

    # Check for existing task
    from services.entity_reconciliation_service import reconcile_task
    existing = reconcile_task(title)
    if existing and existing.get("confidence", 0) >= 0.88:
        return {
            "source_note": None,
            "applied_changes": [{
                "operation": "link_existing_entity",
                "type": "task",
                "entity_id": existing["matched_entity"].id,
                "title": existing["matched_entity"].title,
                "confidence": existing["confidence"],
            }],
            "suggestions": [],
            "warnings": [],
        }

    task = create_entity(
        entity_type="task",
        title=title,
        content=content,
        source=source,
        actor="user",
        properties={},
    )
    db.session.commit()

    return {
        "source_note": None,
        "applied_changes": [{
            "operation": "create_entity",
            "type": "task",
            "entity_id": task.id,
            "title": title,
            "confidence": 1.0,
        }],
        "suggestions": [],
        "warnings": [],
    }


def _capture_as_resource(content, source):
    """Create resource directly, with URL deduplication."""
    title = _first_line(content) or "Untitled resource"

    # Check for existing resource by URL in content
    import re
    urls = re.findall(r'https?://[^\s]+', content)
    if urls:
        from services.entity_reconciliation_service import reconcile_resource
        existing = reconcile_resource(url=urls[0])
        if existing:
            return {
                "source_note": None,
                "applied_changes": [{
                    "operation": "link_existing_entity",
                    "type": "resource",
                    "entity_id": existing["matched_entity"].id,
                    "title": existing["matched_entity"].title,
                    "confidence": existing["confidence"],
                }],
                "suggestions": [],
                "warnings": [],
            }

    resource = create_entity(
        entity_type="resource",
        title=title,
        content=content,
        source=source,
        actor="user",
        properties={},
    )

    # Store URL in reference_url if found
    if urls:
        from services.entity_service import update_entity
        update_entity(resource.id, {"reference_url": urls[0]}, actor="user")

    db.session.commit()

    return {
        "source_note": None,
        "applied_changes": [{
            "operation": "create_entity",
            "type": "resource",
            "entity_id": resource.id,
            "title": title,
            "confidence": 1.0,
        }],
        "suggestions": [],
        "warnings": [],
    }


def _capture_as_person(content, source):
    """Create person directly, with deduplication."""
    title = _first_line(content) or content[:80]

    from services.entity_reconciliation_service import reconcile_person
    existing = reconcile_person(title)
    if existing and existing.get("confidence", 0) >= 0.88:
        return {
            "source_note": None,
            "applied_changes": [{
                "operation": "link_existing_entity",
                "type": "person",
                "entity_id": existing["matched_entity"].id,
                "title": existing["matched_entity"].title,
                "confidence": existing["confidence"],
            }],
            "suggestions": [],
            "warnings": [],
        }

    person = create_entity(
        entity_type="person",
        title=title,
        source=source,
        actor="user",
        properties={},
    )
    db.session.commit()

    return {
        "source_note": None,
        "applied_changes": [{
            "operation": "create_entity",
            "type": "person",
            "entity_id": person.id,
            "title": title,
            "confidence": 1.0,
        }],
        "suggestions": [],
        "warnings": [],
    }


def _create_source_note(content, source):
    """Create a source note and record the capture event."""
    note = create_entity(
        entity_type="note",
        title=_first_line(content),
        content=content,
        source=source,
        actor="user",
        properties={},
    )
    _write_event(
        entity_id=note.id,
        event_type="ai_interpreted",
        actor="user",
        new_value={"source": source, "mode": "capture"},
        confidence=1.0,
        reason="Original capture saved",
    )
    return note


def _first_line(text):
    """Extract first meaningful line from text."""
    if not text:
        return "Untitled"
    for line in text.strip().split("\n"):
        line = line.strip().strip("#").strip()
        if line:
            return line[:120]
    return "Untitled"


def _safe_to_dict(entity):
    """Safely convert entity to dict, handling detached state."""
    try:
        return entity.to_dict()
    except Exception:
        return {"id": str(entity.id), "title": entity.title, "type": entity.type}
