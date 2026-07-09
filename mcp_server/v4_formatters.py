"""Formatting helpers for the v4 MCP server."""


def _entity_title_text(entity, *, id_on_line=False, type_on_line=False):
    title = entity.get("title")
    if title:
        return title

    parts = ["(no title)"]
    if not id_on_line:
        entity_id = entity.get("id")
        if entity_id:
            parts.append(f"`{entity_id}`")
    if not type_on_line:
        entity_type = entity.get("type")
        if entity_type:
            parts.append(f"[{entity_type}]")
    return " ".join(parts)


def format_search_results(payload, query):
    results = payload.get("results") or []
    if not results:
        return f"No v4 entities found for: {query}"

    lines = [f"Search results for '{query}' ({len(results)} found):"]
    for index, result in enumerate(results, 1):
        entity = result.get("entity") or {}
        score = result.get("score")
        score_text = f" score={score:.3f}" if isinstance(score, (int, float)) else ""
        match = result.get("match") or {}
        snippet = match.get("snippet")
        source = match.get("source")
        source_text = f" source={source}" if source else ""
        lines.append(
            f"{index}. `{entity.get('id')}` [{entity.get('type')}] "
            f"{_entity_title_text(entity, id_on_line=True, type_on_line=True)}{score_text}{source_text}"
        )
        if snippet:
            lines.append(f"   {snippet}")
    return "\n".join(lines)


def format_entity(payload, include_relationships=True):
    entity = payload.get("entity") or payload.get("data") or {}
    if not entity:
        return "Entity not found."

    lines = [
        f"{entity.get('type', 'Entity').capitalize()} `{entity.get('id')}`",
        f"Title: {_entity_title_text(entity, id_on_line=True, type_on_line=True)}",
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
                        f"{_entity_title_text(related, id_on_line=True)}"
                    )
    return "\n".join(lines)


def format_recent(payload, entity_type=None):
    entities = payload.get("data") or []
    label = f"recent {entity_type} entities" if entity_type else "recent active entities"
    if not entities:
        return f"No {label} found."

    lines = [f"{label.capitalize()} ({len(entities)}):"]
    for entity in entities:
        lines.append(
            f"- `{entity.get('id')}` [{entity.get('type')}] "
            f"{_entity_title_text(entity, id_on_line=True, type_on_line=True)}"
        )
    return "\n".join(lines)


def _attention_text(entity):
    attention = entity.get("attention") or {}
    score = attention.get("score")
    if not isinstance(score, (int, float)) or score <= 0:
        return ""
    reason = (attention.get("reasons") or [{}])[0].get("label")
    detail = f", {reason}" if reason else ""
    return f" attention={attention.get('level')}:{score}{detail}"


def format_today(payload):
    lines = []

    follow_ups = payload.get("follow_ups") or []
    if follow_ups:
        lines.append(f"Follow-ups ({len(follow_ups)}):")
        for e in follow_ups:
            lines.append(
                f"  - `{e.get('id')}` [{e.get('type')}] "
                f"{_entity_title_text(e, id_on_line=True, type_on_line=True)}"
                f" (follow-up: {e.get('follow_up_at', '')}){_attention_text(e)}"
            )

    blocked = payload.get("blocked_or_waiting_tasks") or []
    if blocked:
        lines.append(f"\nBlocked/waiting tasks ({len(blocked)}):")
        for e in blocked:
            lines.append(
                f"  - `{e.get('id')}` {_entity_title_text(e, id_on_line=True)} "
                f"[{e.get('status')}]{_attention_text(e)}"
            )

    stalled = payload.get("projects_without_open_tasks") or []
    if stalled:
        lines.append(f"\nProjects without open tasks ({len(stalled)}):")
        for e in stalled:
            lines.append(f"  - `{e.get('id')}` {_entity_title_text(e, id_on_line=True)}{_attention_text(e)}")

    recent_notes = payload.get("recent_notes") or []
    if recent_notes:
        lines.append(f"\nRecent notes ({len(recent_notes)}):")
        for e in recent_notes:
            lines.append(f"  - `{e.get('id')}` {_entity_title_text(e, id_on_line=True)}{_attention_text(e)}")

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


