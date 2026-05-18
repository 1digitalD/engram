"""Formatting helpers for the read-only v4 MCP server."""


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
