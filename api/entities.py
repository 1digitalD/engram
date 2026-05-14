"""Universal entity API — unified CRUD across all entity types.

GET    /api/v2/entities/:id         — get any entity
PATCH  /api/v2/entities/:id         — update any entity
DELETE /api/v2/entities/:id         — delete any entity
GET    /api/v2/entities/:id/links   — get all links for entity
GET    /api/v2/entities/:id/events  — get events for entity
"""

from flask import request, jsonify
from api import api_v2_bp
from extensions import db
from models import Entity, EntityLink, EntityEvent
from services.entity_service import update_entity, delete_entity
import logging

logger = logging.getLogger(__name__)


@api_v2_bp.route("/entities/<entity_id>", methods=["GET"])
def v2_get_entity(entity_id):
    """Get any entity by ID."""
    entity = db.session.get(Entity, entity_id)
    if not entity:
        return jsonify({"error": "Entity not found"}), 404
    return jsonify({"data": entity.to_dict()})


@api_v2_bp.route("/entities/<entity_id>", methods=["PATCH"])
def v2_update_entity(entity_id):
    """Update any entity by ID."""
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "No fields to update"}), 400

    try:
        entity = update_entity(entity_id, data, actor="user")
        return jsonify({"data": entity.to_dict()})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Failed to update entity %s", entity_id)
        return jsonify({"error": str(e)}), 500


@api_v2_bp.route("/entities/<entity_id>", methods=["DELETE"])
def v2_delete_entity(entity_id):
    """Delete an entity with optional cascade."""
    cascade = request.args.get("cascade", "false").lower() == "true"
    try:
        result = delete_entity(entity_id, cascade_orphans=cascade)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Failed to delete entity %s", entity_id)
        return jsonify({"error": str(e)}), 500


@api_v2_bp.route("/entities/<entity_id>/links", methods=["GET"])
def v2_get_entity_links(entity_id):
    """Get all links (incoming + outgoing) for any entity."""
    entity = db.session.get(Entity, entity_id)
    if not entity:
        return jsonify({"error": "Entity not found"}), 404

    outgoing = EntityLink.query.filter_by(src_id=entity_id).all()
    incoming = EntityLink.query.filter_by(dst_id=entity_id).all()

    def _enrich(link, direction):
        d = link.to_dict()
        d["direction"] = direction
        other_id = link.dst_id if direction == "outgoing" else link.src_id
        other = db.session.get(Entity, other_id)
        if other:
            d["src_type"] = link.src_entity.type if link.src_entity else None
            d["dst_type"] = link.dst_entity.type if link.dst_entity else None
            d["other_entity"] = {
                "id": other.id,
                "type": other.type,
                "title": other.title,
                "content": other.content,
            }
        return d

    return jsonify({
        "data": [_enrich(l, "outgoing") for l in outgoing] + [_enrich(l, "incoming") for l in incoming],
        "outgoing": [_enrich(l, "outgoing") for l in outgoing],
        "incoming": [_enrich(l, "incoming") for l in incoming],
    })


@api_v2_bp.route("/entities/<entity_id>/events", methods=["GET"])
def v2_get_entity_events(entity_id):
    """Get events for an entity."""
    entity = db.session.get(Entity, entity_id)
    if not entity:
        return jsonify({"error": "Entity not found"}), 404

    events = EntityEvent.query.filter_by(entity_id=entity_id)\
        .order_by(EntityEvent.created_at.desc())\
        .limit(100)\
        .all()

    return jsonify({
        "data": [e.to_dict() for e in events] if hasattr(events[0] if events else None, 'to_dict') else [
            {"id": e.id, "event_type": e.event_type, "actor": e.actor, "confidence": e.confidence, "reason": e.reason, "created_at": e.created_at.isoformat() if e.created_at else None}
            for e in events
        ],
    })
