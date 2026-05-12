"""POST /api/v2/feedback, GET /api/v2/feedback/stats, GET /api/v2/feedback/corrections.

Wires services/feedback.py into the v2 API blueprint.
"""

import logging
from flask import request, jsonify
from api import api_v2_bp
from services.feedback import record_feedback, get_accuracy_stats, get_correction_signals

logger = logging.getLogger(__name__)


@api_v2_bp.route("/feedback", methods=["POST"])
def post_feedback():
    """Record user feedback on an AI classification."""
    data = request.get_json(silent=True) or {}

    entity_id = data.get("entity_id")
    verdict = data.get("verdict")
    reason = data.get("reason")

    if not entity_id:
        return jsonify({"error": "entity_id is required"}), 400
    if not verdict:
        return jsonify({"error": "verdict is required"}), 400

    try:
        feedback = record_feedback(entity_id=entity_id, verdict=verdict, reason=reason)
        return jsonify({
            "id": feedback.id,
            "entity_id": feedback.entity_id,
            "event_type": feedback.event_type,
            "verdict": feedback.new_value.get("verdict"),
            "reason": feedback.new_value.get("reason"),
            "original_confidence": feedback.new_value.get("original_confidence"),
            "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error("POST /feedback failed: %s", e)
        return jsonify({"error": "internal server error"}), 500


@api_v2_bp.route("/feedback/stats", methods=["GET"])
def get_feedback_stats():
    """Return accuracy breakdown from feedback history."""
    try:
        stats = get_accuracy_stats()
        return jsonify(stats), 200
    except Exception as e:
        logger.error("GET /feedback/stats failed: %s", e)
        return jsonify({"error": "internal server error"}), 500


@api_v2_bp.route("/feedback/corrections", methods=["GET"])
def get_feedback_corrections():
    """Return correction signals for improving future classifications."""
    verdict = request.args.get("verdict")
    para_bucket = request.args.get("para_bucket")
    limit = request.args.get("limit", 20, type=int)

    try:
        signals = get_correction_signals(
            verdict=verdict,
            para_bucket=para_bucket,
            limit=limit,
        )
        return jsonify({"signals": signals, "total": len(signals)}), 200
    except Exception as e:
        logger.error("GET /feedback/corrections failed: %s", e)
        return jsonify({"error": "internal server error"}), 500
