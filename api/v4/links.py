"""Engram v4 links API."""

from models import ChangeBatch
from services.v4_trust import record_pin, relationship_pin_field

from api import api_v4_bp
from api.v4._shared import *


@api_v4_bp.route("/entities/<entity_id>/owner", methods=["POST"])
def set_owner_person(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    if entity.type != "person":
        return _error("owner identity must reference a person")

    previous_owner_id = _owner_person_id()
    previous_owner = db.session.get(Entity, previous_owner_id) if previous_owner_id else None
    setting = _app_setting_row("owner_person_id")
    setting.value = entity.id
    flag_modified(setting, "value")
    _record_owner_identity_change(previous_owner, entity)
    db.session.commit()
    return jsonify({"data": {"owner_person_id": entity.id, "is_owner": True}})


@api_v4_bp.route("/entities/<entity_id>/owner", methods=["DELETE"])
def clear_owner_person(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    if entity.type != "person":
        return _error("owner identity must reference a person")

    previous_owner_id = _owner_person_id()
    previous_owner = db.session.get(Entity, previous_owner_id) if previous_owner_id else None
    setting = _app_setting_row("owner_person_id")
    setting.value = None
    flag_modified(setting, "value")
    _record_owner_identity_change(previous_owner, None)
    db.session.commit()
    return jsonify({"data": {"owner_person_id": None, "is_owner": False}})


@api_v4_bp.route("/entities/<entity_id>/relationships", methods=["GET"])
def get_relationships(entity_id):
    entity = db.session.get(Entity, entity_id)
    if entity is None:
        return _error("entity not found", 404)

    outgoing = EntityLink.query.filter_by(source_entity_id=entity_id).all()
    incoming = EntityLink.query.filter_by(target_entity_id=entity_id).all()
    return jsonify({
        "data": [link.to_dict() for link in outgoing + incoming],
        "outgoing": [link.to_dict() for link in outgoing],
        "incoming": [link.to_dict() for link in incoming],
    })


@api_v4_bp.route("/entities/<entity_id>/relationships", methods=["POST"])
def create_relationship(entity_id):
    source_entity = db.session.get(Entity, entity_id)
    if source_entity is None:
        return _error("source entity not found", 404)

    data = request.get_json(silent=True) or {}
    target_entity_id = data.get("target_entity_id")
    relationship_type = data.get("relationship_type")
    if relationship_type not in RELATIONSHIP_TYPES:
        return _error(f"invalid relationship_type: {relationship_type}")
    if target_entity_id == entity_id:
        return _error("self-link relationships not allowed")

    target_entity = db.session.get(Entity, target_entity_id)
    if target_entity is None:
        return _error("target entity not found", 404)
    if EntityLink.query.filter_by(
        source_entity_id=entity_id,
        target_entity_id=target_entity_id,
        relationship_type=relationship_type,
    ).first():
        return _error("duplicate relationship", 409)
    if relationship_type == "blocks" and _creates_blocks_cycle(entity_id, target_entity_id):
        return _error("relationship would create blocks cycle", 409)

    link = EntityLink(
        source_entity_id=entity_id,
        target_entity_id=target_entity_id,
        relationship_type=relationship_type,
        source=data.get("source") or "manual",
        confidence=data.get("confidence"),
        evidence=data.get("evidence"),
    )
    db.session.add(link)
    db.session.flush()
    _write_event(source_entity, "relationship_added", new_value=link.to_dict())

    if relationship_type == "parent" and source_entity.type == "task" and target_entity.type == "project":
        target_entity.updated_at = datetime.now(timezone.utc)

    db.session.commit()
    return jsonify({"data": link.to_dict()}), 201


def _touch_parent_target(source_entity, target_entity, relationship_type):
    if relationship_type == "parent" and source_entity.type == "task" and target_entity.type == "project":
        target_entity.updated_at = datetime.now(timezone.utc)


@api_v4_bp.route("/entities/<entity_id>/links", methods=["POST"])
def create_link(entity_id):
    """Manual link endpoint backing typed affordances.

    Optional `replace_existing` removes existing parent/owner links in the same
    transaction and records the whole change under one ChangeBatch.
    """

    source_entity = db.session.get(Entity, entity_id)
    if source_entity is None:
        return _error("source entity not found", 404)

    data = request.get_json(silent=True) or {}
    target_id = data.get("target_id")
    relationship_type = data.get("relationship_type")
    replace_existing = bool(data.get("replace_existing"))
    batch_summary = (data.get("batch_summary") or "").strip() or None

    if not target_id:
        return _error("target_id required")
    if relationship_type not in RELATIONSHIP_TYPES:
        return _error(f"invalid relationship_type: {relationship_type}")
    if target_id == entity_id:
        return _error("self-link relationships not allowed")
    if replace_existing and relationship_type not in {"assigned_to", "parent"}:
        return _error("replace_existing only supported for parent or assigned_to")

    target_entity = db.session.get(Entity, target_id)
    if target_entity is None:
        return _error("target entity not found", 404)
    if target_entity.lifecycle == "deleted":
        return _error("target entity deleted", 404)

    if not _is_relationship_compatible(relationship_type, source_entity.type, target_entity.type):
        return _error(
            f"{relationship_type} link from {source_entity.type} to {target_entity.type} not allowed",
            400,
        )
    if relationship_type == "blocks" and _creates_blocks_cycle(entity_id, target_id):
        return _error("relationship would create blocks cycle", 409)

    existing_links = (
        EntityLink.query.filter_by(
            source_entity_id=entity_id,
            relationship_type=relationship_type,
        )
        .order_by(EntityLink.created_at.asc())
        .all()
    )
    duplicate_link = next(
        (link for link in existing_links if link.target_entity_id == target_id),
        None,
    )
    if duplicate_link is not None and not replace_existing:
        return _error("duplicate relationship", 409)

    batch = None
    change_batch_id = None
    removed = []
    created = False

    try:
        if replace_existing:
            batch = ChangeBatch(
                source_note_id=None,
                actor="user",
                source="manual",
                summary=batch_summary or f"replace {relationship_type} for {source_entity.title}",
            )
            db.session.add(batch)
            db.session.flush()
            change_batch_id = batch.id

            for existing_link in existing_links:
                if existing_link.target_entity_id == target_id:
                    continue
                old_value = existing_link.to_dict()
                removed.append(old_value)
                db.session.delete(existing_link)
                _write_event(
                    source_entity,
                    "relationship_removed",
                    old_value=old_value,
                    change_batch_id=change_batch_id,
                )

        link = duplicate_link
        if link is None:
            link = _create_entity_link(
                source_entity,
                target_entity,
                relationship_type,
                confidence=1.0,
                evidence="manual link",
                source="manual",
            )
            if link is None:
                db.session.rollback()
                return _error("relationship could not be created", 409)
            created = True

        old_snapshot = source_entity.to_dict()
        pin_field = relationship_pin_field(relationship_type)
        pin_event_needed = pin_field and record_pin(source_entity, pin_field, "user")

        if created:
            _write_event(
                source_entity,
                "relationship_added",
                new_value=link.to_dict(),
                change_batch_id=change_batch_id,
            )
        if pin_event_needed:
            _write_event(
                source_entity,
                "updated",
                old_value={"pinned_fields": old_snapshot.get("pinned_fields", [])},
                new_value={"pinned_fields": source_entity.to_dict().get("pinned_fields", [])},
                change_batch_id=change_batch_id,
            )

        _touch_parent_target(source_entity, target_entity, relationship_type)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    payload = {"data": link.to_dict(), "removed": removed}
    if batch is not None:
        payload["change_batch"] = batch.to_dict()
    return jsonify(payload), 201 if created else 200


@api_v4_bp.route("/relationships/<relationship_id>", methods=["PATCH"])
def update_relationship(relationship_id):
    link = db.session.get(EntityLink, relationship_id)
    if link is None:
        return _error("relationship not found", 404)

    data = request.get_json(silent=True) or {}
    old_value = link.to_dict()
    relationship_type = data.get("relationship_type")
    if relationship_type and relationship_type not in RELATIONSHIP_TYPES:
        return _error(f"invalid relationship_type: {relationship_type}")

    if relationship_type and EntityLink.query.filter(
        EntityLink.id != relationship_id,
        EntityLink.source_entity_id == link.source_entity_id,
        EntityLink.target_entity_id == link.target_entity_id,
        EntityLink.relationship_type == relationship_type,
    ).first():
        return _error("duplicate relationship", 409)
    if relationship_type == "blocks" and _creates_blocks_cycle(link.source_entity_id, link.target_entity_id):
        return _error("relationship would create blocks cycle", 409)

    if relationship_type:
        link.relationship_type = relationship_type
    for field in ("source", "confidence", "evidence"):
        if field in data:
            setattr(link, field, data[field])

    db.session.flush()
    source_entity = db.session.get(Entity, link.source_entity_id)
    if source_entity is not None:
        _write_event(source_entity, "relationship_updated", old_value=old_value, new_value=link.to_dict())
    db.session.commit()
    return jsonify({"data": link.to_dict()})


@api_v4_bp.route("/relationships/<relationship_id>", methods=["DELETE"])
def delete_relationship(relationship_id):
    link = db.session.get(EntityLink, relationship_id)
    if link is None:
        return _error("relationship not found", 404)

    old_value = link.to_dict()
    source_entity = db.session.get(Entity, link.source_entity_id)
    db.session.delete(link)
    if source_entity is not None:
        _write_event(source_entity, "relationship_removed", old_value=old_value)
    db.session.commit()
    return jsonify({"data": {"id": relationship_id, "deleted": True}})
