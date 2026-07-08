"""Engram v4 commitment affordances (nudge drafting)."""

from flask import jsonify

from api import api_v4_bp
from api.v4._shared import _error
from services import v4_nudge_draft as nudge_service


@api_v4_bp.route("/commitments/<commitment_id>/nudge-draft", methods=["POST"])
def nudge_draft(commitment_id):
    try:
        payload = nudge_service.draft_nudge(commitment_id)
    except LookupError as exc:
        return _error(str(exc), 404)
    return jsonify({"data": payload})
