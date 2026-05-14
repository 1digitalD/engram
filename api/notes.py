"""Notes API — Entity-based with backward-compat response shape.

All note operations use Entity(type='note') + entity_service.
Backward-compat aliases ensure legacy response shapes work.
"""

from datetime import datetime, timezone

from collections import defaultdict

from flask import request, jsonify
from sqlalchemy.orm import subqueryload

from api import api_bp
from extensions import db
from models import Entity, EntityTag, EntityLink, Tag
from services.entity_service import create_entity, update_entity, archive_entity, delete_entity
from services.link_service import _set_inverse


def _resolve_or_create_tags(tag_names):
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


def _apply_tags(entity, data):
    """Apply tag_ids or tag_names from request data to entity."""
    if "tag_ids" in data:
        EntityTag.query.filter_by(entity_id=entity.id).delete()
        for tag_id in data["tag_ids"]:
            tag = db.session.get(Tag, tag_id)
            if tag:
                db.session.add(EntityTag(entity_id=entity.id, tag_id=tag.id))
    elif "tag_names" in data:
        EntityTag.query.filter_by(entity_id=entity.id).delete()
        for tag in _resolve_or_create_tags(data["tag_names"]):
            db.session.add(EntityTag(entity_id=entity.id, tag_id=tag.id))


def _apply_project_links(entity, data):
    """Apply project_id or project_ids from request data as entity links."""
    project_ids = []
    if "project_ids" in data:
        raw = data.get("project_ids")
        project_ids = raw if isinstance(raw, list) else []
    elif "project_id" in data:
        pid = data.get("project_id")
        project_ids = [pid] if pid else []

    if project_ids is not None:
        # Remove existing project links (legacy v1 type, then v2 parent type)
        EntityLink.query.filter(
            EntityLink.src_id == entity.id,
            EntityLink.link_type.in_(["project", "parent"])
        ).delete(synchronize_session=False)
        for pid in project_ids:
            if pid and db.session.get(Entity, pid):
                link = EntityLink(
                    src_id=entity.id, dst_id=pid, link_type="parent", source="manual"
                )
                link.inverse = "child"
                db.session.add(link)


def _entity_to_note_response(entity):
    """Convert Entity to note-like response dict with all legacy fields."""
    d = entity.to_dict()
    # Ensure tag_ids are populated from EntityTag relationship
    if not d.get("tag_ids") and entity.entity_tags:
        d["tag_ids"] = [et.tag_id for et in entity.entity_tags]
    # Ensure project_ids are populated from EntityLink relationship
    if not d.get("project_ids"):
        project_links = EntityLink.query.filter(
            EntityLink.src_id == entity.id,
            EntityLink.link_type.in_(["parent", "project"])
        ).all()
        d["project_ids"] = [link.dst_id for link in project_links]
        d["project_id"] = d["project_ids"][0] if d["project_ids"] else None
        d["projects"] = []
        for link in project_links:
            proj = db.session.get(Entity, link.dst_id)
            if proj:
                d["projects"].append({"id": proj.id, "name": proj.title})
    return d


