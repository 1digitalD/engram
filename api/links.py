from flask import request, jsonify
from api import api_bp, api_v2_bp
from extensions import db
from models import Entity, EntityLink, EntityEvent, LinkTypeAllowlist
from services.link_service import (
    create_link as svc_create_link,
    delete_link as svc_delete_link,
    get_links,
)
from services.entity_service import (
    delete_preview as svc_delete_preview,
    delete_entity as svc_delete_entity,
)
import logging

logger = logging.getLogger(__name__)

MAX_V2_LIMIT = 1000
DEFAULT_V2_LIMIT = 50


# ─── Legacy v1 routes (rewritten for Entity/EntityLink) ──────────────────────


@api_bp.route("/links", methods=["GET"])
def list_links():
    """List all entity links (for graph / analytics)."""
    limit = request.args.get("limit", 10000, type=int)
    limit = max(1, min(limit, 50000))
    rows = (
        EntityLink.query
        .order_by(EntityLink.created_at.desc())
        .limit(limit)
        .all()
    )
    return jsonify({"data": [l.to_dict() for l in rows]})


@api_bp.route("/notes/<note_id>/links", methods=["GET"])
def get_note_links(note_id):
    """Get all outgoing and incoming links for an entity."""
    entity = Entity.query.filter_by(id=note_id, type="note").first()
    if not entity:
        return jsonify({"error": "not found"}), 404

    links = get_links(note_id)
    outgoing = [l.to_dict() for l in links if l.src_id == note_id]
    incoming = [l.to_dict() for l in links if l.dst_id == note_id]

    return jsonify({
        "outgoing": outgoing,
        "incoming": incoming,
        "total": len(outgoing) + len(incoming),
    })


@api_bp.route("/notes/<note_id>/related", methods=["GET"])
def get_related_notes(note_id):
    """Get semantically related entities using embedding similarity."""
    entity = Entity.query.filter_by(id=note_id, type="note").first()
    if not entity:
        return jsonify({"error": "not found"}), 404

    limit = request.args.get("limit", 5, type=int)

    try:
        from services.search import find_related
        related = find_related(note_id, limit=limit)
        results = []
        for other in related:
            d = other.to_dict() if hasattr(other, "to_dict") else other
            results.append(d)
        return jsonify({"data": results, "note_id": note_id})
    except Exception as e:
        logger.error(f"Related notes failed: {e}")
        return jsonify({"data": [], "note_id": note_id})


@api_bp.route("/links", methods=["POST"])
def create_link():
    """Create a manual link between two entities."""
    data = request.get_json(silent=True) or {}

    src_id = data.get("src_id")
    dst_id = data.get("dst_id")
    link_type = data.get("link_type", "related")

    if not src_id or not dst_id:
        return jsonify({"error": "src_id and dst_id are required"}), 400

    if not db.session.get(Entity, src_id) or not db.session.get(Entity, dst_id):
        return jsonify({"error": "one or both entities not found"}), 404

    try:
        link = svc_create_link(
            src_id=src_id,
            dst_id=dst_id,
            link_type=link_type,
            source="manual",
            actor="user",
        )
        return jsonify({"data": link.to_dict()}), 201
    except ValueError as e:
        if "already exists" in str(e):
            existing = EntityLink.query.filter_by(
                src_id=src_id, dst_id=dst_id, link_type=link_type
            ).first()
            if existing:
                return jsonify({"data": existing.to_dict()}), 200
        return jsonify({"error": str(e)}), 400


@api_bp.route("/links/<link_id>", methods=["DELETE"])
def delete_link(link_id):
    try:
        svc_delete_link(link_id, actor="user")
        return jsonify({"success": True}), 200
    except ValueError:
        return jsonify({"error": "not found"}), 404


# ─── V2 routes on api_v2_bp ──────────────────────────────────────────────────


