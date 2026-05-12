from flask import request, jsonify
from api import api_bp, api_v2_bp
from extensions import db
from models import Entity, EntityLink
from services.link_service import (
    create_link as svc_create_link,
    delete_link as svc_delete_link,
    get_links,
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

    result = []
    for link in links:
        d = link.to_dict()
        if str(link.src_id) == entity_id:
            d["direction"] = "outgoing"
            other = db.session.get(Entity, link.dst_id)
        else:
            d["direction"] = "incoming"
            other = db.session.get(Entity, link.src_id)

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