@api_bp.route("/notes", methods=["GET"])
def list_notes():
    bucket = request.args.get("bucket")
    project_id = request.args.get("project_id")
    area_id = request.args.get("area_id")
    tag_id = request.args.get("tag_id")
    archived = request.args.get("archived", "false").lower() == "true"
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    q = Entity.query.filter_by(type="note").options(
        subqueryload(Entity.entity_tags).subqueryload(EntityTag.tag)
    )
    if not archived:
        q = q.filter(Entity.lifecycle != "archived")
    if bucket:
        q = q.filter(Entity.properties.contains({"bucket": bucket.upper()}))
    if area_id:
        q = q.filter(Entity.properties.contains({"area_id": area_id}))
    if project_id:
        note_ids_with_project = db.session.query(EntityLink.src_id).filter(
            EntityLink.dst_id == project_id,
            EntityLink.link_type.in_(["parent", "project"])
        ).subquery()
        q = q.filter(Entity.id.in_(note_ids_with_project))
    if tag_id:
        note_ids_with_tag = db.session.query(EntityTag.entity_id).filter_by(tag_id=tag_id).subquery()
        q = q.filter(Entity.id.in_(note_ids_with_tag))

    total = q.count()
    notes = q.order_by(Entity.created_at.desc()).offset(offset).limit(limit).all()

    # Batch-load project links to avoid N+1 in _entity_to_note_response
    note_ids = [n.id for n in notes]
    if note_ids:
        project_links = EntityLink.query.filter(
            EntityLink.src_id.in_(note_ids),
            EntityLink.link_type.in_(["parent", "project"])
        ).all()

        # Batch-load linked project entities
        project_ids = list(set(l.dst_id for l in project_links))
        if project_ids:
            Entity.query.filter(Entity.id.in_(project_ids)).all()

    return jsonify({
        "data": [_entity_to_note_response(n) for n in notes],
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@api_bp.route("/notes", methods=["POST"])
def create_note():
    """Create a note. Routes through AI pipeline when classify=true (default)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    raw_text = data.get("raw_text") or data.get("content")
    if not raw_text:
        return jsonify({"error": "raw_text is required"}), 400

    do_classify = data.get("classify", True)

    properties = {}
    if data.get("bucket"):
        properties["bucket"] = data["bucket"].upper()
    if data.get("area_id"):
        properties["area_id"] = data["area_id"]
    if data.get("person_id"):
        properties["person_id"] = data["person_id"]

    entity = create_entity(
        entity_type="note",
        content=raw_text,
        properties=properties,
        source=data.get("source", "manual"),
        actor="user",
    )

    # Apply project links
    _apply_project_links(entity, data)

    # Apply tags
    _apply_tags(entity, data)

    db.session.commit()
    entity = db.session.get(Entity, entity.id)

    response = _entity_to_note_response(entity)
    resp_data = {"data": response}

    if do_classify:
        resp_data["ai_status"] = entity.ai_status
        resp_data["jobs"] = ["classify", "embed"]

    return jsonify(resp_data), 201


@api_bp.route("/notes/<note_id>", methods=["GET"])
def get_note(note_id):
    note = Entity.query.filter_by(id=note_id, type="note").first()
    if not note:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": _entity_to_note_response(note)})


@api_bp.route("/notes/<note_id>", methods=["PATCH", "PUT"])
def update_note(note_id):
    note = Entity.query.filter_by(id=note_id, type="note").first()
    if not note:
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    fields = {}
    if "raw_text" in data or "content" in data:
        fields["content"] = data.get("raw_text") or data.get("content")

    props = dict(note.properties or {})
    if "bucket" in data:
        props["bucket"] = data["bucket"].upper()
    if "area_id" in data:
        props["area_id"] = data["area_id"]
    if "person_id" in data:
        props["person_id"] = data["person_id"]
    if props != (note.properties or {}):
        fields["properties"] = props

    if "is_archived" in data:
        if data["is_archived"]:
            try:
                archive_entity(note_id, actor="user")
            except ValueError:
                pass
        else:
            note.lifecycle = "active"
            db.session.commit()

    if fields:
        update_entity(note_id, fields, actor="user")
        note = db.session.get(Entity, note_id)

    # Apply project links
    if "project_ids" in data or "project_id" in data:
        _apply_project_links(note, data)

    # Apply tags
    _apply_tags(note, data)

    db.session.commit()
    note = db.session.get(Entity, note_id)

    return jsonify({"data": _entity_to_note_response(note)})


@api_bp.route("/notes/<note_id>", methods=["DELETE"])
def delete_note(note_id):
    note = Entity.query.filter_by(id=note_id, type="note").first()
    if not note:
        return jsonify({"error": "not found"}), 404
    cascade = request.args.get("cascade", "false").lower() == "true"
    try:
        result = delete_entity(note_id, cascade_orphans=cascade)
        if not cascade:
            return jsonify({
                "safe_to_cascade": result["safe_to_cascade"],
                "blocked": result["blocked"],
            })
        return jsonify({"deleted": result["deleted"], "blocked": result["blocked"]})
    except ValueError:
        return jsonify({"error": "not found"}), 404


@api_bp.route("/notes/search", methods=["GET"])
def search_notes_endpoint():
    q = request.args.get("q", "")
    limit = request.args.get("limit", 20, type=int)

    results = Entity.query.filter(
        Entity.type == "note",
        Entity.content.ilike(f"%{q}%")
    ).order_by(Entity.updated_at.desc()).limit(limit).all()

    return jsonify({
        "data": [_entity_to_note_response(r) for r in results],
        "query": q,
        "count": len(results),
    })
