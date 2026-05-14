"""Entity link service — create, delete, query, cascade preview.

Manages entity_links with parent cardinality enforcement,
orphan detection, and delete cascade preview.
"""

from extensions import db
from models import Entity, EntityLink, LinkTypeAllowlist
from services.entity_service import _get_entity, _write_event
from sqlalchemy.exc import DataError


def _get_link(link_id):
    """Safely get link by ID, handling invalid UUID formats."""
    try:
        return db.session.get(EntityLink, link_id)
    except DataError:
        return None


def _set_inverse(link):
    """Look up and set the inverse link type from the allowlist.

    Call this after creating an EntityLink outside of create_link()
    (e.g. in AI pipeline, ingestion, or migration code).
    Does nothing if src or dst entity is not found.
    """
    if link.inverse:
        return
    from models import LinkTypeAllowlist
    src = _get_entity(link.src_id)
    dst = _get_entity(link.dst_id)
    if src and dst:
        link.inverse = LinkTypeAllowlist.get_inverse(src.type, dst.type, link.link_type)


# ─── Link CRUD ───────────────────────────────────────────────────────────────


def create_link(src_id, dst_id, link_type="related", source="manual",
                confidence=None, evidence=None, actor="user"):
    """Create a link between two entities.

    Args:
        src_id: Source entity UUID.
        dst_id: Destination entity UUID.
        link_type: Type of link ('parent', 'related', 'references', etc.).
        source: Origin ('manual', 'ai', 'embedding', 'system').
        confidence: Confidence score (0-1) for AI/embedding links.
        evidence: Reasoning or note about the link.
        actor: Who created the link.

    Returns:
        The created EntityLink instance.

    Raises:
        ValueError: If src/dst not found, self-link, duplicate, or
                    parent cardinality violated.
    """
    src = _get_entity(src_id)
    if src is None:
        raise ValueError(f"source entity {src_id} not found")
    dst = _get_entity(dst_id)
    if dst is None:
        raise ValueError(f"destination entity {dst_id} not found")

    if src_id == dst_id:
        raise ValueError("cannot link entity to itself")

    # Validate against relationship matrix (link_type_allowlist)
    if not LinkTypeAllowlist.is_allowed(src.type, dst.type, link_type):
        raise ValueError(
            f"link type {link_type!r} not allowed between "
            f"{src.type!r} and {dst.type!r}"
        )

    # Look up inverse link type
    inverse = LinkTypeAllowlist.get_inverse(src.type, dst.type, link_type)

    # Enforce parent cardinality: one parent max per entity
    if link_type == "parent":
        existing = EntityLink.query.filter_by(
            src_id=src_id, link_type="parent"
        ).first()
        if existing:
            raise ValueError(
                f"entity {src_id} already has a parent link "
                f"to {existing.dst_id}"
            )

    # Check for duplicate
    existing = EntityLink.query.filter_by(
        src_id=src_id, dst_id=dst_id, link_type=link_type
    ).first()
    if existing:
        raise ValueError(
            f"link already exists: {src_id} -> {dst_id} ({link_type})"
        )

    link = EntityLink(
        src_id=src_id,
        dst_id=dst_id,
        link_type=link_type,
        inverse=inverse,
        source=source,
        confidence=confidence,
        evidence=evidence,
    )
    db.session.add(link)
    db.session.flush()

    # Write events on both entities
    _write_event(src_id, "link_added", actor,
                 new_value={"link_id": str(link.id), "dst_id": str(dst_id),
                            "link_type": link_type},
                 reason=evidence)
    _write_event(dst_id, "link_added", actor,
                 new_value={"link_id": str(link.id), "src_id": str(src_id),
                            "link_type": link_type},
                 reason=evidence)

    db.session.commit()
    return link


