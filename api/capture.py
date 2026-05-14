"""Capture endpoint — the primary AI-powered capture interface.

POST /api/v2/capture

Takes natural-language input, saves as a source note, runs the AI
interpretation pipeline, and returns a structured change plan.
"""

from flask import request, jsonify
from api import api_v2_bp
import logging

logger = logging.getLogger(__name__)


@api_v2_bp.route("/capture", methods=["POST"])
def capture():
    """
    Primary capture endpoint.

    Body (JSON):
      content  str  - raw natural-language text (required)
      mode     str  - auto | note | task | resource | person (default: auto)
      source   str  - origin identifier (default: quick_capture)

    Returns:
      source_note     dict   - the created source note
      applied_changes list   - changes that were auto-applied
      suggestions     list   - changes needing review
      warnings        list   - any warnings
    """
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    mode = (data.get("mode") or "auto").strip().lower()
    source = data.get("source", "quick_capture")

    if not content:
        return jsonify({"error": "content is required"}), 400

    try:
        from services.capture_service import process_capture
        result = process_capture(content=content, mode=mode, source=source)
        return jsonify(result), 201
    except Exception as e:
        logger.exception("Capture failed: %s", e)
        return jsonify({"error": str(e)}), 500
