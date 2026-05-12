"""REST API for AI link proposals (persist → review → accept/dismiss) — DEPRECATED.

This endpoint used the v1 LinkProposal model. The v2 approach creates
EntityLink records directly via link_service.create_link().
"""

from __future__ import annotations

import logging

from flask import jsonify, request

from api import api_bp
from extensions import db
from models import EntityLink
from services import link_service
from sqlalchemy import or_

logger = logging.getLogger(__name__)

_LINK_TYPE = "related"


def _link_exists(src_id: str, dst_id: str) -> bool:
    q = EntityLink.query.filter(
        or_(
            (EntityLink.src_id == src_id) & (EntityLink.dst_id == dst_id),
            (EntityLink.src_id == dst_id) & (EntityLink.dst_id == src_id),
        ),
        EntityLink.link_type == _LINK_TYPE,
    ).first()
    return q is not None


@api_bp.route("/proposals", methods=["GET"])
def list_link_proposals():
    """DEPRECATED: LinkProposal model removed. Returns empty list."""
    return jsonify({"data": []})


@api_bp.route("/proposals/generate", methods=["POST"])
def generate_link_proposals():
    """DEPRECATED: LinkProposal model removed. Returns 410 Gone."""
    return jsonify({"error": "deprecated: use v2 link suggestion via ai_pipeline"}), 410


@api_bp.route("/proposals/<proposal_id>/accept", methods=["POST"])
def accept_link_proposal(proposal_id):
    """DEPRECATED: LinkProposal model removed. Returns 410 Gone."""
    return jsonify({"error": "deprecated: use v2 link suggestion via ai_pipeline"}), 410


@api_bp.route("/proposals/<proposal_id>/dismiss", methods=["POST"])
def dismiss_link_proposal(proposal_id):
    """DEPRECATED: LinkProposal model removed. Returns 410 Gone."""
    return jsonify({"error": "deprecated: use v2 link suggestion via ai_pipeline"}), 410
