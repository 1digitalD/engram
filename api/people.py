from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Person


@api_bp.route("/people", methods=["GET"])
def list_people():
    people = Person.query.order_by(Person.name).all()
    return jsonify({"data": [p.to_dict() for p in people]})


@api_bp.route("/people", methods=["POST"])
def create_person():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    person = Person(
        name=data["name"],
        email=data.get("email"),
        discord_id=data.get("discord_id"),
        notes_text=data.get("notes"),
        last_contacted_at=data.get("last_contacted_at"),
    )
    db.session.add(person)
    db.session.commit()
    return jsonify({"data": person.to_dict()}), 201


@api_bp.route("/people/<person_id>", methods=["GET"])
def get_person(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": person.to_dict()})


@api_bp.route("/people/<person_id>", methods=["PATCH"])
def update_person(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    for field in ("name", "email", "discord_id", "last_contacted_at"):
        if field in data:
            setattr(person, field, data[field])
    if "notes" in data:
        person.notes_text = data["notes"]

    db.session.commit()
    return jsonify({"data": person.to_dict()})


@api_bp.route("/people/<person_id>", methods=["DELETE"])
def delete_person(person_id):
    person = db.session.get(Person, person_id)
    if not person:
        return jsonify({"error": "not found"}), 404
    db.session.delete(person)
    db.session.commit()
    return jsonify({"success": True}), 200