def format_agent_activity(payload):
    items = payload.get("data") or []
    if not items:
        return "No agent activity found."
    lines = [f"Agent activity ({len(items)}):"]
    for item in items:
        entity = item.get("entity") or {}
        confidence = item.get("confidence")
        try:
            conf_text = f" confidence={float(confidence):.2f}" if confidence is not None else ""
        except (TypeError, ValueError):
            conf_text = ""
        entity_text = (
            f"`{entity.get('id')}` [{entity.get('type')}] "
            f"{_entity_title_text(entity, id_on_line=True, type_on_line=True)}"
            if entity else "no source entity"
        )
        lines.append(
            f"- [{item.get('category')}] {item.get('event_type')} {entity_text}"
            f"{conf_text} actor={item.get('actor')}"
        )
        if item.get("reason"):
            lines.append(f"  reason: {item['reason']}")
    return "\n".join(lines)


def format_suggestion_reconcile(payload):
    meta = payload.get("meta") or {}
    items = payload.get("data") or []
    if not items:
        return f"Suggestion reconcile complete: scanned={meta.get('scanned', 0)}, expired=0."
    lines = [f"Suggestion reconcile complete: scanned={meta.get('scanned', 0)}, expired={meta.get('expired', len(items))}."]
    for item in items:
        lines.append(f"- `{item.get('id')}` expired [{item.get('suggestion_type')}] reason={item.get('reason') or ''}")
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
    source = payload.get("source_entity") or payload.get("source_note") or {}
    applied = payload.get("applied_changes") or []
    suggestions = payload.get("suggestions") or []
    warnings = payload.get("warnings") or []
    skipped = payload.get("skipped")

    if skipped:
        return (
            f"Capture skipped: {payload.get('reason', 'duplicate')} "
            f"(existing note `{source.get('id')}`: {_entity_title_text(source, id_on_line=True)})"
        )

    source_type = source.get("type") or "entity"
    lines = [
        f"Ingested on {source_type} `{source.get('id')}`: "
        f"{_entity_title_text(source, id_on_line=True)}"
    ]
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
    report_id = payload.get("report_id")
    if report_id:
        lines.append(f"Report `{report_id}` is ready for review.")
    for w in warnings:
        lines.append(f"Warning: {w}")
    return "\n".join(lines)


def format_entity_write(payload):
    entity = payload.get("data") or {}
    if not entity:
        return "Operation failed or returned empty."
    return (
        f"{entity.get('type', 'entity').capitalize()} `{entity.get('id')}` saved:"
        f" {_entity_title_text(entity, id_on_line=True, type_on_line=True)} [{entity.get('status')}]"
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
            f"Created {created.get('type')} `{created.get('id')}`: "
            f"{_entity_title_text(created, id_on_line=True, type_on_line=True)}"
        )
    if relationship:
        lines.append(
            f"Linked `{relationship.get('source_entity_id')}`"
            f" --[{relationship.get('relationship_type')}]--> `{relationship.get('target_entity_id')}`"
        )
    return "\n".join(lines)


def format_reports_list(payload):
    reports = payload.get("data") or []
    meta = payload.get("meta") or {}
    if not reports:
        return "No distillation reports found."

    lines = [f"Distillation reports ({len(reports)} of {meta.get('total', len(reports))}):"]
    for report in reports:
        stats = report.get("stats") or {}
        suggestion_count = stats.get("suggestion_count")
        count_text = f", {suggestion_count} suggestion(s)" if suggestion_count is not None else ""
        lines.append(
            f"- `{report.get('id')}` [{report.get('status')}] "
            f"source=`{report.get('source_note_id')}`{count_text}"
        )
    return "\n".join(lines)


def format_report_detail(payload):
    report = payload.get("data") or {}
    if not report:
        return "Report not found."

    lines = [
        f"Report `{report.get('id')}` [{report.get('status')}]",
        f"Source note: `{report.get('source_note_id')}`",
    ]
    narrative = report.get("narrative") or {}
    summary = narrative.get("summary")
    if summary:
        lines.append(f"Summary: {summary}")
    sections = narrative.get("sections") or []
    if sections:
        lines.append(f"Sections ({len(sections)}):")
        for section in sections:
            title = section.get("title") or section.get("key") or "section"
            lines.append(f"  - {title}")

    source_note = payload.get("source_note") or {}
    if source_note.get("title"):
        lines.append(f"Note title: {source_note.get('title')}")

    suggestions = payload.get("suggestions") or []
    if suggestions:
        lines.append(f"Suggestions ({len(suggestions)}):")
        for suggestion in suggestions:
            confidence = suggestion.get("confidence")
            try:
                conf_text = f" confidence={float(confidence):.2f}" if confidence is not None else ""
            except (TypeError, ValueError):
                conf_text = ""
            lines.append(
                f"  - `{suggestion.get('id')}` [{suggestion.get('operation_type')}]{conf_text} "
                f"{suggestion.get('reason') or ''}"
            )
    return "\n".join(lines)


