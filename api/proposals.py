"""REST API for v2 link proposals stored in entity.ai_meta and ai_suggestions table."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import jsonify, request

from api import api_bp, api_v2_bp
from extensions import db
from models import Entity, EntityLink, AiSuggestion
from services.link_service import create_link as svc_create_link
from sqlalchemy import or_

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 100
MAX_LIMIT = 500


def _link_exists(src_id: str, dst_id: str, link_type: str) -> bool:
    return EntityLink.query.filter(
        or_(
            (EntityLink.src_id == src_id) & (EntityLink.dst_id == dst_id),
            (EntityLink.src_id == dst_id) & (EntityLink.dst_id == src_id),
        ),
        EntityLink.link_type == link_type,
    ).first() is not None


def _proposal_candidate_id(raw: dict) -> str | None:
    return (
        raw.get("dst_id")
        or raw.get("candidate_id")
        or raw.get("other_entity_id")
        or raw.get("entity_id")
        or raw.get("target_id")
    )


def _normalize_proposal(entity: Entity, raw: dict, index: int) -> dict | None:
    candidate_id = _proposal_candidate_id(raw)
    if not candidate_id:
        return None

    link_type = raw.get("link_type", "related")
    src_id = str(raw.get("src_id") or entity.id)
    dst_id = str(raw.get("dst_id") or candidate_id)

    if src_id == str(entity.id) and _link_exists(src_id, dst_id, link_type):
        return None

    other_id = dst_id if src_id == str(entity.id) else src_id
    other = db.session.get(Entity, other_id)
    if other is None:
        return None

    return {
        "id": str(raw.get("id") or f"{entity.id}:{other_id}:{index}"),
        "src_id": src_id,
        "dst_id": dst_id,
        "link_type": link_type,
        "confidence": raw.get("confidence", 0.0),
        "reason": raw.get("reason"),
        "other_entity": {
            "id": str(other.id),
            "title": other.title,
            "type": other.type,
        },
    }


@api_v2_bp.route("/proposals", methods=["GET"])
def v2_list_link_proposals():
    entity_id = request.args.get("entity_id") or request.args.get("note_id")
    if not entity_id:
        return jsonify({"error": "entity_id is required"}), 400

    entity = db.session.get(Entity, entity_id)
    if entity is None:
        return jsonify({"error": "not found"}), 404

    limit = request.args.get("limit", DEFAULT_LIMIT, type=int)
    limit = max(1, min(limit, MAX_LIMIT))

    raw_proposals = (entity.ai_meta or {}).get("link_proposals") or []
    normalized = []
    for index, raw in enumerate(raw_proposals):
        if not isinstance(raw, dict):
            continue
        proposal = _normalize_proposal(entity, raw, index)
        if proposal is not None:
            normalized.append(proposal)
        if len(normalized) >= limit:
            break

    return jsonify({"data": normalized, "total": len(normalized), "entity_id": str(entity.id)})


@api_v2_bp.route("/links", methods=["POST"])
def v2_create_link():
    data = request.get_json(silent=True) or {}
    src_id = data.get("src_id")
    dst_id = data.get("dst_id")
    link_type = data.get("link_type", "related")

    if not src_id or not dst_id:
        return jsonify({"error": "src_id and dst_id are required"}), 400

    if db.session.get(Entity, src_id) is None or db.session.get(Entity, dst_id) is None:
        return jsonify({"error": "one or both entities not found"}), 404

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
    except ValueError as exc:
        if "already exists" in str(exc):
            existing = EntityLink.query.filter_by(
                src_id=src_id,
                dst_id=dst_id,
                link_type=link_type,
            ).first()
            if existing is not None:
                return jsonify({"data": existing.to_dict()}), 200
        return jsonify({"error": str(exc)}), 400


@api_bp.route("/proposals", methods=["GET"])
def list_link_proposals():
    """Legacy v1 endpoint retained for old review flows."""
    return jsonify({"data": []})


@api_bp.route("/proposals/generate", methods=["POST"])
def generate_link_proposals():
    """Legacy v1 endpoint retained for old review flows."""
    return jsonify({"error": "deprecated: use v2 link suggestion via ai_pipeline"}), 410


@api_bp.route("/proposals/<proposal_id>/accept", methods=["POST"])
def accept_link_proposal(proposal_id):
    """Legacy v1 endpoint retained for old review flows."""
    return jsonify({"error": "deprecated: use v2 link suggestion via ai_pipeline"}), 410


@api_bp.route("/proposals/<proposal_id>/dismiss", methods=["POST"])
def dismiss_link_proposal(proposal_id):
    """Legacy v1 endpoint retained for old review flows."""
    return jsonify({"error": "deprecated: use v2 link suggestion via ai_pipeline"}), 410


# ─── V2 Suggestions API (reads from AiSuggestion table + ai_meta) ────────────


@api_v2_bp.route("/suggestions", methods=["GET"])
def v2_list_suggestions():
    """List AI suggestions for review.

    Query params:
      entity_id: optional filter by source entity
      status: optional filter (pending, accepted, dismissed, edited, expired)
      limit: max results (default 100)
    """
    entity_id = request.args.get("entity_id")
    status = request.args.get("status")
    limit = request.args.get("limit", DEFAULT_LIMIT, type=int)
    limit = max(1, min(limit, MAX_LIMIT))

    query = AiSuggestion.query
    if entity_id:
        query = query.filter(AiSuggestion.source_entity_id == entity_id)
    if status:
        query = query.filter(AiSuggestion.status == status)

    suggestions = query.order_by(AiSuggestion.created_at.desc()).limit(limit).all()
    return jsonify({"data": [s.to_dict() for s in suggestions]})


@api_v2_bp.route("/suggestions/<suggestion_id>/accept", methods=["POST"])
def v2_accept_suggestion(suggestion_id):
    """Accept an AI suggestion and apply its operation."""
    suggestion = db.session.get(AiSuggestion, suggestion_id)
    if not suggestion:
        return jsonify({"error": "Suggestion not found"}), 404
    if suggestion.status != "pending":
        return jsonify({"error": f"Suggestion already {suggestion.status}"}), 400

    payload = suggestion.payload or {}
    try:
        if suggestion.suggestion_type == "link":
            link = svc_create_link(
                src_id=payload.get("src_id"),
                dst_id=payload.get("dst_id"),
                link_type=payload.get("link_type", "related"),
                source="ai",
                confidence=payload.get("confidence", suggestion.confidence),
                evidence=payload.get("evidence", suggestion.reason),
                actor="user",
            )
            suggestion.status = "accepted"
            suggestion.resolved_at = datetime.now(timezone.utc)
            db.session.commit()
            return jsonify({"data": {"link": link.to_dict(), "suggestion": suggestion.to_dict()}}), 200
        elif suggestion.suggestion_type == "create_task":
            from services.ai_operation_applier import _apply_create_task
            result = _apply_create_task(payload, payload.get("source_note_id"), "user")
            suggestion.status = "accepted"
            suggestion.resolved_at = datetime.now(timezone.utc)
            db.session.commit()
            return jsonify({"data": {"result": result, "suggestion": suggestion.to_dict()}}), 200
        else:
            suggestion.status = "accepted"
            suggestion.resolved_at = datetime.now(timezone.utc)
            db.session.commit()
            return jsonify({"data": {"suggestion": suggestion.to_dict()}}), 200
    except Exception as e:
        logger.exception("Failed to accept suggestion %s", suggestion_id)
        return jsonify({"error": str(e)}), 500


@api_v2_bp.route("/suggestions/<suggestion_id>/dismiss", methods=["POST"])
def v2_dismiss_suggestion(suggestion_id):
    """Dismiss an AI suggestion."""
    suggestion = db.session.get(AiSuggestion, suggestion_id)
    if not suggestion:
        return jsonify({"error": "Suggestion not found"}), 404
    if suggestion.status != "pending":
        return jsonify({"error": f"Suggestion already {suggestion.status}"}), 400

    suggestion.status = "dismissed"
    suggestion.resolved_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({"data": suggestion.to_dict()}), 200


@api_v2_bp.route("/suggestions/<suggestion_id>/edit", methods=["POST"])
def v2_edit_suggestion(suggestion_id):
    """Edit an AI suggestion (modify the payload before accepting)."""
    suggestion = db.session.get(AiSuggestion, suggestion_id)
    if not suggestion:
        return jsonify({"error": "Suggestion not found"}), 404
    if suggestion.status != "pending":
        return jsonify({"error": f"Suggestion already {suggestion.status}"}), 400

    data = request.get_json(silent=True) or {}
    if "payload" in data:
        suggestion.payload = data["payload"]
    if "operation_type" in data:
        suggestion.operation_type = data["operation_type"]

    suggestion.status = "edited"
    suggestion.resolved_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({"data": suggestion.to_dict()}), 200
