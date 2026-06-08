"""Formatting helpers for the v4 MCP server."""


def format_search_results(payload, query):
    results = payload.get("results") or []
    if not results:
        return f"No v4 entities found for: {query}"

    lines = [f"Search results for '{query}' ({len(results)} found):"]
    for index, result in enumerate(results, 1):
        entity = result.get("entity") or {}
        score = result.get("score")
        score_text = f" score={score:.3f}" if isinstance(score, (int, float)) else ""
        snippet = (result.get("match") or {}).get("snippet")
        lines.append(f"{index}. `{entity.get('id')}` [{entity.get('type')}] {entity.get('title') or 'Untitled'}{score_text}")
        if snippet:
            lines.append(f"   {snippet}")
    return "\n".join(lines)


def format_entity(payload, include_relationships=True):
    entity = payload.get("entity") or payload.get("data") or {}
    if not entity:
        return "Entity not found."

    lines = [
        f"{entity.get('type', 'Entity').capitalize()} `{entity.get('id')}`",
        f"Title: {entity.get('title') or 'Untitled'}",
        f"Status: {entity.get('status')}",
        f"Lifecycle: {entity.get('lifecycle')}",
    ]
    if entity.get("follow_up_at"):
        lines.append(f"Follow-up: {entity['follow_up_at']}")
    if entity.get("content"):
        lines.append(f"\nContent:\n{entity['content']}")

    ai = entity.get("ai") or {}
    if ai.get("summary"):
        lines.append(f"\nAI summary: {ai['summary']}")

    if include_relationships:
        sections = payload.get("sections") or []
        if sections:
            lines.append("\nRelationships:")
            for section in sections:
                items = section.get("items") or []
                if not items:
                    continue
                lines.append(f"- {section.get('title')}:")
                for item in items:
                    related = item.get("entity") or {}
                    relationship = item.get("relationship") or {}
                    lines.append(
                        f"  - `{related.get('id')}` [{relationship.get('relationship_type')}] "
                        f"{related.get('title') or 'Untitled'}"
                    )
    return "\n".join(lines)


def format_recent(payload, entity_type=None):
    entities = payload.get("data") or []
    label = f"recent {entity_type} entities" if entity_type else "recent active entities"
    if not entities:
        return f"No {label} found."

    lines = [f"{label.capitalize()} ({len(entities)}):"]
    for entity in entities:
        lines.append(f"- `{entity.get('id')}` [{entity.get('type')}] {entity.get('title') or 'Untitled'}")
    return "\n".join(lines)


def format_today(payload):
    lines = []

    follow_ups = payload.get("follow_ups") or []
    if follow_ups:
        lines.append(f"Follow-ups ({len(follow_ups)}):")
        for e in follow_ups:
            lines.append(
                f"  - `{e.get('id')}` [{e.get('type')}] {e.get('title') or 'Untitled'}"
                f" (follow-up: {e.get('follow_up_at', '')})"
            )

    blocked = payload.get("blocked_or_waiting_tasks") or []
    if blocked:
        lines.append(f"\nBlocked/waiting tasks ({len(blocked)}):")
        for e in blocked:
            lines.append(f"  - `{e.get('id')}` {e.get('title') or 'Untitled'} [{e.get('status')}]")

    stalled = payload.get("projects_without_open_tasks") or []
    if stalled:
        lines.append(f"\nProjects without open tasks ({len(stalled)}):")
        for e in stalled:
            lines.append(f"  - `{e.get('id')}` {e.get('title') or 'Untitled'}")

    recent_notes = payload.get("recent_notes") or []
    if recent_notes:
        lines.append(f"\nRecent notes ({len(recent_notes)}):")
        for e in recent_notes:
            lines.append(f"  - `{e.get('id')}` {e.get('title') or 'Untitled'}")

    suggestions = payload.get("pending_suggestions") or []
    if suggestions:
        lines.append(f"\nPending AI suggestions ({len(suggestions)}):")
        for s in suggestions:
            lines.append(
                f"  - `{s.get('id')}` [{s.get('suggestion_type')}] {s.get('reason') or ''}"
            )

    if not lines:
        return "Nothing due or pending today."
    return "\n".join(lines)


