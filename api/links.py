from flask import request, jsonify
from api import api_bp
from extensions import db
from models import Link, Note
from services.links import VALID_LINK_TYPES
import logging

logger = logging.getLogger(__name__)


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
