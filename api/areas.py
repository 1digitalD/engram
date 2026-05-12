"""Areas API — Entity-based with backward-compat response shape."""

from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Entity
from services.entity_service import create_entity, update_entity


@api_bp.route("/areas", methods=["GET"])
def list_areas():
    q = Entity.query.filter_by(type="area", lifecycle="active")
    areas = q.order_by(Entity.title).all()
    return jsonify({"data": [a.to_dict() for a in areas]})


@api_bp.route("/areas", methods=["POST"])
def create_area():
    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    properties = {}
    if data.get("content"):
        properties["description"] = data["content"]
    if data.get("color"):
        properties["color"] = data["color"]

    entity = create_entity(
        entity_type="area",
        title=data["title"],
        content=data.get("content"),
        properties=properties,
        actor="user",
    )
    return jsonify({"data": entity.to_dict()}), 201


@api_bp.route("/areas/<area_id>", methods=["GET"])
def get_area(area_id):
    area = Entity.query.filter_by(id=area_id, type="area").first()
    if not area:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": area.to_dict()})


@api_bp.route("/areas/<area_id>", methods=["PATCH"])
def update_area(area_id):
    area = Entity.query.filter_by(id=area_id, type="area").first()
    if not area:
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    fields = {}
    if "title" in data:
        fields["title"] = data["title"]
    if "content" in data:
        fields["content"] = data["content"]

    props = dict(area.properties or {})
    if "description" in data:
        props["description"] = data["description"]
    if "color" in data:
        props["color"] = data["color"]
    if props != (area.properties or {}):
        fields["properties"] = props

    if fields:
        update_entity(area_id, fields, actor="user")
        area = Entity.query.get(area_id)

    return jsonify({"data": area.to_dict()})


@api_bp.route("/areas/<area_id>", methods=["DELETE"])
def delete_area(area_id):
    area = Entity.query.filter_by(id=area_id, type="area").first()
    if not area:
        return jsonify({"error": "not found"}), 404
    db.session.delete(area)
    db.session.commit()
    return jsonify({"success": True}), 200
