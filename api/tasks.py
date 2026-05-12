"""Tasks API — Entity-based with backward-compat response shape."""

from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Entity
from services.entity_service import create_entity, update_entity, transition_status


@api_bp.route("/tasks", methods=["GET"])
def list_tasks():
    status = request.args.get("status")
    project_id = request.args.get("project_id")
    area_id = request.args.get("area_id")

    q = Entity.query.filter_by(type="task")
    if status:
        q = q.filter(Entity.status == status.lower())
    if project_id:
        q = q.filter(Entity.properties.contains({"project_id": project_id}))
    if area_id:
        q = q.filter(Entity.properties.contains({"area_id": area_id}))

    tasks = q.order_by(Entity.updated_at.desc()).all()
    return jsonify({"data": [t.to_dict() for t in tasks]})


@api_bp.route("/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    task = Entity.query.filter_by(id=task_id, type="task").first()
    if not task:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": task.to_dict()})


@api_bp.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    properties = {}
    if data.get("content"):
        properties["description"] = data["content"]
    if data.get("priority"):
        properties["priority"] = data["priority"].upper()
    if data.get("project_id"):
        properties["project_id"] = data["project_id"]
    if data.get("area_id"):
        properties["area_id"] = data["area_id"]
    if data.get("note_id"):
        properties["note_id"] = data["note_id"]

    follow_up_at = None
    if data.get("follow_up_at"):
        from datetime import datetime
        try:
            follow_up_at = datetime.fromisoformat(data["follow_up_at"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    entity = create_entity(
        entity_type="task",
        title=data["title"],
        content=data.get("content"),
        properties=properties,
        follow_up_at=follow_up_at,
        actor="user",
    )
    return jsonify({"data": entity.to_dict()}), 201


@api_bp.route("/tasks/<task_id>", methods=["PATCH", "PUT"])
def update_task(task_id):
    task = Entity.query.filter_by(id=task_id, type="task").first()
    if not task:
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    fields = {}
    if "title" in data:
        fields["title"] = data["title"]
    if "content" in data:
        fields["content"] = data["content"]
    if "description" in data:
        fields["content"] = data["description"]

    props = dict(task.properties or {})
    if "priority" in data:
        props["priority"] = data["priority"].upper()
    if "project_id" in data:
        props["project_id"] = data["project_id"]
    if "area_id" in data:
        props["area_id"] = data["area_id"]
    if "note_id" in data:
        props["note_id"] = data["note_id"]
    if "description" in data:
        props["description"] = data["description"]
    if props != (task.properties or {}):
        fields["properties"] = props

    if "follow_up_at" in data:
        from datetime import datetime
        try:
            fields["follow_up_at"] = datetime.fromisoformat(data["follow_up_at"].replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    if "status" in data:
        try:
            transition_status(task_id, data["status"].lower(), actor="user")
            task = Entity.query.get(task_id)
            if fields:
                update_entity(task_id, fields, actor="user")
                task = Entity.query.get(task_id)
            return jsonify({"data": task.to_dict()})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    if fields:
        update_entity(task_id, fields, actor="user")
        task = Entity.query.get(task_id)

    return jsonify({"data": task.to_dict()})


@api_bp.route("/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    task = Entity.query.filter_by(id=task_id, type="task").first()
    if not task:
        return jsonify({"error": "not found"}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({"success": True}), 200
