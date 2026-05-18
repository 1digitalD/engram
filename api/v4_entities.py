"""Engram v4 canonical entity API."""

from datetime import datetime

from flask import jsonify, request
from sqlalchemy.orm import selectinload

from api import api_v4_bp
from extensions import db
from models import Entity, EntityEvent, EntityLink, EntityTag, Tag


ENTITY_TYPES = {"note", "task", "project", "area", "resource", "person"}
DEFAULT_STATUS = {
    "note": "active",
    "task": "open",
    "project": "active",
    "area": "active",
    "resource": "active",
    "person": "active",
}
VALID_STATUS = {
    "note": {"active", "processed", "archived"},
    "task": {"open", "in_progress", "waiting", "blocked", "done", "cancelled"},
    "project": {"active", "on_hold", "completed", "cancelled"},
    "area": {"active", "archived"},
    "resource": {"active", "archived"},
    "person": {"active", "archived"},
}
VALID_LIFECYCLE = {"active", "archived", "deleted"}
WRITABLE_FIELDS = {
    "title",
    "content",
    "status",
    "lifecycle",
    "follow_up_at",
    "source",
    "reference_url",
    "properties",
}
RELATIONSHIP_PROPERTY_KEYS = {
    "project_id",
    "project_ids",
    "area_id",
    "area_ids",
    "person_id",
    "person_ids",
    "note_id",
    "note_ids",
    "source_note_id",
    "source_note_ids",
    "parent_id",
    "parent_ids",
}
RELATIONSHIP_TYPES = {
    "parent",
    "related",
    "derived_from",
    "mentions",
    "assigned_to",
    "references",
    "blocks",
}


@api_v4_bp.route("/health", methods=["GET"])
def health():
    db.session.execute(db.text("SELECT 1"))
    return jsonify({"status": "ok", "api": "v4"})


@api_v4_bp.route("/entities", methods=["GET"])
def list_entities():
    query = _entity_query()
    entity_type = request.args.get("type")
    status = request.args.get("status")
    lifecycle = request.args.get("lifecycle")
    limit = max(1, min(request.args.get("limit", 50, type=int), 200))

    if entity_type:
        if entity_type not in ENTITY_TYPES:
            return _error(f"invalid entity type: {entity_type}")
        query = query.filter(Entity.type == entity_type)
    if status:
        query = query.filter(Entity.status == status)
    if lifecycle:
        if lifecycle not in VALID_LIFECYCLE:
            return _error(f"invalid lifecycle: {lifecycle}")
        query = query.filter(Entity.lifecycle == lifecycle)

    rows = query.order_by(Entity.updated_at.desc(), Entity.created_at.desc()).limit(limit).all()
    return jsonify({"data": [row.to_dict() for row in rows]})


@api_v4_bp.route("/entities", methods=["POST"])
def create_entity():
    data = request.get_json(silent=True) or {}
    entity_type = data.get("type")
    if entity_type not in ENTITY_TYPES:
        return _error("type must be one of: " + ", ".join(sorted(ENTITY_TYPES)))

    status = data.get("status") or DEFAULT_STATUS[entity_type]
    validation_error = _validate_status(entity_type, status)
    if validation_error:
        return validation_error

    properties = data.get("properties") or {}
    properties_error = _validate_properties(properties)
    if properties_error:
        return properties_error

    entity = Entity(
        type=entity_type,
        title=data.get("title"),
        content=data.get("content"),
        status=status,
        lifecycle=data.get("lifecycle") or "active",
        follow_up_at=_parse_datetime(data.get("follow_up_at")),
        source=data.get("source") or "manual",
        reference_url=data.get("reference_url"),
        properties=properties,
        ai_meta=data.get("ai_meta") or {},
        ai_status=data.get("ai_status") or "pending",
    )
    lifecycle_error = _validate_lifecycle(entity.lifecycle)
    if lifecycle_error:
        return lifecycle_error

    db.session.add(entity)
    db.session.flush()
    _replace_tags(entity, data.get("tags", []))
    _write_event(entity, "created", new_value=entity.to_dict())
    db.session.commit()

    return jsonify({"data": _load_entity(entity.id).to_dict()}), 201


