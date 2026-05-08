from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Task, TaskStatus, Priority
from utils import parse_priority as _priority


@api_bp.route("/tasks", methods=["GET"])
def list_tasks():
    status = request.args.get("status")
    project_id = request.args.get("project_id")
    area_id = request.args.get("area_id")
    note_id = request.args.get("note_id")

    q = Task.query
    if status:
        try:
            s = TaskStatus(status.upper())
            q = q.filter(Task.status == s)
        except ValueError:
            pass
    if project_id:
        q = q.filter(Task.project_id == project_id)
    if area_id:
        q = q.filter(Task.area_id == area_id)
    if note_id:
        q = q.filter(Task.note_id == note_id)

    tasks = q.order_by(Task.modified_at.desc()).all()
    return jsonify({"data": [t.to_dict() for t in tasks]})


@api_bp.route("/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": task.to_dict()})


@api_bp.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    task = Task(
        title=data["title"],
        description=data.get("description"),
        priority=_priority(data.get("priority", "medium")),
        due_date=data.get("due_date"),
        project_id=data.get("project_id"),
        area_id=data.get("area_id"),
        note_id=data.get("note_id"),
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"data": task.to_dict()}), 201


@api_bp.route("/tasks/<task_id>", methods=["PATCH", "PUT"])
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    for field in ("title", "description", "due_date", "project_id", "area_id", "note_id"):
        if field in data:
            setattr(task, field, data[field])
    if "status" in data:
        try:
            task.status = TaskStatus(data["status"].upper())
        except ValueError:
            pass
    if "priority" in data:
        task.priority = _priority(data["priority"])

    db.session.commit()
    return jsonify({"data": task.to_dict()})


@api_bp.route("/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "not found"}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({"success": True}), 200
