from datetime import datetime

from flask import request, jsonify

from api import api_bp
from api.notes import _resolve_or_create_tags
from extensions import db
from models import Resource, ResourceType, Tag


def _parse_published_at(val):
    if val is None or val == "":
        return None
    if isinstance(val, str):
        s = val.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return val


def _normalize_rating_optional(val):
    if val is None or val == "":
        return None
    try:
        r = int(val)
        if 1 <= r <= 5:
            return r
    except (TypeError, ValueError):
        pass
    return None


def _merge_tags_create(resource: Resource, data: dict) -> None:
    if "tag_ids" not in data and not data.get("tag_names"):
        return
    tags = []
    if "tag_ids" in data:
        for tag_id in data["tag_ids"]:
            tag = db.session.get(Tag, tag_id)
            if tag and tag not in tags:
                tags.append(tag)
    if data.get("tag_names"):
        for t in _resolve_or_create_tags(data["tag_names"]):
            if t not in tags:
                tags.append(t)
    resource.tags = tags


def _apply_tags_patch(resource: Resource, data: dict) -> None:
    if "tag_ids" in data:
        tags = []
        for tag_id in data["tag_ids"]:
            tag = db.session.get(Tag, tag_id)
            if tag:
                tags.append(tag)
        resource.tags = tags
    elif "tag_names" in data:
        resource.tags = _resolve_or_create_tags(data["tag_names"])


@api_bp.route("/resources", methods=["GET"])
def list_resources():
    type_raw = request.args.get("type")
    area_id = request.args.get("area_id")

    q = Resource.query
    if type_raw:
        try:
            q = q.filter(Resource.resource_type == ResourceType(type_raw.upper()))
        except ValueError:
            q = q.filter(False)
    if area_id:
        q = q.filter(Resource.area_id == area_id)

    resources = q.order_by(Resource.modified_at.desc()).all()
    return jsonify({"data": [r.to_dict() for r in resources]})


@api_bp.route("/resources/<resource_id>", methods=["GET"])
def get_resource(resource_id):
    resource = db.session.get(Resource, resource_id)
    if not resource:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": resource.to_dict()})


@api_bp.route("/resources", methods=["POST"])
def create_resource():
    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    rt_raw = data.get("resource_type", "OTHER")
    try:
        rtype = ResourceType(rt_raw.upper())
    except ValueError:
        return jsonify({"error": "invalid resource_type"}), 400

    rating = None
    if "rating" in data:
        if data["rating"] is None or data["rating"] == "":
            rating = None
        else:
            rating = _normalize_rating_optional(data["rating"])
            if rating is None:
                return jsonify({"error": "rating must be an integer between 1 and 5"}), 400

    resource = Resource(
        title=data["title"],
        resource_type=rtype,
        url=data.get("url"),
        author=data.get("author"),
        published_at=_parse_published_at(data.get("published_at")),
        description=data.get("description"),
        my_notes=data.get("my_notes"),
        is_read=bool(data.get("is_read", False)),
        rating=rating,
        area_id=data.get("area_id"),
    )
    db.session.add(resource)
    db.session.flush()
    _merge_tags_create(resource, data)
    db.session.commit()
    return jsonify({"data": resource.to_dict()}), 201


@api_bp.route("/resources/<resource_id>", methods=["PATCH", "PUT"])
def update_resource(resource_id):
    resource = db.session.get(Resource, resource_id)
    if not resource:
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    for field in ("title", "url", "author", "description", "my_notes", "area_id"):
        if field in data:
            setattr(resource, field, data[field])

    if "published_at" in data:
        resource.published_at = _parse_published_at(data.get("published_at"))

    if "is_read" in data:
        resource.is_read = bool(data["is_read"])

    if "resource_type" in data:
        try:
            resource.resource_type = ResourceType(data["resource_type"].upper())
        except ValueError:
            return jsonify({"error": "invalid resource_type"}), 400

    if "rating" in data:
        if data["rating"] is None or data["rating"] == "":
            resource.rating = None
        else:
            r = _normalize_rating_optional(data["rating"])
            if r is None:
                return jsonify({"error": "rating must be an integer between 1 and 5"}), 400
            resource.rating = r

    _apply_tags_patch(resource, data)

    db.session.commit()
    return jsonify({"data": resource.to_dict()})


@api_bp.route("/resources/<resource_id>", methods=["DELETE"])
def delete_resource(resource_id):
    resource = db.session.get(Resource, resource_id)
    if not resource:
        return jsonify({"error": "not found"}), 404
    db.session.delete(resource)
    db.session.commit()
    return jsonify({"success": True}), 200
