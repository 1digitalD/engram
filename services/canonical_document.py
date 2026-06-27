"""On-demand canonical markdown generation for v4 entities."""

from models import Entity, EntityLink
from services.title_utils import title_or_placeholder


def generate_canonical_markdown(entity: Entity) -> str:
    lines = [
        f"# {title_or_placeholder(entity)}",
        "",
        f"Type: {entity.type}",
        f"Status: {entity.status}",
        f"Lifecycle: {entity.lifecycle}",
    ]

    if entity.follow_up_at is not None:
        lines.append(f"Follow-up: {_fmt(entity.follow_up_at)}")

    for key, value in sorted((entity.properties or {}).items()):
        lines.append(f"{_label(key)}: {value}")

    lines.extend([
        "",
        "## Content",
        entity.content or "",
        "",
        "## Relationships",
    ])
    relationships = _relationship_lines(entity)
    lines.extend(relationships or ["None"])

    tag_names = [
        entity_tag.tag.name
        for entity_tag in entity.entity_tags
        if getattr(entity_tag, "tag", None) is not None
    ]
    lines.extend([
        "",
        "## Tags",
        ", ".join(tag_names) if tag_names else "None",
        "",
        "## Source",
        f"Source: {entity.source or 'manual'}",
        f"Reference URL: {entity.reference_url}" if entity.reference_url else "Reference URL: None",
        f"Created: {_fmt(entity.created_at)}",
        f"Updated: {_fmt(entity.updated_at)}",
    ])
    return "\n".join(lines).strip() + "\n"


def _relationship_lines(entity):
    lines = []
    outgoing = EntityLink.query.filter_by(source_entity_id=entity.id).all()
    incoming = EntityLink.query.filter_by(target_entity_id=entity.id).all()

    for link in outgoing:
        target = link.target_entity
        if target is None:
            continue
        lines.append(f"- {link.relationship_type} {target.type}: {target.title or target.id}")
    for link in incoming:
        source = link.source_entity
        if source is None:
            continue
        lines.append(f"- incoming {link.relationship_type} {source.type}: {source.title or source.id}")
    return lines


def _label(key):
    return key.replace("_", " ").capitalize()


def _fmt(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        from datetime import timezone
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat()
    return str(value)
