from types import SimpleNamespace

from services.v4_narration import ENTITY_EVENT_TYPES, TEMPLATES, narrate_event


def _event(
    event_type,
    new_value=None,
    old_value=None,
    actor="agent:v4-capture",
    reason=None,
    event_id="evt-1",
):
    return SimpleNamespace(
        id=event_id,
        event_type=event_type,
        actor=actor,
        new_value=new_value,
        old_value=old_value,
        reason=reason,
    )


def test_narrate_created_by_agent_includes_type_and_title():
    event = _event(
        "created",
        new_value={"type": "task", "title": "Follow up with Henry"},
        actor="agent:v4-capture",
    )
    assert narrate_event(event) == "I created task 'Follow up with Henry'."


def test_narrate_created_by_user():
    event = _event("created", new_value={"type": "note", "title": "Idea"}, actor="user")
    assert narrate_event(event) == "Created note 'Idea'."


def test_narrate_updated_lists_changed_fields():
    event = _event(
        "updated",
        old_value={"title": "Old", "content": "A"},
        new_value={"title": "New", "content": "B"},
        actor="user",
    )
    assert narrate_event(event) == "Updated content, title."


def test_narrate_updated_by_agent():
    event = _event(
        "updated",
        old_value={"due_at": "2026-06-01T00:00:00+00:00"},
        new_value={"due_at": "2026-06-05T00:00:00+00:00"},
        actor="agent:v4-capture",
    )
    assert narrate_event(event) == "I updated due date."


def test_narrate_status_changed():
    event = _event(
        "status_changed",
        old_value={"status": "open"},
        new_value={"status": "in_progress"},
    )
    assert narrate_event(event) == "Status changed from open to in_progress."


def test_narrate_archived_by_agent():
    event = _event("archived", actor="agent:v4-hygiene")
    assert narrate_event(event) == "I archived this entity."


def test_narrate_deleted_by_user():
    event = _event("deleted", actor="user")
    assert narrate_event(event) == "Deleted this entity."


def test_narrate_relationship_added():
    event = _event(
        "relationship_added",
        new_value={
            "relationship_type": "parent",
            "target_entity_id": "proj-1",
            "target_entity_title": "Memory Lookup",
        },
    )
    assert narrate_event(event) == "Added parent relationship to 'Memory Lookup'."


def test_narrate_relationship_added_without_target_title():
    event = _event(
        "relationship_added",
        new_value={"relationship_type": "assigned_to"},
    )
    assert narrate_event(event) == "Added assigned_to relationship."


def test_narrate_relationship_updated():
    event = _event(
        "relationship_updated",
        old_value={"relationship_type": "related"},
        new_value={"relationship_type": "references"},
    )
    assert narrate_event(event) == "Updated relationship from related to references."


def test_narrate_relationship_removed():
    event = _event(
        "relationship_removed",
        old_value={"relationship_type": "blocks", "target_entity_id": "task-2"},
    )
    assert narrate_event(event) == "Removed blocks relationship."


def test_narrate_tag_added():
    event = _event("tag_added", new_value={"tag": "urgent", "tag_id": "tag-1"})
    assert narrate_event(event) == "Added tag 'urgent'."


def test_narrate_tag_removed():
    event = _event("tag_removed", old_value={"tag": "stale", "tag_id": "tag-2"})
    assert narrate_event(event) == "Removed tag 'stale'."


def test_narrate_ai_processed():
    event = _event("ai_processed", actor="agent:v4-capture")
    assert narrate_event(event) == "I processed this entity."


def test_narration_ai_updated_with_task_created():
    event = _event(
        "ai_updated",
        new_value={"task_created": "Call Henry", "from_note": "Weekly sync"},
        actor="agent:v4-capture",
    )
    assert narrate_event(event) == "I created task 'Call Henry' from your note 'Weekly sync'."


def test_narrate_ai_updated_with_field_changes():
    event = _event(
        "ai_updated",
        old_value={"title": "Old title"},
        new_value={"title": "New title"},
        actor="agent:v4-capture",
    )
    assert narrate_event(event) == "I updated title to 'New title'."


def test_narrate_ai_summarized():
    event = _event("ai_summarized", new_value={"note_count": 3}, actor="agent:v4-summarization")
    assert narrate_event(event) == "I summarized this entity from 3 notes."


def test_narration_suggestion_accepted():
    event = _event(
        "suggestion_accepted",
        new_value={"target_title": "Follow up with Henry"},
        actor="user",
    )
    assert narrate_event(event) == "You accepted the suggestion for 'Follow up with Henry'."


def test_narrate_suggestion_accepted_with_reason_fallback():
    event = _event(
        "suggestion_accepted",
        new_value={"suggestion_id": "sug-1"},
        reason="extracted task from note",
        actor="agent:v4-review",
    )
    assert narrate_event(event) == "I accepted a suggestion: extracted task from note."


def test_narrate_suggestion_dismissed():
    event = _event(
        "suggestion_dismissed",
        reason="low confidence",
        actor="user",
    )
    assert narrate_event(event) == "You dismissed a suggestion: low confidence."


def test_narrate_suggestion_expired():
    event = _event("suggestion_expired")
    assert narrate_event(event) == "A suggestion expired."


def test_narrate_review_marked_resolved():
    event = _event("review_marked_resolved", actor="agent:v4-review")
    assert narrate_event(event) == "I marked the review as resolved."


def test_narrate_activity_update_added():
    event = _event(
        "activity_update_added",
        new_value={"title": "Shipped v4.1"},
        actor="agent:activity-update",
    )
    assert narrate_event(event) == "Added activity update 'Shipped v4.1'."


def test_narrate_reverted():
    event = _event(
        "reverted",
        old_value={"status": "done"},
        new_value={"status": "open"},
        reason="revert of event evt-99",
    )
    assert narrate_event(event) == "Reverted a change: revert of event evt-99."


def test_narrate_merged():
    event = _event(
        "merged",
        old_value={"merged_from": {"title": "Old duplicate", "id": "dup-1"}},
        actor="user",
    )
    assert narrate_event(event) == "Merged duplicate 'Old duplicate' into this entity."


def test_narrate_merged_into():
    event = _event(
        "merged_into",
        new_value={"merged_into": "survivor-1", "lifecycle": "deleted"},
    )
    assert narrate_event(event) == "Merged into another entity."


def test_narrate_type_converted():
    event = _event(
        "type_converted",
        old_value={"type": "task"},
        new_value={"type": "project"},
    )
    assert narrate_event(event) == "Converted from task to project."


def test_narrate_promoted():
    event = _event(
        "promoted",
        old_value={"type": "theme"},
        new_value={"type": "project"},
    )
    assert narrate_event(event) == "Promoted from theme to project."


def test_narration_cache_hit():
    event = _event("created", new_value={"type": "task", "title": "T"}, event_id="cached-evt")
    narrate_event.cache_clear()
    first = narrate_event(event)
    assert narrate_event.cache_info().misses == 1
    second = narrate_event(event)
    assert narrate_event.cache_info().hits == 1
    assert first == second


def test_narration_default_for_unknown_payload():
    event = _event("unknown_event", actor="user")
    assert narrate_event(event) == "Updated this entity."


def test_unknown_event_type_with_agent_actor():
    event = _event("unknown_event", actor="agent:v4-capture")
    assert narrate_event(event) == "I updated this entity."


def test_all_canonical_types_have_templates():
    assert set(ENTITY_EVENT_TYPES) == set(TEMPLATES)
