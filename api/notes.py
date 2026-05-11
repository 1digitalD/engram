from sqlalchemy import or_

from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Note, BucketType, Tag, Project, Area, Person
from services.search import search_notes


def _apply_note_project_ids(note: Note, project_ids: list) -> None:
    """Replace note↔projects links; primary project_id becomes first listed id."""
    ordered = []
    seen = set()
    for pid in project_ids:
        if not pid or pid in seen:
            continue
        seen.add(pid)
        p = db.session.get(Project, pid)
        if p:
            ordered.append(p)
    note.projects = ordered
    note.project_id = ordered[0].id if ordered else None


def _project_ids_payload_from_note_data(note: Note, data: dict) -> None:
    """Apply project links from JSON: project_ids array wins; else legacy project_id scalar."""
    if "project_ids" in data:
        raw = data.get("project_ids")
        ids = raw if isinstance(raw, list) else []
        _apply_note_project_ids(note, ids)
    elif "project_id" in data:
        pid = data.get("project_id")
        _apply_note_project_ids(note, [pid] if pid else [])


def _resolve_or_create_tags(tag_names: list) -> list:
    """Find existing tags by name (case-insensitive) or create them."""
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


def _project_ids_query_values():
    """?project_ids=a&project_ids=b or ?project_ids=a,b — deduped, non-empty strings only."""
    raw = request.args.getlist("project_ids")
    out = []
    for part in raw:
        if not part or not str(part).strip():
            continue
        if "," in part:
            out.extend(p.strip() for p in part.split(",") if p.strip())
        else:
            out.append(str(part).strip())
    seen = set()
    ordered = []
    for pid in out:
        if pid not in seen:
            seen.add(pid)
            ordered.append(pid)
    return ordered


