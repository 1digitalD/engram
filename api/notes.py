from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Note, BucketType, Tag
from services.classifier import classify_note
from services.search import search_notes


def _resolve_or_create_tags(tag_names: list) -> list:
    """Find existing tags by name (case-insensitive) or create them. Returns Tag objects."""
    tags = []
    for name in tag_names:
        name = name.strip().lower()
        if not name:
            continue
        tag = Tag.query.filter(Tag.name.ilike(name)).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
        tags.append(tag)
    return tags


@api_bp.route("/notes", methods=["GET"])
def list_notes():
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
            b = BucketType(bucket.upper())
            q = q.filter(Note.bucket == b)
        except ValueError:
            pass

    if project_id:
        q = q.filter(Note.project_id == project_id)
    if area_id:
        q = q.filter(Note.area_id == area_id)
    if tag_id:
        q = q.filter(Note.tags.any(Tag.id == tag_id))
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
    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    raw_text = data.get("raw_text")
    if not raw_text:
        return jsonify({"error": "raw_text is required"}), 400

    do_classify = data.get("classify", True)

    ai_meta = None
    resolved_project_id = data.get("project_id")
    resolved_area_id = data.get("area_id")
    resolved_person_id = data.get("person_id")
    tag_objects = []

    # Respect explicit bucket if provided (only override when classifying)
    explicit_bucket = data.get("bucket")
    if explicit_bucket:
        try:
            bucket = BucketType(explicit_bucket.upper())
        except ValueError:
            bucket = BucketType.INBOX
    else:
        bucket = BucketType.INBOX

    if do_classify:
        from models import Project, Area
        existing_projects = [p.name for p in Project.query.filter_by(is_archived=False).all()]
        existing_areas = [a.name for a in Area.query.all()]

        result = classify_note(raw_text, projects=existing_projects, areas=existing_areas)
        bucket_str = result.get("bucket", "INBOX")
        try:
            bucket = BucketType(bucket_str.upper())
        except ValueError:
            bucket = BucketType.INBOX

        suggested_project_name = result.get("suggested_project")
        suggested_area_name = result.get("suggested_area")
        suggested_tags = result.get("suggested_tags", [])

        if suggested_project_name and not resolved_project_id:
            matched = Project.query.filter(
                Project.name.ilike(f"%{suggested_project_name}%")
            ).first()
            if matched:
                resolved_project_id = matched.id

        if suggested_area_name and not resolved_area_id:
            matched = Area.query.filter(
                Area.name.ilike(f"%{suggested_area_name}%")
            ).first()
            if matched:
                resolved_area_id = matched.id

        if resolved_project_id and bucket == BucketType.INBOX:
            bucket = BucketType.PROJECTS
        elif resolved_area_id and bucket == BucketType.INBOX:
            bucket = BucketType.AREAS

        # Create/link suggested tags
        if suggested_tags:
            tag_objects = _resolve_or_create_tags(suggested_tags)

        ai_meta = {
            "confidence": result.get("confidence", 0.0),
            "reasoning": result.get("reasoning", ""),
            "bucket": bucket_str,
            "suggested_project": suggested_project_name,
            "suggested_area": suggested_area_name,
            "suggested_tags": suggested_tags,
        }

    # Handle explicit tag_ids from caller
    if data.get("tag_ids"):
        for tag_id in data["tag_ids"]:
            tag = db.session.get(Tag, tag_id)
            if tag and tag not in tag_objects:
                tag_objects.append(tag)

    # Handle explicit tag_names from caller
    if data.get("tag_names"):
        extra_tags = _resolve_or_create_tags(data["tag_names"])
        for t in extra_tags:
            if t not in tag_objects:
                tag_objects.append(t)

    note = Note(
        raw_text=raw_text,
        bucket=bucket,
        project_id=resolved_project_id,
        area_id=resolved_area_id,
        person_id=resolved_person_id,
        ai_meta=ai_meta,
    )
    note.tags = tag_objects
    db.session.add(note)
    db.session.commit()

    # Queue embedding generation in background
    _queue_embedding(note.id, raw_text)

    return jsonify({"data": note.to_dict()}), 201


@api_bp.route("/notes/<note_id>", methods=["GET"])
def get_note(note_id):
    note = db.session.get(Note, note_id)
    if not note:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": note.to_dict()})


@api_bp.route("/notes/<note_id>", methods=["PATCH", "PUT"])
def update_note(note_id):
    note = db.session.get(Note, note_id)
    if not note:
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    text_changed = False
    if "raw_text" in data:
        note.raw_text = data["raw_text"]
        text_changed = True
    if "bucket" in data:
        try:
            note.bucket = BucketType(data["bucket"].upper())
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

    # Tag updates
    if "tag_ids" in data:
        tags = []
        for tag_id in data["tag_ids"]:
            tag = db.session.get(Tag, tag_id)
            if tag:
                tags.append(tag)
        note.tags = tags
    elif "tag_names" in data:
        note.tags = _resolve_or_create_tags(data["tag_names"])

    db.session.commit()

    if text_changed:
        _queue_embedding(note.id, note.raw_text)

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
    mode = request.args.get("mode", "hybrid")  # hybrid | fts | semantic
    results = search_notes(q, limit=limit, mode=mode)
    return jsonify({"data": results, "query": q, "count": len(results), "mode": mode})


def _queue_embedding(note_id: str, text: str):
    """Generate and store embedding in a background thread with app context."""
    import threading
    from flask import current_app
    app = current_app._get_current_object()

    def _embed():
        with app.app_context():
            try:
                from services.embeddings import embed_note
                embed_note(note_id, text)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Embedding failed for {note_id}: {e}")

    threading.Thread(target=_embed, daemon=True).start()