def format_suggestions(payload):
    suggestions = payload.get("data") or []
    if not suggestions:
        return "No suggestions found."
    lines = [f"AI suggestions ({len(suggestions)}):"]
    for s in suggestions:
        confidence = s.get("confidence") or 0.0
        try:
            conf_text = f" confidence={float(confidence):.2f}"
        except (TypeError, ValueError):
            conf_text = ""
        source = s.get("source_note_title") or "unknown"
        lines.append(
            f"- `{s.get('id')}` [{s.get('suggestion_type')}]{conf_text}"
            f" source='{source}' reason={s.get('reason') or ''}"
        )
    return "\n".join(lines)


def format_capture_result(payload):
    note = payload.get("source_note") or {}
    applied = payload.get("applied_changes") or []
    suggestions = payload.get("suggestions") or []
    warnings = payload.get("warnings") or []
    skipped = payload.get("skipped")

    if skipped:
        return (
            f"Capture skipped: {payload.get('reason', 'duplicate')} "
            f"(existing note `{note.get('id')}`: {note.get('title') or 'Untitled'})"
        )

    lines = [f"Captured note `{note.get('id')}`: {note.get('title') or 'Untitled'}"]
    if applied:
        lines.append(f"Applied {len(applied)} change(s):")
        for change in applied:
            change_type = change.get("type", "")
            if change_type == "entity_created":
                lines.append(
                    f"  + created {change.get('entity_type')} `{change.get('entity_id')}`: {change.get('title')}"
                )
            elif change_type == "relationship_added":
                lines.append(
                    f"  + linked `{change.get('target_entity_id')}` [{change.get('relationship_type')}]"
                )
            elif change_type == "tag_added":
                lines.append(f"  + tag: {change.get('tag')}")
            elif change_type == "summary_updated":
                snippet = (change.get("summary") or "")[:80]
                lines.append(f"  + summary: {snippet}")
            else:
                lines.append(f"  + {change_type}")
    if suggestions:
        lines.append(f"{len(suggestions)} suggestion(s) queued for review.")
    for w in warnings:
        lines.append(f"Warning: {w}")
    return "\n".join(lines)


def format_entity_write(payload):
    entity = payload.get("data") or {}
    if not entity:
        return "Operation failed or returned empty."
    return (
        f"{entity.get('type', 'entity').capitalize()} `{entity.get('id')}` saved:"
        f" {entity.get('title') or 'Untitled'} [{entity.get('status')}]"
    )


def format_link(payload):
    link = payload.get("data") or {}
    if not link:
        return "Relationship operation failed."
    return (
        f"Relationship `{link.get('id')}` created:"
        f" `{link.get('source_entity_id')}` --[{link.get('relationship_type')}]--> `{link.get('target_entity_id')}`"
    )


def format_suggestion_action(payload, action):
    suggestion = payload.get("suggestion") or {}
    created = payload.get("created_entity")
    relationship = payload.get("relationship")

    lines = [f"Suggestion `{suggestion.get('id')}` {action}."]
    if created:
        lines.append(
            f"Created {created.get('type')} `{created.get('id')}`: {created.get('title') or 'Untitled'}"
        )
    if relationship:
        lines.append(
            f"Linked `{relationship.get('source_entity_id')}`"
            f" --[{relationship.get('relationship_type')}]--> `{relationship.get('target_entity_id')}`"
        )
    return "\n".join(lines)


def format_activity_update(payload):
    note = payload.get("data") or {}
    skipped = payload.get("skipped")
    if skipped:
        return f"Activity update skipped: {payload.get('reason', 'duplicate')}"
    if not note:
        return "Activity update failed."
    preview = (note.get("content") or "")[:200]
    suffix = "…" if len(note.get("content") or "") > 200 else ""
    return f"Activity update appended: {preview}{suffix}"
