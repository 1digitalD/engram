"""People API — Entity-based with backward-compat response shape."""

from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Entity, EntityTag, Tag
from services.entity_service import create_entity, delete_entity, update_entity


@api_bp.route("/people", methods=["GET"])
def list_people():
    q = Entity.query.filter_by(type="person", lifecycle="active")
    people = q.order_by(Entity.title).all()
    return jsonify({"data": [p.to_dict() for p in people]})


@api_bp.route("/people", methods=["POST"])
def create_person():
    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    properties = {}
    if data.get("email"):
        properties["email"] = data["email"]
    if data.get("role"):
        properties["role"] = data["role"]
    if data.get("external_ids"):
        properties["external_ids"] = data["external_ids"]
    if data.get("notes"):
        properties["notes_text"] = data["notes"]
    if data.get("last_contacted_at"):
        properties["last_contacted_at"] = data["last_contacted_at"]
    if data.get("content"):
        properties["notes_text"] = data["content"]

    entity = create_entity(
        entity_type="person",
        title=data["title"],
        content=data.get("content"),
        properties=properties,
        actor="user",
    )
    return jsonify({"data": entity.to_dict()}), 201


@api_bp.route("/people/<person_id>", methods=["GET"])
def get_person(person_id):
    person = Entity.query.filter_by(id=person_id, type="person").first()
    if not person:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": person.to_dict()})


@api_bp.route("/people/<person_id>", methods=["PATCH"])
def update_person(person_id):
    person = Entity.query.filter_by(id=person_id, type="person").first()
    if not person:
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    fields = {}
    if "title" in data:
        fields["title"] = data["title"]
    if "content" in data:
        fields["content"] = data["content"]

    props = dict(person.properties or {})
    if "email" in data:
        props["email"] = data["email"]
    if "role" in data:
        props["role"] = data["role"]
    if "external_ids" in data:
        props["external_ids"] = {**(props.get("external_ids") or {}), **data["external_ids"]}
    if "notes" in data:
        props["notes_text"] = data["notes"]
    if "last_contacted_at" in data:
        props["last_contacted_at"] = data["last_contacted_at"]
    if props != (person.properties or {}):
        fields["properties"] = props

    if fields:
        update_entity(person_id, fields, actor="user")
        person = db.session.get(Entity, person_id)

    return jsonify({"data": person.to_dict()})


@api_bp.route("/people/<person_id>", methods=["DELETE"])
def delete_person(person_id):
    person = Entity.query.filter_by(id=person_id, type="person").first()
    if not person:
        return jsonify({"error": "not found"}), 404
    delete_entity(person_id, cascade_orphans=True)
    return jsonify({"success": True}), 200
