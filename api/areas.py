"""Areas API — Entity-based with backward-compat response shape."""

from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Entity
from services.entity_service import create_entity, update_entity, delete_entity


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
        area = db.session.get(Entity, area_id)

    return jsonify({"data": area.to_dict()})


@api_bp.route("/areas/<area_id>", methods=["DELETE"])
def delete_area(area_id):
    area = Entity.query.filter_by(id=area_id, type="area").first()
    if not area:
        return jsonify({"error": "not found"}), 404
    cascade = request.args.get("cascade", "false").lower() == "true"
    try:
        result = delete_entity(area_id, cascade_orphans=cascade)
        if not cascade:
            return jsonify({
                "safe_to_cascade": result["safe_to_cascade"],
                "blocked": result["blocked"],
            })
        return jsonify({"deleted": result["deleted"], "blocked": result["blocked"]})
    except ValueError:
        return jsonify({"error": "not found"}), 404