@api_v4_bp.route("/entities/<entity_id>", methods=["GET"])
def get_entity(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    return jsonify({"data": entity.to_dict()})


@api_v4_bp.route("/entities/<entity_id>", methods=["PATCH"])
def update_entity(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)

    data = request.get_json(silent=True) or {}
    unknown = set(data) - WRITABLE_FIELDS - {"tags"}
    if unknown:
        return _error("unsupported fields: " + ", ".join(sorted(unknown)))

    old_snapshot = entity.to_dict()
    status_changed = False
    archived = False

    if "status" in data:
        validation_error = _validate_status(entity.type, data["status"])
        if validation_error:
            return validation_error
        status_changed = data["status"] != entity.status
        entity.status = data["status"]

    if "lifecycle" in data:
        lifecycle_error = _validate_lifecycle(data["lifecycle"])
        if lifecycle_error:
            return lifecycle_error
        archived = data["lifecycle"] == "archived" and entity.lifecycle != "archived"
        entity.lifecycle = data["lifecycle"]

    if "properties" in data:
        properties = data.get("properties") or {}
        properties_error = _validate_properties(properties)
        if properties_error:
            return properties_error
        entity.properties = properties

    for field in ("title", "content", "source", "reference_url"):
        if field in data:
            setattr(entity, field, data[field])
    if "follow_up_at" in data:
        entity.follow_up_at = _parse_datetime(data["follow_up_at"])
    if "tags" in data:
        _replace_tags(entity, data.get("tags") or [])

    db.session.flush()
    new_snapshot = entity.to_dict()
    _write_event(entity, "updated", old_value=old_snapshot, new_value=new_snapshot)
    if status_changed:
        _write_event(
            entity,
            "status_changed",
            old_value={"status": old_snapshot["status"]},
            new_value={"status": entity.status},
        )
    if archived:
        _write_event(
            entity,
            "archived",
            old_value={"lifecycle": old_snapshot["lifecycle"]},
            new_value={"lifecycle": entity.lifecycle},
        )
    db.session.commit()

    return jsonify({"data": _load_entity(entity.id).to_dict()})


@api_v4_bp.route("/entities/<entity_id>", methods=["DELETE"])
def delete_entity(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)

    old_snapshot = entity.to_dict()
    entity.lifecycle = "deleted"
    db.session.flush()
    _write_event(
        entity,
        "deleted",
        old_value={"lifecycle": old_snapshot["lifecycle"]},
        new_value={"lifecycle": "deleted"},
    )
    db.session.commit()

    return jsonify({"data": _load_entity(entity.id).to_dict()})


@api_v4_bp.route("/entities/<entity_id>/events", methods=["GET"])
def get_entity_events(entity_id):
    if db.session.get(Entity, entity_id) is None:
        return _error("entity not found", 404)
    events = (
        EntityEvent.query.filter_by(entity_id=entity_id)
        .order_by(EntityEvent.created_at.desc())
        .limit(100)
        .all()
    )
    return jsonify({"data": [event.to_dict() for event in events]})


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
        link.relationship_type = relationship_type
    for field in ("source", "confidence", "evidence"):
        if field in data:
            setattr(link, field, data[field])

    db.session.flush()
    source_entity = db.session.get(Entity, link.source_entity_id)
    if source_entity is not None:
        _write_event(source_entity, "relationship_added", old_value=old_value, new_value=link.to_dict())
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


def _entity_query():
    return Entity.query.options(
        selectinload(Entity.entity_tags).selectinload(EntityTag.tag),
        selectinload(Entity.incoming_links),
        selectinload(Entity.outgoing_links),
    )


def _load_entity(entity_id):
    return _entity_query().filter(Entity.id == entity_id).first()


def _replace_tags(entity, tag_names):
    EntityTag.query.filter_by(entity_id=entity.id).delete(synchronize_session=False)
    for raw_name in tag_names:
        name = str(raw_name).strip()
        if not name:
            continue
        tag = Tag.query.filter_by(name=name).first()
        if tag is None:
            tag = Tag(name=name)
            db.session.add(tag)
            db.session.flush()
        db.session.add(EntityTag(entity_id=entity.id, tag_id=tag.id))


def _write_event(entity, event_type, old_value=None, new_value=None):
    db.session.add(
        EntityEvent(
            entity_id=entity.id,
            event_type=event_type,
            actor="user",
            old_value=old_value,
            new_value=new_value,
        )
    )


def _validate_status(entity_type, status):
    if status not in VALID_STATUS[entity_type]:
        return _error(f"invalid status for {entity_type}: {status}")
    return None


def _validate_lifecycle(lifecycle):
    if lifecycle not in VALID_LIFECYCLE:
        return _error(f"invalid lifecycle: {lifecycle}")
    return None


def _validate_properties(properties):
    if not isinstance(properties, dict):
        return _error("properties must be an object")
    bad_key = _find_relationship_property_key(properties)
    if bad_key:
        return _error(f"properties must not contain relationship IDs: {bad_key}")
    return None


def _find_relationship_property_key(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in RELATIONSHIP_PROPERTY_KEYS or key.endswith("_id") or key.endswith("_ids"):
                return key
            found = _find_relationship_property_key(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_relationship_property_key(child)
            if found:
                return found
    return None


def _parse_datetime(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"invalid datetime: {value}") from None


def _error(message, status=400):
    return jsonify({"error": message}), status
