"""Shared helpers for entity title display."""


def title_or_placeholder(entity, include_type=True):
    """Return an entity's title, or a consistent placeholder if it has none.

    The placeholder matches the pattern used by the MCP formatters and the
    React entityTitleLabel helper: ``(no title)`` plus the entity id and,
    when requested, its type so rows remain actionable.
    """
    title = getattr(entity, "title", None)
    if title:
        return title

    parts = ["(no title)"]
    entity_id = getattr(entity, "id", None)
    if entity_id is not None:
        parts.append(str(entity_id))
    if include_type:
        entity_type = getattr(entity, "type", None)
        if entity_type:
            parts.append(f"[{entity_type}]")
    return " ".join(parts)
