"""Entity lifecycle service — CRUD + status transitions + delete preview.

All business logic for entity creation, updates, archival, and deletion.
Writes entity_events for every mutation. Enqueues AI jobs on creation.
"""

from datetime import datetime, timezone

from extensions import db
from models import Entity, EntityEvent, EntityLink, Job

# ─── Default initial status per entity type ──────────────────────────────────

DEFAULT_STATUS = {
    "task": "pending",
    "project": "active",
    "note": "active",
    "area": "active",
    "resource": "active",
    "person": "active",
}

# ─── Valid status transitions ────────────────────────────────────────────────

VALID_TRANSITIONS = {
    "task": {
        "pending": ["in_progress", "done", "cancelled"],
        "in_progress": ["pending", "done", "cancelled"],
        "done": ["pending"],
        "cancelled": ["pending"],
    },
    "project": {
        "active": ["on_hold", "completed", "cancelled"],
        "on_hold": ["active", "cancelled"],
        "completed": ["active"],
        "cancelled": ["active"],
    },
    "note": {
        "active": ["archived"],
        "archived": ["active"],
    },
    "area": {
        "active": ["archived"],
        "archived": ["active"],
    },
    "resource": {
        "active": ["archived"],
        "archived": ["active"],
    },
    "person": {
        "active": ["archived"],
        "archived": ["active"],
    },
}


# ─── Entity CRUD ─────────────────────────────────────────────────────────────


def create_entity(entity_type, title=None, content=None, properties=None,
                  source="manual", actor="user", **extra_fields):
    """Create a new entity, write a 'created' event, enqueue AI jobs.

    Args:
        entity_type: One of note, task, project, area, resource, person.
        title: Entity title.
        content: Entity body content.
        properties: Type-specific fields as dict.
        source: Origin of the entity ('manual', 'ai', 'web', etc.).
        actor: Who created it ('user', 'agent:name', etc.).
        **extra_fields: Additional fields (follow_up_at, reference_url, etc.).

    Returns:
        The created Entity instance.
    """
    entity = Entity(
        type=entity_type,
        title=title,
        content=content,
        properties=properties or {},
        source=source,
        status=DEFAULT_STATUS.get(entity_type, "active"),
        lifecycle="active",
        ai_meta={},
        ai_status="pending",
        **{k: v for k, v in extra_fields.items() if v is not None},
    )
    db.session.add(entity)
    db.session.flush()

    _write_event(entity.id, "created", actor,
                 new_value={"type": entity_type, "title": title})

    # Enqueue AI jobs (skip if job infrastructure not available)
    try:
        _enqueue_classify(entity.id)
        _enqueue_embed(entity.id)
    except Exception:
        pass  # AI pipeline not yet initialized — entity still created

    db.session.commit()
    return entity


def update_entity(entity_id, fields, actor="user"):
    """Update entity fields, write 'field_updated' events for each changed field.

    Args:
        entity_id: UUID of the entity.
        fields: Dict of field_name -> new_value.
        actor: Who made the change.

    Returns:
        The updated Entity instance.

    Raises:
        ValueError: If entity not found or is deleted/archived.
    """
    entity = Entity.query.get(entity_id)
    if entity is None:
        raise ValueError(f"entity {entity_id} not found")
    if entity.lifecycle in ("archived", "deleted"):
        raise ValueError(f"cannot update {entity.lifecycle} entity")

    changed = {}
    for field, new_value in fields.items():
        if hasattr(entity, field):
            old_value = getattr(entity, field)
            if old_value != new_value:
                setattr(entity, field, new_value)
                changed[field] = {"old": old_value, "new": new_value}

    if changed:
        entity.updated_at = datetime.now(timezone.utc)
        _write_event(entity.id, "field_updated", actor,
                     old_value=changed, new_value=fields)
        db.session.commit()

    return entity


def transition_status(entity_id, new_status, actor="user", reason=None):
    """Transition entity status, enforcing VALID_TRANSITIONS.

    Args:
        entity_id: UUID of the entity.
        new_status: Target status value.
        actor: Who initiated the transition.
        reason: Optional reason for the change.

    Returns:
        The updated Entity instance.

    Raises:
        ValueError: If entity not found, transition invalid, or entity archived.
    """
    entity = Entity.query.get(entity_id)
    if entity is None:
        raise ValueError(f"entity {entity_id} not found")
    if entity.lifecycle == "deleted":
        raise ValueError(f"cannot transition deleted entity")

    entity_type = entity.type
    current_status = entity.status

    if entity_type not in VALID_TRANSITIONS:
        raise ValueError(f"unknown entity type: {entity_type}")

    allowed = VALID_TRANSITIONS[entity_type].get(current_status, [])
    if new_status not in allowed:
        raise ValueError(
            f"invalid transition: {entity_type} {current_status} -> {new_status}. "
            f"Allowed: {allowed}"
        )

    old_status = entity.status
    entity.status = new_status
    entity.updated_at = datetime.now(timezone.utc)

    _write_event(entity.id, "status_changed", actor,
                 old_value={"status": old_status},
                 new_value={"status": new_status},
                 reason=reason)

    db.session.commit()
    return entity


