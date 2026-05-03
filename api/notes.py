from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Note, BucketType
from services.classifier import classify_note
from services.search import search_notes


@api_bp.route("/notes", methods=["GET"])
def list_notes():
    """List notes, optionally filtered by bucket, project_id, area_id, tag_id."""
    bucket = request.args.get("bucket")
    project_id = request.args.get("project_id")
    area_id = request.args.get("area_id")
    tag_id = request.args.get("tag_id")
    archived = request.args.get("archived", "false").lower() == "true"
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    q = Note.query

    if bucket:
        try:
            b = BucketType(bucket)
            q = q.filter(Note.bucket == b)
        except ValueError:
            pass

    if project_id:
        q = q.filter(Note.project_id == project_id)
    if area_id:
        q = q.filter(Note.area_id == area_id)
    if not archived:
        q = q.filter(Note.is_archived == False)

    total = q.count()
    notes = q.order_by(Note.modified_at.desc()).offset(offset).limit(limit).all()

    return jsonify({
        "data": [n.to_dict() for n in notes],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@api_bp.route("/notes", methods=["POST"])
def create_note():
    """Create a note. Auto-classifies via AI unless classify=false."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    raw_text = data.get("raw_text")
    if not raw_text:
        return jsonify({"error": "raw_text is required"}), 400

    do_classify = data.get("classify", True)

    # Run AI classification
    ai_meta = None
    bucket = BucketType.INBOX
    project_id = data.get("project_id")
    area_id = data.get("area_id")

    if do_classify:
        result = classify_note(raw_text)
        bucket_str = result.get("bucket", "inbox")
        try:
            bucket = BucketType(bucket_str)
        except ValueError:
            bucket = BucketType.INBOX

        ai_meta = {
            "confidence": result.get("confidence", 0.0),
            "reasoning": result.get("reasoning", ""),
            "bucket": bucket_str,
            "suggested_project": result.get("suggested_project"),
            "suggested_area": result.get("suggested_area"),
            "suggested_tags": result.get("suggested_tags", []),
        }

    note = Note(
        raw_text=raw_text,
        bucket=bucket,
        project_id=project_id,
        area_id=area_id,
        ai_meta=ai_meta,
    )
    db.session.add(note)
    db.session.commit()

    return jsonify({"data": note.to_dict()}), 201


@api_bp.route("/notes/<note_id>", methods=["GET"])
def get_note(note_id):
    note = db.session.get(Note, note_id)
    if not note:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": note.to_dict()})


@api_bp.route("/notes/<note_id>", methods=["PATCH"])
def update_note(note_id):
    note = db.session.get(Note, note_id)
    if not note:
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    if "raw_text" in data:
        note.raw_text = data["raw_text"]
    if "bucket" in data:
        try:
            note.bucket = BucketType(data["bucket"])
        except ValueError:
            pass
    if "project_id" in data:
        note.project_id = data["project_id"]
    if "area_id" in data:
        note.area_id = data["area_id"]
    if "person_id" in data:
        note.person_id = data["person_id"]
    if "is_archived" in data:
        note.is_archived = data["is_archived"]

    db.session.commit()
    return jsonify({"data": note.to_dict()})


@api_bp.route("/notes/<note_id>", methods=["DELETE"])
def delete_note(note_id):
    note = db.session.get(Note, note_id)
    if not note:
        return jsonify({"error": "not found"}), 404
    db.session.delete(note)
    db.session.commit()
    return jsonify({"success": True}), 200


@api_bp.route("/notes/search", methods=["GET"])
def search():
    q = request.args.get("q", "")
    limit = request.args.get("limit", 20, type=int)
    results = search_notes(q, limit)
    return jsonify({"data": results, "query": q, "count": len(results)})
