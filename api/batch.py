"""
Batch operations endpoint — v2 Entity model.
Agents can submit multiple note/task/project reads and writes in one request.
Each operation: { "op": "create_note|update_note|get_note|create_task|update_task" + relevant fields }

All operations use Entity, create_entity, transition_status, EntityTag.
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
    return {"note": result.get("entity") or result.get("note"), "tasks": result.get("tasks", []), "confident": result.get("confident")}


def _op_get_note(body: dict) -> dict:
    from models import Entity
    note_id = body.get("note_id") or body.get("id")
    if not note_id:
        return {"error": "note_id is required"}
    note = Entity.query.filter_by(id=note_id, type="note").first()
    if not note:
        return {"error": f"note {note_id} not found"}
    return {"note": note.to_dict()}


def _op_update_note(body: dict) -> dict:
    from models import Entity, EntityTag, Tag
    note_id = body.get("note_id") or body.get("id")
    if not note_id:
        return {"error": "note_id is required"}
    note = Entity.query.filter_by(id=note_id, type="note").first()
    if not note:
        return {"error": f"note {note_id} not found"}
    text_changed = False
    if "raw_text" in body or "content" in body:
        new_text = body.get("raw_text") or body.get("content")
        if note.content != new_text:
            note.content = new_text
            text_changed = True
    if "bucket" in body:
        props = dict(note.properties or {})
        props["bucket"] = body["bucket"].upper()
        note.properties = props
    for field in ("is_archived",):
        if field in body:
            if field == "is_archived" and body[field]:
                note.lifecycle = "archived"
            else:
                setattr(note, field, body[field])
    if "tag_names" in body:
        from api.notes import _resolve_or_create_tags
        EntityTag.query.filter_by(entity_id=note.id).delete()
        tags = _resolve_or_create_tags(body["tag_names"])
        db.session.flush()
        for tag in tags:
            db.session.add(EntityTag(entity_id=note.id, tag_id=tag.id))
    if text_changed:
        from services.extractor import extract_inline_tasks
        extract_inline_tasks(note.id, note.content, note.properties.get("project_id"), note.properties.get("area_id"))
    db.session.commit()
    return {"note": note.to_dict()}


def _op_create_task(body: dict) -> dict:
    from services.entity_service import create_entity
    title = body.get("title")
    if not title:
        return {"error": "title is required"}
    props = {}
    if body.get("priority"):
        from utils import parse_priority
        props["priority"] = parse_priority(body["priority"]).value
    if body.get("due_date"):
        props["due_date"] = body["due_date"]
    task = create_entity(
        entity_type="task",
        title=title,
        content=body.get("description"),
        properties=props if props else None,
        source=body.get("source", "batch"),
        actor="user",
    )
    return {"task": task.to_dict()}


def _op_update_task(body: dict) -> dict:
    from models import Entity
    from services.entity_service import transition_status, update_entity
    task_id = body.get("task_id") or body.get("id")
    if not task_id:
        return {"error": "task_id is required"}
    task = Entity.query.filter_by(id=task_id, type="task").first()
    if not task:
        return {"error": f"task {task_id} not found"}
    if "status" in body:
        try:
            transition_status(task_id, body["status"], actor="user")
            task = Entity.query.filter_by(id=task_id, type="task").first()
        except ValueError as e:
            return {"error": str(e)}
    fields = {}
    for field in ("title", "content"):
        if field in body:
            fields[field] = body[field]
    if "description" in body:
        fields["content"] = body["description"]
    if "priority" in body:
        from utils import parse_priority
        props = dict(task.properties or {})
        props["priority"] = parse_priority(body["priority"]).value
        fields["properties"] = props
    if fields:
        try:
            update_entity(task_id, fields, actor="user")
            task = Entity.query.filter_by(id=task_id, type="task").first()
        except ValueError:
            pass
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