@api_bp.route("/notes", methods=["GET"])
def list_notes():
    bucket = request.args.get("bucket")
    project_ids_filter = _project_ids_query_values()
    project_id = request.args.get("project_id")
    area_id = request.args.get("area_id")
    tag_id = request.args.get("tag_id")
    archived = request.args.get("archived", "false").lower() == "true"
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    q = Note.query

    if bucket:
        try:
            b = BucketType(bucket.upper()).value
            q = q.filter(Note.bucket == b)
        except ValueError:
            pass

    if project_ids_filter:
        q = q.filter(
            or_(
                *[
                    or_(
                        Note.project_id == pid,
                        Note.projects.any(Project.id == pid),
                    )
                    for pid in project_ids_filter
                ]
            )
        )
    elif project_id:
        q = q.filter(
            or_(
                Note.project_id == project_id,
                Note.projects.any(Project.id == project_id),
            )
        )
    if area_id:
        q = q.filter(Note.area_id == area_id)
    if tag_id:
        q = q.filter(Note.tags.any(Tag.id == tag_id))
    if not archived:
        q = q.filter(Note.is_archived == False)

    total = q.count()
    notes = q.order_by(Note.created_at.desc()).offset(offset).limit(limit).all()

    return jsonify({
        "data": [n.to_dict() for n in notes],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@api_bp.route("/notes", methods=["POST"])
def create_note():
    """
    Create a note. Routes through the full ingestion pipeline when classify=true (default).
    Accepts raw_text or content. Returns note + any extracted entities.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    # Accept both field names
    raw_text = data.get("raw_text") or data.get("content")
    if not raw_text:
        return jsonify({"error": "raw_text is required"}), 400

    do_classify = data.get("classify", True)

    # Fast path: caller opts out of AI (explicit classify=false)
    if not do_classify:
        return _create_note_simple(data, raw_text)

    # Full ingestion pipeline
    try:
        from services.ingestion import run_ingestion
        result = run_ingestion(
            content=raw_text,
            source=data.get("source", "api"),
        )
        if "error" in result:
            return jsonify(result), 400

        # Merge caller-supplied IDs if the AI didn't link anything
        note_id = result["note"]["id"]
        note_obj = db.session.get(Note, note_id)
        changed = False

        if "project_ids" in data or "project_id" in data:
            _project_ids_payload_from_note_data(note_obj, data)
            changed = True
        if data.get("area_id") and not note_obj.area_id:
            note_obj.area_id = data["area_id"]
            changed = True
        if data.get("person_id") and not note_obj.person_id:
            note_obj.person_id = data["person_id"]
            changed = True
        if changed:
            from services.extractor import extract_inline_tasks

            extract_inline_tasks(
                note_obj.id,
                note_obj.raw_text,
                note_obj.project_id,
                note_obj.area_id,
            )
            db.session.commit()

        # Return note in standard format + enrichment fields for callers that want them
        return jsonify({
            "data": note_obj.to_dict(),
            "tasks": result.get("tasks", []),
            "people": result.get("people", []),
            "project": result.get("project"),
            "area": result.get("area"),
            "confident": result.get("confident", False),
            "extraction": result.get("extraction", {}),
        }), 201

    except Exception as e:
        import logging
        logging.getLogger(__name__).exception(f"Ingestion pipeline failed, falling back: {e}")
        return _create_note_simple(data, raw_text)


def _create_note_simple(data: dict, raw_text: str):
    """Fallback: create note with basic classification only (no entity extraction)."""
    from services.classifier import classify_note

    explicit_bucket = data.get("bucket")
    bucket = BucketType.INBOX.value
    if explicit_bucket:
        try:
            bucket = BucketType(explicit_bucket.upper()).value
        except ValueError:
            pass

    ai_meta = data.get("ai_meta")  # preserve caller-supplied ai_meta when classify=false
    explicit_projects = "project_ids" in data or "project_id" in data
    resolved_project_id = None if explicit_projects else data.get("project_id")
    resolved_area_id = data.get("area_id")
    tag_objects = []

    if data.get("classify", True) and not explicit_bucket:
        ai_meta = None  # classifier will generate fresh ai_meta below
        from models import Project, Area
        existing_projects = [p.name for p in Project.query.filter_by(is_archived=False).all()]
        existing_areas = [a.name for a in Area.query.all()]
        result = classify_note(raw_text, projects=existing_projects, areas=existing_areas)
        try:
            bucket = BucketType(result.get("bucket", "INBOX").upper()).value
        except ValueError:
            bucket = BucketType.INBOX.value

        suggested_project = result.get("suggested_project")
        suggested_area = result.get("suggested_area")

        if suggested_project and not resolved_project_id:
            from models import Project
            m = Project.query.filter(Project.name.ilike(f"%{suggested_project}%")).first()
            if m:
                resolved_project_id = m.id
        if suggested_area and not resolved_area_id:
            from models import Area
            m = Area.query.filter(Area.name.ilike(f"%{suggested_area}%")).first()
            if m:
                resolved_area_id = m.id

        if resolved_project_id and bucket == BucketType.INBOX.value:
            bucket = BucketType.PROJECTS.value
        elif resolved_area_id and bucket == BucketType.INBOX.value:
            bucket = BucketType.AREAS.value

        if result.get("suggested_tags"):
            tag_objects = _resolve_or_create_tags(result["suggested_tags"])

        ai_meta = {
            "confidence": result.get("confidence", 0.0),
            "reasoning": result.get("reasoning", ""),
            "bucket": result.get("bucket", "INBOX"),
            "suggested_project": suggested_project,
            "suggested_area": suggested_area,
            "suggested_tags": result.get("suggested_tags", []),
        }

    if data.get("tag_ids"):
        from models import Tag
        for tag_id in data["tag_ids"]:
            tag = db.session.get(Tag, tag_id)
            if tag and tag not in tag_objects:
                tag_objects.append(tag)
    if data.get("tag_names"):
        for t in _resolve_or_create_tags(data["tag_names"]):
            if t not in tag_objects:
                tag_objects.append(t)

    note = Note(
        raw_text=raw_text,
        bucket=bucket,
        project_id=resolved_project_id,
        area_id=resolved_area_id,
        person_id=data.get("person_id"),
        ai_meta=ai_meta,
    )
    note.tags = tag_objects
    db.session.add(note)
    db.session.flush()
    if explicit_projects:
        _project_ids_payload_from_note_data(note, data)
        db.session.flush()
    note_id = note.id
    from services.extractor import extract_inline_tasks

    extract_inline_tasks(note_id, raw_text, note.project_id, note.area_id)
    db.session.commit()
    _queue_embedding(note_id, raw_text)
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
    classify_requested = data.get("classify", False)
    if "raw_text" in data:
        new_text = data["raw_text"]
        if note.raw_text != new_text:
            note.raw_text = new_text
            text_changed = True
    if "bucket" in data:
        try:
            note.bucket = BucketType(data["bucket"].upper()).value
        except ValueError:
            pass
    if "project_ids" in data or "project_id" in data:
        _project_ids_payload_from_note_data(note, data)
    if "area_id" in data:
        note.area_id = data["area_id"]
    if "person_id" in data:
        note.person_id = data["person_id"]
    if "is_archived" in data:
        note.is_archived = data["is_archived"]

    # Preserve caller-supplied ai_meta unless classify=true (which regenerates it below)
    if "ai_meta" in data and not classify_requested:
        caller_meta = data["ai_meta"]
        if isinstance(caller_meta, dict):
            note.ai_meta = caller_meta

    # ai_meta is server-only when classify=true (classifier regenerates it below)

    # Re-classify / extract on demand
    if classify_requested:
        from services.extractor import extract
        import time

        # Per-note cooldown: reject if classified in the last 60 seconds
        last_classified = (note.ai_meta or {}).get("last_classified_at", 0)
        if time.time() - last_classified < 60:
            return jsonify({"error": "rate limited: note was classified recently, try again shortly"}), 429

        all_projects = [p.name for p in Project.query.filter_by(is_archived=False).all()]
        all_areas    = [a.name for a in Area.query.filter_by(is_archived=False).all()]
        result = extract(note.raw_text, projects=all_projects, area_names=all_areas)

        # Multi-project linking: resolve all mentioned projects
        all_project_ids: list[str] = []
        if result.suggested_project:
            matched = Project.query.filter(
                Project.name.ilike(f"%{result.suggested_project}%")
            ).first()
            if matched:
                all_project_ids.append(matched.id)
        # Resolve additional projects hinted by tasks
        for task in (result.tasks or []):
            if task.project_hint:
                matched = Project.query.filter(
                    Project.name.ilike(f"%{task.project_hint}%")
                ).first()
                if matched and matched.id not in all_project_ids:
                    all_project_ids.append(matched.id)

        # Resolve suggested area
        resolved_area_id = None
        if result.suggested_area:
            m = Area.query.filter(Area.name.ilike(f"%{result.suggested_area}%")).first()
            if m:
                resolved_area_id = m.id

        # Auto-link projects (only when note has no existing links)
        note_project_links = db.session.execute(
            db.text("SELECT project_id FROM note_projects WHERE note_id = :nid"),
            {"nid": note.id}
        ).fetchall()
        note_has_project_link = any(row[0] for row in note_project_links)

        if all_project_ids and not note.project_id and not note_has_project_link:
            for pid in all_project_ids:
                db.session.execute(
                    db.text("INSERT INTO note_projects (note_id, project_id) VALUES (:nid, :pid)"),
                    {"nid": note.id, "pid": pid}
                )
        if resolved_area_id and not note.area_id:
            note.area_id = resolved_area_id

        # Extract tasks: create Task records for extracted action items (skip duplicates)
        if result.tasks:
            from models import Task, TaskStatus
            from datetime import datetime
            for etask in result.tasks:
                existing = Task.query.filter_by(
                    note_id=note.id, title=etask.title, status=TaskStatus.PENDING
                ).first()
                if existing:
                    continue
                pid = None
                if etask.project_hint:
                    m = Project.query.filter(Project.name.ilike(f"%{etask.project_hint}%")).first()
                    if m:
                        pid = m.id
                due = None
                if etask.due_date:
                    try:
                        due = datetime.strptime(etask.due_date, "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        pass
                task = Task(
                    title=etask.title,
                    note_id=note.id,
                    project_id=pid or note.project_id,
                    area_id=resolved_area_id or note.area_id,
                    status=TaskStatus.PENDING,
                    priority=etask.priority,
                    due_date=due,
                )
                db.session.add(task)

        # Extract people: link or create person records
        if result.people:
            from sqlalchemy.exc import IntegrityError
            for ep in result.people:
                person = Person.query.filter(Person.name.ilike(ep.name)).first()
                if not person:
                    try:
                        person = Person(name=ep.name, email=ep.email or None)
                        db.session.add(person)
                        db.session.flush()
                    except IntegrityError:
                        db.session.rollback()
                        person = Person.query.filter(Person.name.ilike(ep.name)).first()
                        if not person:
                            continue
                # Link to note if not already linked
                if not note.person_id:
                    note.person_id = person.id

        # Update ai_meta
        note.ai_meta = {
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "bucket": result.para_bucket,
            "suggested_project": result.suggested_project,
            "suggested_area": result.suggested_area,
            "suggested_tags": result.tags,
            "extracted_tasks": [
                {"title": t.title, "priority": t.priority, "due_date": t.due_date, "project_hint": t.project_hint}
                for t in (result.tasks or [])
            ],
            "extracted_people": [
                {"name": p.name} for p in (result.people or [])
            ],
            "source": "on-demand-extract",
            "last_classified_at": time.time(),
        }

    if "tag_ids" in data:
        tags = []
        for tag_id in data["tag_ids"]:
            tag = db.session.get(Tag, tag_id)
            if tag:
                tags.append(tag)
        note.tags = tags
    elif "tag_names" in data:
        note.tags = _resolve_or_create_tags(data["tag_names"])

    note_id = note.id
    note_text = note.raw_text
    if text_changed:
        from services.extractor import extract_inline_tasks

        extract_inline_tasks(note_id, note_text, note.project_id, note.area_id)
    db.session.commit()
    if text_changed:
        _queue_embedding(note_id, note_text)
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
    mode = request.args.get("mode", "hybrid")
    bucket = request.args.get("bucket")
    project_id = request.args.get("project_id")
    area_id = request.args.get("area_id")
    results = search_notes(q, limit=limit, mode=mode, bucket=bucket, project_id=project_id, area_id=area_id)
    return jsonify({"data": results, "query": q, "count": len(results), "mode": mode})


def _queue_embedding(note_id: str, text: str):
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
