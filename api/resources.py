"""Resources API — Entity-based with backward-compat response shape."""

from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Entity, EntityTag, Tag
from services.entity_service import create_entity, delete_entity, update_entity


@api_bp.route("/resources", methods=["GET"])
def list_resources():
    resource_type = request.args.get("resource_type")
    area_id = request.args.get("area_id")

    q = Entity.query.filter_by(type="resource")
    if resource_type:
        q = q.filter(Entity.properties.contains({"resource_type": resource_type}))
    if area_id:
        q = q.filter(Entity.properties.contains({"area_id": area_id}))

    resources = q.order_by(Entity.updated_at.desc()).all()
    return jsonify({"data": [r.to_dict() for r in resources]})


@api_bp.route("/resources", methods=["POST"])
def create_resource():
    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    properties = {}
    if data.get("resource_type"):
        properties["resource_type"] = data["resource_type"]
    if data.get("content"):
        properties["description"] = data["content"]
    if data.get("reference_url") or data.get("url"):
        properties["url"] = data.get("reference_url") or data.get("url")
    if data.get("author"):
        properties["author"] = data["author"]
    if data.get("is_read") is not None:
        properties["is_read"] = bool(data["is_read"])
    if data.get("rating") is not None:
        properties["rating"] = data["rating"]
    if data.get("area_id"):
        properties["area_id"] = data["area_id"]
    if data.get("source"):
        properties["source"] = data["source"]

    entity = create_entity(
        entity_type="resource",
        title=data["title"],
        content=data.get("content"),
        properties=properties,
        reference_url=data.get("reference_url"),
        source=data.get("source", "manual"),
        actor="user",
    )

    # Handle tags
    if data.get("tag_ids"):
        for tag_id in data["tag_ids"]:
            tag = db.session.get(Tag, tag_id)
            if tag:
                entity_tag = EntityTag(entity_id=entity.id, tag_id=tag.id)
                db.session.add(entity_tag)

    db.session.commit()
    return jsonify({"data": entity.to_dict()}), 201


@api_bp.route("/resources/<resource_id>", methods=["GET"])
def get_resource(resource_id):
    resource = Entity.query.filter_by(id=resource_id, type="resource").first()
    if not resource:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": resource.to_dict()})


@api_bp.route("/resources/<resource_id>", methods=["PATCH", "PUT"])
def update_resource(resource_id):
    resource = Entity.query.filter_by(id=resource_id, type="resource").first()
    if not resource:
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    fields = {}
    if "title" in data:
        fields["title"] = data["title"]
    if "content" in data:
        fields["content"] = data["content"]
    if "reference_url" in data:
        fields["reference_url"] = data["reference_url"]
    if "source" in data:
        fields["source"] = data["source"]

    props = dict(resource.properties or {})
    if "resource_type" in data:
        props["resource_type"] = data["resource_type"]
    if "url" in data:
        props["url"] = data["url"]
    if "author" in data:
        props["author"] = data["author"]
    if "description" in data:
        props["description"] = data["description"]
    if "is_read" in data:
        props["is_read"] = bool(data["is_read"])
    if "rating" in data:
        props["rating"] = data["rating"]
    if "area_id" in data:
        props["area_id"] = data["area_id"]
    if props != (resource.properties or {}):
        fields["properties"] = props

    if fields:
        update_entity(resource_id, fields, actor="user")
        resource = db.session.get(Entity, resource_id)

    # Handle tags
    if "tag_ids" in data:
        EntityTag.query.filter_by(entity_id=resource_id).delete()
        for tag_id in data["tag_ids"]:
            tag = db.session.get(Tag, tag_id)
            if tag:
                entity_tag = EntityTag(entity_id=resource_id, tag_id=tag.id)
                db.session.add(entity_tag)
        db.session.commit()
        resource = db.session.get(Entity, resource_id)

    return jsonify({"data": resource.to_dict()})


@api_bp.route("/resources/<resource_id>", methods=["DELETE"])
def delete_resource(resource_id):
    resource = Entity.query.filter_by(id=resource_id, type="resource").first()
    if not resource:
        return jsonify({"error": "not found"}), 404
    delete_entity(resource_id, cascade_orphans=True)
    return jsonify({"success": True}), 200