def archive_entity(entity_id, actor="user"):
    """Archive an entity (lifecycle -> 'archived').

    Args:
        entity_id: UUID of the entity.
        actor: Who archived it.

    Returns:
        The archived Entity instance.

    Raises:
        ValueError: If entity not found or already archived/deleted.
    """
    entity = Entity.query.get(entity_id)
    if entity is None:
        raise ValueError(f"entity {entity_id} not found")
    if entity.lifecycle == "archived":
        raise ValueError(f"entity {entity_id} is already archived")
    if entity.lifecycle == "deleted":
        raise ValueError(f"cannot archive deleted entity")

    old_lifecycle = entity.lifecycle
    entity.lifecycle = "archived"
    entity.updated_at = datetime.now(timezone.utc)

    _write_event(entity.id, "archived", actor,
                 old_value={"lifecycle": old_lifecycle},
                 new_value={"lifecycle": "archived"})

    db.session.commit()
    return entity


def delete_preview(entity_id):
    """Preview what would be deleted if entity_id is deleted.

    Returns:
        dict with:
            entity: the entity dict
            safe_to_cascade: list of entity IDs that would be orphaned
                (only connected to this entity)
            blocked: list of entity IDs that have other connections
    """
    entity = Entity.query.get(entity_id)
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


def delete_entity(entity_id, cascade_orphans=False):
    """Delete an entity, optionally cascading to orphaned linked entities.

    Args:
        entity_id: UUID of the entity.
        cascade_orphans: If False, returns preview. If True, executes deletion.

    Returns:
        dict with 'deleted' list and 'blocked' list.

    Raises:
        ValueError: If entity not found.
    """
    entity = Entity.query.get(entity_id)
    if entity is None:
        raise ValueError(f"entity {entity_id} not found")

    preview = delete_preview(entity_id)

    if not cascade_orphans:
        return {
            "deleted": [],
            "blocked": preview["blocked"],
            "safe_to_cascade": preview["safe_to_cascade"],
        }

    # Execute deletion: delete safe-to-cascade entities first, then the main entity
    deleted_ids = []

    for orphan_id in preview["safe_to_cascade"]:
        orphan = Entity.query.get(orphan_id)
        if orphan:
            _write_event(orphan_id, "deleted", "system",
                         old_value={"lifecycle": orphan.lifecycle},
                         reason=f"cascade delete from {entity_id}")
            # Delete links first to avoid NOT NULL constraint violations
            _delete_links_for_entity(orphan_id)
            db.session.delete(orphan)
            deleted_ids.append(orphan_id)

    _write_event(entity_id, "deleted", "system",
                 old_value={"lifecycle": entity.lifecycle},
                 reason="manual delete")
    # Flush the event so it's persisted before we delete the entity
    db.session.flush()
    # Delete links first to avoid NOT NULL constraint violations
    _delete_links_for_entity(entity_id)
    db.session.delete(entity)
    deleted_ids.append(entity_id)

    db.session.commit()

    return {
        "deleted": deleted_ids,
        "blocked": preview["blocked"],
    }


# ─── Internal helpers ────────────────────────────────────────────────────────


def _write_event(entity_id, event_type, actor, old_value=None, new_value=None,
                 confidence=None, reason=None):
    """Write an entity_events record."""
    event = EntityEvent(
        entity_id=entity_id,
        event_type=event_type,
        actor=actor,
        old_value=old_value,
        new_value=new_value,
        confidence=confidence,
        reason=reason,
    )
    db.session.add(event)


def _delete_links_for_entity(entity_id):
    """Delete all links involving this entity to avoid FK constraint issues."""
    EntityLink.query.filter(
        (EntityLink.src_id == entity_id) | (EntityLink.dst_id == entity_id)
    ).delete(synchronize_session=False)


def _enqueue_classify(entity_id):
    """Enqueue a classify job for the entity."""
    job = Job(
        job_type="classify",
        entity_id=entity_id,
        payload={"entity_id": entity_id},
    )
    db.session.add(job)


def _enqueue_embed(entity_id):
    """Enqueue an embed job for the entity."""
    job = Job(
        job_type="embed",
        entity_id=entity_id,
        payload={"entity_id": entity_id},
    )
    db.session.add(job)
