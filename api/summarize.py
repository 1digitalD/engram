"""On-demand progressive summarization for selected notes — DEPRECATED.

This endpoint used v1 models (Note, Summary). The v2 replacement uses
Entity(type='note') and EntityEvent for summarization tracking.
"""

from flask import jsonify, request

from api import api_bp


@api_bp.route("/summarize", methods=["POST"])
def summarize_notes_endpoint():
    """DEPRECATED: Use v2 summarization via Entity model."""
    return jsonify({"error": "deprecated: use v2 summarization"}), 410
