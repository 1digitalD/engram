from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Area


@api_bp.route("/areas", methods=["GET"])
def list_areas():
    areas = Area.query.order_by(Area.name).all()
    return jsonify({"data": [a.to_dict() for a in areas]})


@api_bp.route("/areas", methods=["POST"])
def create_area():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    area = Area(
        name=data["name"],
        description=data.get("description"),
        color=data.get("color"),
    )
    db.session.add(area)
    db.session.commit()
    return jsonify({"data": area.to_dict()}), 201


@api_bp.route("/areas/<area_id>", methods=["GET"])
def get_area(area_id):
    area = db.session.get(Area, area_id)
    if not area:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": area.to_dict(include_notes=True)})


@api_bp.route("/areas/<area_id>", methods=["PATCH"])
def update_area(area_id):
    area = db.session.get(Area, area_id)
    if not area:
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    for field in ("name", "description", "color"):
        if field in data:
            setattr(area, field, data[field])

    db.session.commit()
    return jsonify({"data": area.to_dict()})


@api_bp.route("/areas/<area_id>", methods=["DELETE"])
def delete_area(area_id):
    area = db.session.get(Area, area_id)
    if not area:
        return jsonify({"error": "not found"}), 404
    db.session.delete(area)
    db.session.commit()
    return jsonify({"success": True}), 200