@api_v2_bp.route("/links/<entity_id>", methods=["GET"])
def v2_get_entity_links(entity_id):
    """Get all links (src and dst) for an entity, direction-agnostic."""
    entity = db.session.get(Entity, entity_id)
    if not entity:
        return jsonify({"error": "not found"}), 404

    limit = request.args.get("limit", DEFAULT_V2_LIMIT, type=int)
    limit = max(1, min(limit, MAX_V2_LIMIT))
    offset = request.args.get("offset", 0, type=int)
    link_type_filter = request.args.get("link_type")

    query = EntityLink.query.filter(
        (EntityLink.src_id == entity_id) | (EntityLink.dst_id == entity_id)
    )
    if link_type_filter:
        query = query.filter(EntityLink.link_type == link_type_filter)

    total = query.count()
    links = (
        query.order_by(EntityLink.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Batch-load other entities to avoid N+1
    other_ids = set()
    for link in links:
        if str(link.src_id) == entity_id:
            other_ids.add(link.dst_id)
        else:
            other_ids.add(link.src_id)
    if other_ids:
        other_entities = {
            e.id: e
            for e in Entity.query.filter(Entity.id.in_(list(other_ids))).all()
        }
    else:
        other_entities = {}

    result = []
    for link in links:
        d = link.to_dict()
        if str(link.src_id) == entity_id:
            d["direction"] = "outgoing"
            other = other_entities.get(link.dst_id)
        else:
            d["direction"] = "incoming"
            other = other_entities.get(link.src_id)

        if other:
            d["other_entity"] = {
                "id": str(other.id),
                "title": other.title,
                "type": other.type,
            }
        result.append(d)

    return jsonify({
        "data": result,
        "total": total,
        "limit": limit,
        "offset": offset,
    })


@api_v2_bp.route("/link-types/<src_type>/<dst_type>", methods=["GET"])
def v2_get_allowed_link_types(src_type, dst_type):
    """Return allowed link types between two entity types."""
    allowed = LinkTypeAllowlist.get_allowed_types(src_type, dst_type)
    return jsonify({"data": allowed})


@api_v2_bp.route("/link-types", methods=["GET"])
def v2_list_all_link_types():
    """Return all allowed link types (full matrix)."""
    rows = LinkTypeAllowlist.query.order_by(
        LinkTypeAllowlist.src_type, LinkTypeAllowlist.dst_type
    ).all()
    return jsonify({"data": [r.to_dict() for r in rows]})


@api_v2_bp.route("/entity-links", methods=["POST"])
def v2_create_entity_link():
    """Create a link between two entities."""
    data = request.get_json(silent=True) or {}
    src_id = data.get("src_id")
    dst_id = data.get("dst_id")
    link_type = data.get("link_type", "related")

    if not src_id or not dst_id:
        return jsonify({"error": "src_id and dst_id are required"}), 400

    try:
        link = svc_create_link(
            src_id=src_id,
            dst_id=dst_id,
            link_type=link_type,
            source=data.get("source", "manual"),
            confidence=data.get("confidence"),
            evidence=data.get("evidence"),
            actor="user",
        )
        return jsonify({"data": link.to_dict()}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@api_v2_bp.route("/entity-links/<link_id>", methods=["PATCH"])
def v2_update_entity_link(link_id):
    """Update a link's link_type (re-validates against allowlist)."""
    data = request.get_json(silent=True) or {}
    new_link_type = data.get("link_type")
    if not new_link_type:
        return jsonify({"error": "link_type is required"}), 400

    link = db.session.get(EntityLink, link_id)
    if not link:
        return jsonify({"error": "not found"}), 404

    src = db.session.get(Entity, link.src_id)
    dst = db.session.get(Entity, link.dst_id)
    if not src or not dst:
        return jsonify({"error": "linked entities not found"}), 500

    if not LinkTypeAllowlist.is_allowed(src.type, dst.type, new_link_type):
        return jsonify({
            "error": f"link type {new_link_type!r} not allowed between "
                     f"{src.type!r} and {dst.type!r}"
        }), 422

    from services.link_service import update_link as svc_update_link
    try:
        updated = svc_update_link(link_id, new_link_type, actor="user")
        return jsonify({"data": updated.to_dict()}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@api_v2_bp.route("/entity-links/<link_id>", methods=["DELETE"])
def v2_delete_entity_link(link_id):
    """Delete an entity link."""
    try:
        svc_delete_link(link_id, actor="user")
        return jsonify({"success": True}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


# ─── V2 delete-preview endpoint ──────────────────────────────────────────────


@api_v2_bp.route("/entities/<entity_id>/delete-preview", methods=["GET"])
def v2_delete_preview(entity_id):
    """Preview what would be deleted if entity_id is deleted.

    Returns orphan analysis: which linked entities would be safely cascade-deleted
    vs which are blocked (have other connections).
    """
    try:
        preview = svc_delete_preview(entity_id)
        return jsonify({
            "entity": preview["entity"],
            "safe_to_cascade": preview["safe_to_cascade"],
            "blocked": preview["blocked"],
        })
    except ValueError:
        return jsonify({"error": "not found"}), 404


@api_v2_bp.route("/entities/<entity_id>/events", methods=["GET"])
def v2_entity_events(entity_id):
    """Return event/audit history for an entity."""
    entity = db.session.get(Entity, entity_id)
    if not entity:
        return jsonify({"error": "not found"}), 404

    limit = request.args.get("limit", 50, type=int)
    event_type = request.args.get("event_type")
    actor = request.args.get("actor")

    q = EntityEvent.query.filter_by(entity_id=entity_id)
    if event_type:
        q = q.filter(EntityEvent.event_type == event_type)
    if actor:
        q = q.filter(EntityEvent.actor == actor)

    events = q.order_by(EntityEvent.created_at.desc()).limit(limit).all()
    return jsonify({"data": [e.to_dict() for e in events]})
