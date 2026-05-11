from flask import Blueprint, request, jsonify
from api import api_bp
from extensions import db
from models import Link, Note, Entity, EntityLink
from services.links import VALID_LINK_TYPES
import logging

logger = logging.getLogger(__name__)


# ─── V2 Blueprint ────────────────────────────────────────────────────────────

api_v2_bp = Blueprint("api_v2", __name__, url_prefix="/api/v2")


@api_bp.route("/links", methods=["GET"])
def list_links():
    """List all note↔note links (for graph / analytics)."""
    limit = request.args.get("limit", 10000, type=int)
    limit = max(1, min(limit, 50000))
    rows = Link.query.order_by(Link.created_at.desc()).limit(limit).all()
    return jsonify({"data": [l.to_dict() for l in rows]})


@api_bp.route("/notes/<note_id>/links", methods=["GET"])
def get_note_links(note_id):
    """Get all outgoing and incoming links for a note."""
    note = db.session.get(Note, note_id)
    if not note:
        return jsonify({"error": "not found"}), 404

    outgoing = [l.to_dict() for l in note.outgoing_links]
    incoming = [l.to_dict() for l in note.incoming_links]

    return jsonify({
        "outgoing": outgoing,
        "incoming": incoming,
        "total": len(outgoing) + len(incoming),
    })


@api_bp.route("/notes/<note_id>/related", methods=["GET"])
def get_related_notes(note_id):
    """Get semantically related notes using embedding similarity."""
    note = db.session.get(Note, note_id)
    if not note:
        return jsonify({"error": "not found"}), 404

    limit = request.args.get("limit", 5, type=int)

    try:
        from services.embeddings import find_related_note_ids
        related = find_related_note_ids(note_id, limit=limit, min_similarity=0.75)
        results = []
        for other_id, similarity in related:
            other = db.session.get(Note, other_id)
            if other:
                d = other.to_dict()
                d["_similarity"] = round(similarity, 4)
                results.append(d)
        return jsonify({"data": results, "note_id": note_id})
    except Exception as e:
        logger.error(f"Related notes failed: {e}")
        return jsonify({"data": [], "note_id": note_id})


@api_bp.route("/links", methods=["POST"])
def create_link():
    """Create a manual link between two notes."""
    data = request.get_json(silent=True) or {}

    src_id = data.get("src_id")
    dst_id = data.get("dst_id")
    link_type = data.get("link_type", "related")

    if not src_id or not dst_id:
        return jsonify({"error": "src_id and dst_id are required"}), 400

    if link_type not in VALID_LINK_TYPES:
        return jsonify({"error": f"link_type must be one of: {', '.join(VALID_LINK_TYPES)}"}), 400

    if not db.session.get(Note, src_id) or not db.session.get(Note, dst_id):
        return jsonify({"error": "one or both notes not found"}), 404

    existing = Link.query.filter_by(src_id=src_id, dst_id=dst_id, link_type=link_type).first()
    if existing:
        return jsonify({"data": existing.to_dict()}), 200

    link = Link(
        src_id=src_id,
        dst_id=dst_id,
        link_type=link_type,
        weight=data.get("weight", 1.0),
        source="manual",
    )
    db.session.add(link)
    db.session.commit()
    return jsonify({"data": link.to_dict()}), 201


@api_bp.route("/links/<link_id>", methods=["DELETE"])
def delete_link(link_id):
    link = db.session.get(Link, link_id)
    if not link:
        return jsonify({"error": "not found"}), 404
    db.session.delete(link)
    db.session.commit()
    return jsonify({"success": True}), 200


# ─── V2: Universal Entity Links API ──────────────────────────────────────────


@api_v2_bp.route("/links/<entity_id>", methods=["GET"])
def get_entity_links_v2(entity_id):
    """Universal entity links endpoint — direction-agnostic with filtering and pagination.

    GET /api/v2/links/:entity_id
    Query params:
        link_type — filter by link type (e.g. 'related', 'parent')
        limit     — page size (default 50, max 1000)
        offset    — page offset (default 0)

    Returns paginated list of all links where the entity is src or dst,
    with direction indicator, weight/confidence strength fields, and
    the other entity's basic info.
    """
    entity = db.session.get(Entity, entity_id)
    if entity is None:
        return jsonify({"error": "entity not found"}), 404

    link_type = request.args.get("link_type")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    limit = max(1, min(limit, 1000))

    query = EntityLink.query.filter(
        (EntityLink.src_id == entity_id) | (EntityLink.dst_id == entity_id)
    )

    if link_type:
        query = query.filter(EntityLink.link_type == link_type)

    total = query.count()
    links = query.order_by(EntityLink.created_at.desc()).limit(limit).offset(offset).all()

    result = []
    for link in links:
        is_outgoing = link.src_id == entity_id
        other_id = link.dst_id if is_outgoing else link.src_id
        other_entity = db.session.get(Entity, other_id)

        link_data = link.to_dict()
        link_data["direction"] = "outgoing" if is_outgoing else "incoming"
        if other_entity:
            link_data["other_entity"] = {
                "id": other_entity.id,
                "type": other_entity.type,
                "title": other_entity.title,
                "lifecycle": other_entity.lifecycle,
            }
        result.append(link_data)

    return jsonify({
        "data": result,
        "total": total,
        "limit": limit,
        "offset": offset,
    })
