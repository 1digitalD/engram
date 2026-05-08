"""
Batch operations endpoint.
Agents can submit multiple note/task/project reads and writes in one request.
Each operation: { "op": "create_note|update_note|get_note|create_task|update_task" + relevant fields }

Unlike the old test_client() approach, each operation calls service/ORM functions
directly — no HTTP round-trips, no broken atomic rollbacks.
"""
from flask import request, jsonify
from api import api_bp
from extensions import db
import logging

logger = logging.getLogger(__name__)

# Maximum operations per call
MAX_OPS = 50


def _op_create_note(body: dict) -> dict:
    raw_text = body.get("raw_text") or body.get("content", "")
    if not raw_text:
        return {"error": "raw_text is required"}
    from services.ingestion import run_ingestion
    result = run_ingestion(content=raw_text, source=body.get("source", "batch"))
    if "error" in result:
        return result
    return {"note": result["note"], "tasks": result.get("tasks", []), "confident": result.get("confident")}


def _op_get_note(body: dict) -> dict:
    from models import Note
    note_id = body.get("note_id") or body.get("id")
    if not note_id:
        return {"error": "note_id is required"}
    note = db.session.get(Note, note_id)
    if not note:
        return {"error": f"note {note_id} not found"}
    return {"note": note.to_dict()}


def _op_update_note(body: dict) -> dict:
    from models import Note, BucketType, Tag
    note_id = body.get("note_id") or body.get("id")
    if not note_id:
        return {"error": "note_id is required"}
    note = db.session.get(Note, note_id)
    if not note:
        return {"error": f"note {note_id} not found"}
    text_changed = False
    if "raw_text" in body:
        new_text = body["raw_text"]
        if note.raw_text != new_text:
            note.raw_text = new_text
            text_changed = True
    if "bucket" in body:
        try:
            note.bucket = BucketType(body["bucket"].upper())
        except ValueError:
            pass
    for field in ("project_id", "area_id", "person_id", "is_archived"):
        if field in body:
            setattr(note, field, body[field])
    if "tag_names" in body:
        from api.notes import _resolve_or_create_tags
        note.tags = _resolve_or_create_tags(body["tag_names"])
    if text_changed:
        from services.extractor import extract_inline_tasks

        extract_inline_tasks(note.id, note.raw_text, note.project_id, note.area_id)
    db.session.commit()
    return {"note": note.to_dict()}


def _op_create_task(body: dict) -> dict:
    from models import Task
    from utils import parse_priority
    title = body.get("title")
    if not title:
        return {"error": "title is required"}
    task = Task(
        title=title,
        description=body.get("description"),
        priority=parse_priority(body.get("priority", "medium")),
        due_date=body.get("due_date"),
        project_id=body.get("project_id"),
    )
    db.session.add(task)
    db.session.commit()
    return {"task": task.to_dict()}


def _op_update_task(body: dict) -> dict:
    from models import Task, TaskStatus
    from utils import parse_priority
    task_id = body.get("task_id") or body.get("id")
    if not task_id:
        return {"error": "task_id is required"}
    task = db.session.get(Task, task_id)
    if not task:
        return {"error": f"task {task_id} not found"}
    for field in ("title", "description", "due_date", "project_id"):
        if field in body:
            setattr(task, field, body[field])
    if "status" in body:
        try:
            task.status = TaskStatus(body["status"].upper())
        except ValueError:
            pass
    if "priority" in body:
        task.priority = parse_priority(body["priority"])
    db.session.commit()
    return {"task": task.to_dict()}


def _op_search(body: dict) -> dict:
    from services.search import search_notes
    q = body.get("query") or body.get("q", "")
    if not q:
        return {"error": "query is required"}
    results = search_notes(
        q,
        limit=body.get("limit", 10),
        mode=body.get("mode", "hybrid"),
        bucket=body.get("bucket"),
        project_id=body.get("project_id"),
        area_id=body.get("area_id"),
    )
    return {"notes": results, "count": len(results)}


_DISPATCH = {
    "create_note": _op_create_note,
    "get_note": _op_get_note,
    "update_note": _op_update_note,
    "create_task": _op_create_task,
    "update_task": _op_update_task,
    "search": _op_search,
}


@api_bp.route("/batch", methods=["POST"])
def batch():
    """
    Execute multiple operations in one request.

    Body:
      operations  list  - array of { "op": "<operation>", ...fields }
      atomic      bool  - if true, rollback all on any error (default: false)

    Supported ops: create_note, get_note, update_note, create_task, update_task, search

    Returns:
      results  list  - per-operation { index, op, data, error }
      success  bool  - true if all operations succeeded
    """
    data = request.get_json(silent=True) or {}
    operations = data.get("operations", [])
    atomic = data.get("atomic", False)

    if not operations:
        return jsonify({"error": "operations list is required"}), 400
    if len(operations) > MAX_OPS:
        return jsonify({"error": f"max {MAX_OPS} operations per batch"}), 400

    results = []
    had_error = False

    try:
        for i, op in enumerate(operations):
            op_name = (op.get("op") or "").lower().strip()
            handler = _DISPATCH.get(op_name)
            if not handler:
                results.append({"index": i, "op": op_name, "error": f"unknown op '{op_name}'. Valid: {sorted(_DISPATCH)}"})
                had_error = True
                if atomic:
                    raise RuntimeError("atomic abort")
                continue

            try:
                result = handler(op)
                if "error" in result:
                    results.append({"index": i, "op": op_name, "error": result["error"]})
                    had_error = True
                    if atomic:
                        raise RuntimeError("atomic abort")
                else:
                    results.append({"index": i, "op": op_name, "data": result})
            except RuntimeError:
                raise
            except Exception as e:
                logger.error(f"Batch op {i} ({op_name}) failed: {e}")
                results.append({"index": i, "op": op_name, "error": str(e)})
                had_error = True
                if atomic:
                    raise RuntimeError("atomic abort")

    except RuntimeError:
        db.session.rollback()
        return jsonify({
            "results": results,
            "success": False,
            "count": len(results),
            "aborted": True,
        }), 207

    return jsonify({
        "results": results,
        "success": not had_error,
        "count": len(results),
    }), 200 if not had_error else 207