def format_resolve_report(payload):
    report = payload.get("data") or {}
    meta = payload.get("meta") or {}
    if not report:
        return "Report resolve failed or returned empty."

    lines = [
        f"Report `{report.get('id')}` resolved [{report.get('status')}]",
        f"Applied: {meta.get('applied', 0)}, dismissed: {meta.get('dismissed', 0)}, "
        f"later: {meta.get('later', 0)}",
    ]
    batch = payload.get("change_batch") or {}
    if batch.get("id"):
        lines.append(f"Change batch: `{batch.get('id')}`")
    return "\n".join(lines)


def format_workboard(payload):
    data = payload.get("data") or {}
    groups = data.get("groups") or []
    meta = payload.get("meta") or {}
    counts = meta.get("counts") or {}
    total = meta.get("total", 0)

    if total == 0:
        return "Workboard is empty."

    count_bits = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()) if value)
    lines = [
        f"Workboard ({total} task(s), group={meta.get('group', 'space')})",
    ]
    if count_bits:
        lines.append(f"Counts: {count_bits}")
    filters = meta.get("state_filters") or []
    if filters:
        lines.append(f"Filters: {', '.join(filters)}")

    for group in groups:
        label = group.get("label") or group.get("key") or "group"
        items = group.get("items") or []
        if not items:
            continue
        lines.append(f"\n{label} ({len(items)}):")
        for item in items:
            states = item.get("states") or {}
            active_states = [name for name, active in states.items() if active and name != "at_risk_detail"]
            state_text = f" [{', '.join(active_states)}]" if active_states else ""
            owner = (item.get("owner") or {}).get("title")
            owner_text = f" owner={owner}" if owner else ""
            lines.append(
                f"  - `{item.get('id')}` {item.get('title') or '(no title)'}"
                f" [{item.get('status')}]{state_text}{owner_text}"
            )
    return "\n".join(lines)


def format_marker(payload):
    marker = payload.get("data") or {}
    if not marker:
        return "Marker operation failed or returned empty."
    lines = [
        f"Marker `{marker.get('id')}` [{marker.get('kind')}] on entity `{marker.get('entity_id')}`",
    ]
    if marker.get("due_at"):
        lines.append(f"Due: {marker.get('due_at')}")
    if marker.get("person_entity_id"):
        lines.append(f"Person: `{marker.get('person_entity_id')}`")
    if marker.get("note"):
        lines.append(f"Note: {marker.get('note')}")
    return "\n".join(lines)


def format_nudge_draft(payload):
    data = payload.get("data") or {}
    if not data:
        return "Nudge draft failed or returned empty."

    lines = [
        f"Nudge draft for commitment `{data.get('commitment_id')}`",
        f"Original ask: {data.get('original_ask') or '(unknown)'}",
    ]
    if data.get("committed_at"):
        lines.append(f"Committed: {data.get('committed_at')}")
    if data.get("draft"):
        lines.append(f"\nDraft:\n{data.get('draft')}")
    receipts = data.get("receipts") or []
    if receipts:
        lines.append(f"\nReceipts ({len(receipts)}):")
        for receipt in receipts[:5]:
            label = receipt.get("label") or receipt.get("field") or receipt.get("kind") or "receipt"
            value = receipt.get("value") or receipt.get("quote") or ""
            lines.append(f"  - {label}: {value}")
    if data.get("auto_sent"):
        lines.append("Warning: auto_sent is true (unexpected).")
    return "\n".join(lines)


def format_activity_update(payload):
    note = payload.get("data") or {}
    skipped = payload.get("skipped")
    if skipped:
        return f"Activity update skipped: {payload.get('reason', 'duplicate')}"
    if not note:
        return "Activity update failed."

    lines = []
    preview = (note.get("content") or "")[:200]
    suffix = "\u2026" if len(note.get("content") or "") > 200 else ""
    lines.append(f"Activity update appended: {preview}{suffix}")

    extracted = payload.get("extracted") or {}
    follow_up = extracted.get("follow_up_at")
    if follow_up:
        lines.append(f"Follow-up set to: {follow_up} (extracted from update)")

    tasks = extracted.get("tasks") or []
    if tasks:
        auto_created = [t for t in tasks if t.get("auto_created")]
        suggested = [t for t in tasks if not t.get("auto_created")]
        if auto_created:
            names = ", ".join(t.get("title", "") for t in auto_created)
            lines.append(f"Auto-created {len(auto_created)} task(s): {names}")
        if suggested:
            names = ", ".join(t.get("title", "") for t in suggested)
            lines.append(f"Queued {len(suggested)} task suggestion(s) for review: {names}")

    return "\n".join(lines)
