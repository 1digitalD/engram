"""Projects API — Entity-based with backward-compat response shape."""

from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Entity
from services.entity_service import create_entity, update_entity, transition_status, delete_entity


@api_bp.route("/projects", methods=["GET"])
def list_projects():
    archived = request.args.get("archived", "false").lower() == "true"
    area_id = request.args.get("area_id")

    q = Entity.query.filter_by(type="project")
    if not archived:
        q = q.filter(Entity.lifecycle != "archived")
    if area_id:
        q = q.filter(Entity.properties.contains({"area_id": area_id}))

    projects = q.order_by(Entity.updated_at.desc()).all()
    return jsonify({"data": [p.to_dict() for p in projects]})


@api_bp.route("/projects", methods=["POST"])
def create_project():
    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    properties = {}
    if data.get("content"):
        properties["description"] = data["content"]
    if data.get("priority"):
        properties["priority"] = data["priority"].upper()
    if data.get("color"):
        properties["color"] = data["color"]
    if data.get("area_id"):
        properties["area_id"] = data["area_id"]

    entity = create_entity(
        entity_type="project",
        title=data["title"],
        content=data.get("content"),
        properties=properties,
        actor="user",
    )
    return jsonify({"data": entity.to_dict()}), 201


@api_bp.route("/projects/<project_id>", methods=["GET"])
def get_project(project_id):
    project = Entity.query.filter_by(id=project_id, type="project").first()
    if not project:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": project.to_dict()})


@api_bp.route("/projects/<project_id>", methods=["PATCH"])
def update_project(project_id):
    project = Entity.query.filter_by(id=project_id, type="project").first()
    if not project:
        return jsonify({"error": "not found"}), 404

    data = request.get_json() or {}

    # Handle status transitions
    if "status" in data:
        try:
            transition_status(project_id, data["status"], actor="user")
            project = db.session.get(Entity, project_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    # Handle archival
    if "is_archived" in data:
        from services.entity_service import archive_entity
        if data["is_archived"]:
            area_id = (project.properties or {}).get("area_id")
            if area_id:
                return (
                    jsonify({
                        "error": "Archiving projects with areas requires entity service.",
                        "code": "rollup_confirmation_required",
                        "area_id": area_id,
                    }),
                    409,
                )
            try:
                archive_entity(project_id, actor="user")
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
        else:
            project.lifecycle = "active"
            db.session.commit()
        project = db.session.get(Entity, project_id)
        return jsonify({"data": project.to_dict()})

    # Regular field updates
    fields = {}
    if "title" in data:
        fields["title"] = data["title"]
    if "content" in data:
        fields["content"] = data["content"]

    props = dict(project.properties or {})
    if "description" in data:
        props["description"] = data["description"]
    if "priority" in data:
        props["priority"] = data["priority"].upper()
    if "color" in data:
        props["color"] = data["color"]
    if "area_id" in data:
        props["area_id"] = data["area_id"]
    if props != (project.properties or {}):
        fields["properties"] = props

    if fields:
        update_entity(project_id, fields, actor="user")
        project = db.session.get(Entity, project_id)

    return jsonify({"data": project.to_dict()})


@api_bp.route("/projects/<project_id>", methods=["DELETE"])
def delete_project(project_id):
    project = Entity.query.filter_by(id=project_id, type="project").first()
    if not project:
        return jsonify({"error": "not found"}), 404
    cascade = request.args.get("cascade", "false").lower() == "true"
    try:
        result = delete_entity(project_id, cascade_orphans=cascade)
        if not cascade:
            return jsonify({
                "safe_to_cascade": result["safe_to_cascade"],
                "blocked": result["blocked"],
            })
        return jsonify({"deleted": result["deleted"], "blocked": result["blocked"]})
    except ValueError:
        return jsonify({"error": "not found"}), 404
