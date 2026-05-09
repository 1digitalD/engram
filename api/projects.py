from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Project, Priority
from utils import parse_priority as _priority


@api_bp.route("/projects", methods=["GET"])
def list_projects():
    archived = request.args.get("archived", "false").lower() == "true"
    area_id = request.args.get("area_id")
    q = Project.query
    if not archived:
        q = q.filter(Project.is_archived == False)
    if area_id:
        q = q.filter(Project.area_id == area_id)
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
        area_id=data.get("area_id"),
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

    data = request.get_json() or {}
    rollup_confirmed = bool(
        data.pop("rollup_confirmed", False) or data.pop("confirm_rollup", False)
    )
    archive_in_payload = "is_archived" in data
    archive_value = data.pop("is_archived", None) if archive_in_payload else None

    for field in ("name", "description", "color", "deadline", "area_id"):
        if field in data:
            setattr(project, field, data[field])
    if "priority" in data:
        project.priority = _priority(data["priority"])

    if archive_in_payload:
        if archive_value is True:
            if project.area_id and not rollup_confirmed:
                db.session.commit()
                return (
                    jsonify(
                        {
                            "error": (
                                "This project belongs to an area. Confirm the rollup "
                                "retrospective to complete it, or archive without a parent area."
                            ),
                            "code": "rollup_confirmation_required",
                            "area_id": project.area_id,
                        }
                    ),
                    409,
                )
            if project.area_id and rollup_confirmed:
                from services.rollup import rollup_project_to_area

                db.session.commit()
                try:
                    summary_note = rollup_project_to_area(project_id)
                except ValueError as exc:
                    db.session.rollback()
                    return jsonify({"error": str(exc)}), 400
                project = db.session.get(Project, project_id)
                return jsonify(
                    {"data": project.to_dict(), "rollup": {"note_id": summary_note.id}}
                )
            project.is_archived = True
        else:
            project.is_archived = False

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
