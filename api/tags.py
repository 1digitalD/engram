from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Tag


@api_bp.route("/tags", methods=["GET"])
def list_tags():
    tags = Tag.query.order_by(Tag.name).all()
    return jsonify({"data": [t.to_dict() for t in tags]})


@api_bp.route("/tags/<tag_id>", methods=["GET"])
def get_tag(tag_id):
    tag = db.session.get(Tag, tag_id)
    if not tag:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": tag.to_dict()})


@api_bp.route("/tags", methods=["POST"])
def create_tag():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    existing = Tag.query.filter(Tag.name.ilike(data["name"])).first()
    if existing:
        return jsonify({"data": existing.to_dict()}), 200

    tag = Tag(name=data["name"].lower().strip(), color=data.get("color"))
    db.session.add(tag)
    db.session.commit()
    return jsonify({"data": tag.to_dict()}), 201


@api_bp.route("/tags/<tag_id>", methods=["PATCH", "PUT"])
def update_tag(tag_id):
    tag = db.session.get(Tag, tag_id)
    if not tag:
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    for field in ("name", "color"):
        if field in data:
            setattr(tag, field, data[field])

    db.session.commit()
    return jsonify({"data": tag.to_dict()})


@api_bp.route("/tags/<tag_id>", methods=["DELETE"])
def delete_tag(tag_id):
    tag = db.session.get(Tag, tag_id)
    if not tag:
        return jsonify({"error": "not found"}), 404
    db.session.delete(tag)
    db.session.commit()
    return jsonify({"success": True}), 200