def update_link(link_id, new_link_type, actor="user"):
    """Update a link's link_type. Re-validates against allowlist."""
    link = _get_link(link_id)
    if link is None:
        raise ValueError(f"link {link_id} not found")

    src = _get_entity(link.src_id)
    dst = _get_entity(link.dst_id)
    if src is None or dst is None:
        raise ValueError("linked entities not found")

    if not LinkTypeAllowlist.is_allowed(src.type, dst.type, new_link_type):
        raise ValueError(
            f"link type {new_link_type!r} not allowed between "
            f"{src.type!r} and {dst.type!r}"
        )

    old_link_type = link.link_type
    link.link_type = new_link_type
    link.inverse = LinkTypeAllowlist.get_inverse(src.type, dst.type, new_link_type)
    db.session.flush()

    _write_event(link.src_id, "field_updated", actor,
                 old_value={"link_type": old_link_type},
                 new_value={"link_type": new_link_type, "link_id": str(link_id)})
    _write_event(link.dst_id, "field_updated", actor,
                 old_value={"link_type": old_link_type},
                 new_value={"link_type": new_link_type, "link_id": str(link_id)})

    db.session.commit()
    return link


def delete_link(link_id, actor="user"):
    """Delete a link and write removal events on both entities.

    Args:
        link_id: UUID of the link to delete.
        actor: Who deleted the link.

    Raises:
        ValueError: If link not found.
    """
    link = _get_link(link_id)
    if link is None:
        raise ValueError(f"link {link_id} not found")

    src_id = link.src_id
    dst_id = link.dst_id
    link_type = link.link_type

    db.session.delete(link)

    _write_event(src_id, "link_removed", actor,
                 old_value={"link_id": str(link_id), "dst_id": str(dst_id),
                            "link_type": link_type})
    _write_event(dst_id, "link_removed", actor,
                 old_value={"link_id": str(link_id), "src_id": str(src_id),
                            "link_type": link_type})

    db.session.commit()


def get_links(entity_id, direction="both", link_types=None):
    """Get links for an entity.

    Args:
        entity_id: UUID of the entity.
        direction: 'outgoing', 'incoming', or 'both'.
        link_types: Optional list of link_type strings to filter by.

    Returns:
        List of EntityLink instances.
    """
    query = EntityLink.query

    if direction == "outgoing":
        query = query.filter_by(src_id=entity_id)
    elif direction == "incoming":
        query = query.filter_by(dst_id=entity_id)
    else:
        query = query.filter(
            (EntityLink.src_id == entity_id) | (EntityLink.dst_id == entity_id)
        )

    if link_types:
        query = query.filter(EntityLink.link_type.in_(link_types))

    return query.all()


def delete_preview(entity_id):
    """Preview cascade delete impact for an entity.

    Returns:
        dict with:
            entity: the entity dict
            safe_to_cascade: list of entity IDs that would be orphaned
                (only connected to this entity)
            blocked: list of entity IDs that have other connections
    """
    entity = _get_entity(entity_id)
    if entity is None:
        raise ValueError(f"entity {entity_id} not found")

    # Find all entities linked to this one
    outgoing = EntityLink.query.filter_by(src_id=entity_id).all()
    incoming = EntityLink.query.filter_by(dst_id=entity_id).all()

    linked_ids = set()
    for link in outgoing:
        linked_ids.add(link.dst_id)
    for link in incoming:
        linked_ids.add(link.src_id)

    safe_to_cascade = []
    blocked = []

    for linked_id in linked_ids:
        # Check if this linked entity has any other connections besides this one
        other_links = EntityLink.query.filter(
            ((EntityLink.src_id == linked_id) | (EntityLink.dst_id == linked_id))
            & (EntityLink.src_id != entity_id)
            & (EntityLink.dst_id != entity_id)
        ).all()

        if other_links:
            blocked.append(linked_id)
        else:
            safe_to_cascade.append(linked_id)

    return {
        "entity": entity.to_dict(),
        "safe_to_cascade": safe_to_cascade,
        "blocked": blocked,
    }


# ─── Internal helpers ────────────────────────────────────────────────────────
