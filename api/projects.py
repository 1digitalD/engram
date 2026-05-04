from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Project, Note, Priority


def _priority(val):
    if val is None:
        return None
    if isinstance(val, Priority):
        return val
    try:
        return Priority(val.upper())
    except (ValueError, AttributeError):
        return Priority.MEDIUM


@api_bp.route("/projects", methods=["GET"])
def list_projects():
    archived = request.args.get("archived", "false").lower() == "true"
    q = Project.query
    if not archived:
        q = q.filter(Project.is_archived == False)
    projects = q.order_by(Project.modified_at.desc()).all()
    return jsonify({"data": [p.to_dict() for p in projects]})


@api_bp.route("/projects", methods=["POST"])
def create_project():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "name is required"}), 400

    project = Project(
        name=data["name"],
        description=data.get("description"),
        priority=_priority(data.get("priority", "medium")),
        color=data.get("color"),
        deadline=data.get("deadline"),
    )
    db.session.add(project)
    db.session.commit()
    return jsonify({"data": project.to_dict()}), 201


@api_bp.route("/projects/<project_id>", methods=["GET"])
def get_project(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": project.to_dict(include_notes=True)})


@api_bp.route("/projects/<project_id>", methods=["PATCH"])
def update_project(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    for field in ("name", "description", "color", "deadline", "is_archived"):
        if field in data:
            setattr(project, field, data[field])
    if "priority" in data:
        project.priority = _priority(data["priority"])

    db.session.commit()
    return jsonify({"data": project.to_dict()})


@api_bp.route("/projects/<project_id>", methods=["DELETE"])
def delete_project(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "not found"}), 404
    db.session.delete(project)
    db.session.commit()
    return jsonify({"success": True}), 200
