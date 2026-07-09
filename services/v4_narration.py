"""Templated, deterministic narration for entity_events.

Generated on read, cached per event_id, no LLM call in the read path.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Mapping

from models import EntityEvent


# Per-event_type templates keyed in TEMPLATES below.
ENTITY_EVENT_TYPES = (
    "created",
    "updated",
    "status_changed",
    "archived",
    "deleted",
    "redacted",
    "relationship_added",
    "relationship_updated",
    "relationship_removed",
    "tag_added",
    "tag_removed",
    "ai_processed",
    "ai_updated",
    "ai_summarized",
    "suggestion_accepted",
    "suggestion_dismissed",
    "suggestion_expired",
    "review_marked_resolved",
    "activity_update_added",
    "reverted",
    "merged",
    "merged_into",
    "type_converted",
    "promoted",
    "decision_recorded",
)


def _agent(actor: str | None) -> bool:
    return bool(actor and actor.startswith("agent:"))


def _get(value: Mapping[str, Any] | None, key: str, default: Any = None) -> Any:
    if not isinstance(value, dict):
        return default
    return value.get(key, default)


def _changed_keys(old_value: Mapping[str, Any] | None, new_value: Mapping[str, Any] | None) -> list[str]:
    old = old_value if isinstance(old_value, dict) else {}
    new = new_value if isinstance(new_value, dict) else {}
    keys = set(old) | set(new)
    return sorted(
        k for k in keys
        if json.dumps(old.get(k), sort_keys=True, default=str)
        != json.dumps(new.get(k), sort_keys=True, default=str)
    )


def _humanize_field(key: str) -> str:
    if key == "follow_up_at":
        return "follow-up"
    if key == "due_at":
        return "due date"
    if key == "reference_url":
        return "reference URL"
    return key.replace("_", " ")


def _title(value: Mapping[str, Any] | None) -> str | None:
    return _get(value, "title") or _get(value, "name")


def _template_created(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    entity_type = _get(new_value, "type") or "entity"
    title = _title(new_value)
    subject = f"{entity_type} '{title}'" if title else f"this {entity_type}"
    if _agent(actor):
        return f"I created {subject}."
    return f"Created {subject}."


def _template_updated(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    changed = _changed_keys(old_value, new_value)
    if changed:
        fields = ", ".join(_humanize_field(k) for k in changed)
        if _agent(actor):
            return f"I updated {fields}."
        return f"Updated {fields}."
    if reason:
        return f"Updated: {reason}."
    if _agent(actor):
        return "I updated this entity."
    return "Updated this entity."


def _template_status_changed(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    old_status = _get(old_value, "status")
    new_status = _get(new_value, "status")
    if old_status and new_status:
        return f"Status changed from {old_status} to {new_status}."
    if new_status:
        return f"Status changed to {new_status}."
    return "Status changed."


def _template_archived(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    if _agent(actor):
        return "I archived this entity."
    return "Archived this entity."


def _template_deleted(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    if _agent(actor):
        return "I deleted this entity."
    return "Deleted this entity."


def _template_redacted(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    return "Redacted this note."


def _template_relationship_added(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    rel = _get(new_value, "relationship_type")
    target = (
        _title(new_value)
        or _get(new_value, "target_entity_title")
        or _get(new_value, "target_title")
        or _get(new_value, "target_entity_id")
    )
    if rel and target:
        return f"Added {rel} relationship to '{target}'."
    if rel:
        return f"Added {rel} relationship."
    return "Added a relationship."


def _template_relationship_updated(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    old_rel = _get(old_value, "relationship_type")
    new_rel = _get(new_value, "relationship_type")
    if old_rel and new_rel and old_rel != new_rel:
        return f"Updated relationship from {old_rel} to {new_rel}."
    rel = new_rel or old_rel
    if rel:
        return f"Updated {rel} relationship."
    return "Updated a relationship."


def _template_relationship_removed(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    rel = _get(old_value, "relationship_type") or _get(new_value, "relationship_type")
    if rel:
        return f"Removed {rel} relationship."
    return "Removed a relationship."


def _template_tag_added(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    tag = _get(new_value, "tag") or _get(new_value, "name")
    if tag:
        return f"Added tag '{tag}'."
    return "Added a tag."


def _template_tag_removed(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    tag = _get(old_value, "tag") or _get(old_value, "name") or _get(new_value, "tag") or _get(new_value, "name")
    if tag:
        return f"Removed tag '{tag}'."
    return "Removed a tag."


def _template_ai_processed(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    return "I processed this entity."


def _template_ai_updated(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    task_created = _get(new_value, "task_created")
    from_note = _get(new_value, "from_note")
    if task_created and from_note:
        return f"I created task '{task_created}' from your note '{from_note}'."
    if task_created:
        return f"I created task '{task_created}'."

    changed = _changed_keys(old_value, new_value)
    if changed:
        parts = []
        for key in changed:
            new = _get(new_value, key)
            if key == "title" and new:
                parts.append(f"title to '{new}'")
            elif key == "status" and new:
                parts.append(f"status to {new}")
            elif key == "follow_up_at":
                parts.append(f"follow-up to {new}")
            elif key == "due_at":
                parts.append(f"due date to {new}")
            else:
                parts.append(f"{_humanize_field(key)} to {new}")
        return f"I updated {', '.join(parts)}."

    if reason:
        return f"I updated this entity: {reason}."
    return "I updated this entity."


def _template_ai_summarized(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    note_count = _get(new_value, "note_count")
    if note_count:
        return f"I summarized this entity from {note_count} notes."
    return "I summarized this entity."


def _template_suggestion_accepted(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    target = _get(new_value, "target_title")
    if target:
        return f"You accepted the suggestion for '{target}'."
    if reason:
        prefix = "I accepted" if _agent(actor) else "You accepted"
        return f"{prefix} a suggestion: {reason}."
    prefix = "I accepted" if _agent(actor) else "You accepted"
    return f"{prefix} a suggestion."


def _template_suggestion_dismissed(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    if reason:
        prefix = "I dismissed" if _agent(actor) else "You dismissed"
        return f"{prefix} a suggestion: {reason}."
    prefix = "I dismissed" if _agent(actor) else "You dismissed"
    return f"{prefix} a suggestion."


def _template_suggestion_expired(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    return "A suggestion expired."


def _template_review_marked_resolved(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    return "I marked the review as resolved."


def _template_activity_update_added(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    title = _title(new_value) or _get(new_value, "activity_update_title")
    if title:
        return f"Added activity update '{title}'."
    return "Added an activity update."


def _template_reverted(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    if reason:
        return f"Reverted a change: {reason}."
    return "Reverted a change."


def _template_merged(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    merged_from = _get(old_value, "merged_from")
    from_title = merged_from.get("title") if isinstance(merged_from, dict) else None
    if from_title:
        return f"Merged duplicate '{from_title}' into this entity."
    return "Merged a duplicate into this entity."


def _template_merged_into(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    return "Merged into another entity."


def _template_type_converted(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    old_type = _get(old_value, "type")
    new_type = _get(new_value, "type")
    if old_type and new_type:
        return f"Converted from {old_type} to {new_type}."
    return "Converted this entity to a new type."


def _template_promoted(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    old_type = _get(old_value, "type")
    new_type = _get(new_value, "type")
    if old_type and new_type:
        return f"Promoted from {old_type} to {new_type}."
    return "Promoted this entity."


def _template_decision_recorded(
    event_type: str,
    actor: str,
    new_value: Mapping[str, Any] | None,
    old_value: Mapping[str, Any] | None,
    reason: str | None,
) -> str:
    statement = _get(new_value, "statement")
    if statement:
        return f"Decision recorded: {statement}"
    return "A decision was recorded."


TEMPLATES = {
    "created": _template_created,
    "updated": _template_updated,
    "status_changed": _template_status_changed,
    "archived": _template_archived,
    "deleted": _template_deleted,
    "redacted": _template_redacted,
    "relationship_added": _template_relationship_added,
    "relationship_updated": _template_relationship_updated,
    "relationship_removed": _template_relationship_removed,
    "tag_added": _template_tag_added,
    "tag_removed": _template_tag_removed,
    "ai_processed": _template_ai_processed,
    "ai_updated": _template_ai_updated,
    "ai_summarized": _template_ai_summarized,
    "suggestion_accepted": _template_suggestion_accepted,
    "suggestion_dismissed": _template_suggestion_dismissed,
    "suggestion_expired": _template_suggestion_expired,
    "review_marked_resolved": _template_review_marked_resolved,
    "activity_update_added": _template_activity_update_added,
    "reverted": _template_reverted,
    "merged": _template_merged,
    "merged_into": _template_merged_into,
    "type_converted": _template_type_converted,
    "promoted": _template_promoted,
    "decision_recorded": _template_decision_recorded,
}


def _default_narration(actor: str) -> str:
    if _agent(actor):
        return "I updated this entity."
    return "Updated this entity."


def narrate_event(event: EntityEvent) -> str:
    """Return a one-sentence human-readable narration for an event."""
    return _narrate_event_cached(
        event.id,
        event.event_type,
        event.actor or "",
        json.dumps(event.new_value, sort_keys=True, default=str),
        json.dumps(event.old_value, sort_keys=True, default=str),
        event.reason or "",
    )


@lru_cache(maxsize=10000)
def _narrate_event_cached(
    event_id: str,
    event_type: str,
    actor: str,
    new_value_json: str,
    old_value_json: str,
    reason: str,
) -> str:
    new_value = json.loads(new_value_json) if new_value_json != "null" else None
    old_value = json.loads(old_value_json) if old_value_json != "null" else None
    template = TEMPLATES.get(event_type)
    if template is None:
        return _default_narration(actor)
    return template(event_type, actor, new_value, old_value, reason or None)


narrate_event.cache_info = _narrate_event_cached.cache_info
narrate_event.cache_clear = _narrate_event_cached.cache_clear
