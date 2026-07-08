"""Engram v4 links API."""

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
    relationship_type = data.get("relationship_type") or "related"
    if relationship_type not in RELATIONSHIP_TYPES:
        return _error(f"invalid relationship_type: {relationship_type}")
    if not target_entity_id:
        return _error("target_entity_id is required")
    if target_entity_id == entity_id:
        return _error("self-link relationships are not allowed")
    if db.session.get(Entity, target_entity_id) is None:
        return _error("target entity not found", 404)
    if EntityLink.query.filter_by(
        source_entity_id=entity_id,
        target_entity_id=target_entity_id,
        relationship_type=relationship_type,
    ).first():
        return _error("duplicate relationship", 409)
    if relationship_type == "blocks" and _creates_blocks_cycle(entity_id, target_entity_id):
        return _error("relationship would create a blocks cycle", 409)

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

    # When a task is parent-linked to a project, advance the project's updated_at
    if (relationship_type == "parent"
        and source_entity.type == "task"):
        target_entity = db.session.get(Entity, target_entity_id)
        if target_entity is not None and target_entity.type == "project":
            target_entity.updated_at = datetime.now(timezone.utc)

    db.session.commit()

    return jsonify({"data": link.to_dict()}), 201


@api_v4_bp.route("/entities/<entity_id>/links", methods=["POST"])
def create_link(entity_id):
    """Additive manual link endpoint for Lab entity authoring.

    Body: { target_id, relationship_type }. Reuses _create_entity_link so the
    new path behaves identically to existing callers for cycle/duplicate
    handling, while adding explicit request validation and recording the
    manual user actor/source.
    """
    source_entity = db.session.get(Entity, entity_id)
    if source_entity is None:
        return _error("source entity not found", 404)

    data = request.get_json(silent=True) or {}
    target_id = data.get("target_id")
    relationship_type = data.get("relationship_type")

    if not target_id:
        return _error("target_id is required")
    if relationship_type not in RELATIONSHIP_TYPES:
        return _error(f"invalid relationship_type: {relationship_type}")
    if target_id == entity_id:
        return _error("self-link relationships are not allowed")

    target_entity = db.session.get(Entity, target_id)
    if target_entity is None:
        return _error("target entity not found", 404)
    if target_entity.lifecycle == "deleted":
        return _error("target entity is deleted", 404)

    if not _is_relationship_compatible(relationship_type, source_entity.type, target_entity.type):
        return _error(
            f"{relationship_type} link from {source_entity.type} to {target_entity.type} is not allowed",
            400,
        )

    if EntityLink.query.filter_by(
        source_entity_id=entity_id,
        target_entity_id=target_id,
        relationship_type=relationship_type,
    ).first():
        return _error("duplicate relationship", 409)

    if relationship_type == "blocks" and _creates_blocks_cycle(entity_id, target_id):
        return _error("relationship would create a blocks cycle", 409)

    link = _create_entity_link(
        source_entity,
        target_entity,
        relationship_type,
        confidence=1.0,
        evidence="manual link",
        source="manual",
    )
    if link is None:
        return _error("relationship could not be created", 409)

    _write_event(
        source_entity,
        "relationship_added",
        new_value=link.to_dict(),
        actor="user",
        reason="manual link",
    )
    db.session.commit()

    return jsonify({"data": link.to_dict()}), 201


@api_v4_bp.route("/relationships/<relationship_id>", methods=["PATCH"])
def update_relationship(relationship_id):
    link = db.session.get(EntityLink, relationship_id)
    if link is None:
        return _error("relationship not found", 404)

    data = request.get_json(silent=True) or {}
    old_value = link.to_dict()
    if "relationship_type" in data:
        relationship_type = data["relationship_type"]
        if relationship_type not in RELATIONSHIP_TYPES:
            return _error(f"invalid relationship_type: {relationship_type}")
        duplicate = EntityLink.query.filter(
            EntityLink.id != relationship_id,
            EntityLink.source_entity_id == link.source_entity_id,
            EntityLink.target_entity_id == link.target_entity_id,
            EntityLink.relationship_type == relationship_type,
        ).first()
        if duplicate:
            return _error("duplicate relationship", 409)
        if relationship_type == "blocks" and _creates_blocks_cycle(link.source_entity_id, link.target_entity_id):
            return _error("relationship would create a blocks cycle", 409)
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


