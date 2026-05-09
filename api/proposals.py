"""REST API for AI link proposals (persist → review → accept/dismiss)."""

from __future__ import annotations

import logging

from flask import jsonify, request

from api import api_bp
from extensions import db
from models import Link, LinkProposal, LinkProposalStatus
from services.link_proposer import propose_links
from sqlalchemy import or_

logger = logging.getLogger(__name__)

_LINK_TYPE = "related"


def _link_exists(src_id: str, dst_id: str) -> bool:
    q = Link.query.filter(
        or_(
            (Link.src_id == src_id) & (Link.dst_id == dst_id),
            (Link.src_id == dst_id) & (Link.dst_id == src_id),
        ),
        Link.link_type == _LINK_TYPE,
    ).first()
    return q is not None


@api_bp.route("/proposals", methods=["GET"])
def list_link_proposals():
    """List proposals; defaults to pending only."""
    status_arg = (request.args.get("status") or "pending").strip().lower()
    limit = request.args.get("limit", default=50, type=int)
    limit = max(1, min(limit, 500))

    q = LinkProposal.query
    if status_arg != "all":
        try:
            st = LinkProposalStatus(status_arg)
            q = q.filter(LinkProposal.status == st)
        except ValueError:
            return jsonify({"error": f"invalid status: {status_arg}"}), 400

    note_id = (request.args.get("note_id") or "").strip()
    if note_id:
        q = q.filter(
            or_(
                LinkProposal.src_id == note_id,
                LinkProposal.dst_id == note_id,
            )
        )

    rows = (
        q.order_by(LinkProposal.created_at.asc())
        .limit(limit)
        .all()
    )
    return jsonify({"data": [r.to_dict() for r in rows]})


@api_bp.route("/proposals/generate", methods=["POST"])
def generate_link_proposals():
    """Run proposal engine and persist new rows (skips existing pairs)."""
    data = request.get_json(silent=True) or {}

    raw_ids = data.get("note_ids")
    note_ids = None
    if raw_ids is not None:
        if not isinstance(raw_ids, list):
            return jsonify({"error": "note_ids must be a list"}), 400
        note_ids = [str(x) for x in raw_ids]

    try:
        proposals_in = propose_links(
            note_ids,
            max_notes=int(data.get("max_notes", 500)),
            min_confidence=float(data.get("min_confidence", 0.38)),
            temporal_window_days=int(data.get("temporal_window_days", 14)),
            semantic_min_similarity=float(data.get("semantic_min_similarity", 0.72)),
            semantic_neighbors=int(data.get("semantic_neighbors", 14)),
            max_proposals=int(data.get("max_proposals", 400)),
        )
    except Exception as e:
        logger.exception("propose_links failed")
        return jsonify({"error": str(e)}), 500

    created = 0
    for p in proposals_in:
        src_id = p["from_note_id"]
        dst_id = p["to_note_id"]
        exists = LinkProposal.query.filter_by(src_id=src_id, dst_id=dst_id).first()
        if exists:
            continue
        row = LinkProposal(
            src_id=src_id,
            dst_id=dst_id,
            confidence=p["confidence"],
            reason=p.get("reason"),
            status=LinkProposalStatus.PENDING,
        )
        db.session.add(row)
        created += 1

    db.session.commit()
    return jsonify({"data": {"created": created}})


@api_bp.route("/proposals/<proposal_id>/accept", methods=["POST"])
def accept_link_proposal(proposal_id):
    proposal = db.session.get(LinkProposal, proposal_id)
    if not proposal:
        return jsonify({"error": "not found"}), 404
    if proposal.status != LinkProposalStatus.PENDING:
        return jsonify({"error": "proposal is not pending"}), 400

    link_payload = None
    if not _link_exists(proposal.src_id, proposal.dst_id):
        link = Link(
            src_id=proposal.src_id,
            dst_id=proposal.dst_id,
            link_type=_LINK_TYPE,
            weight=proposal.confidence,
            source="llm",
        )
        db.session.add(link)
        db.session.flush()
        link_payload = link.to_dict()
    else:
        existing = (
            Link.query.filter(
                or_(
                    (Link.src_id == proposal.src_id) & (Link.dst_id == proposal.dst_id),
                    (Link.src_id == proposal.dst_id) & (Link.dst_id == proposal.src_id),
                ),
                Link.link_type == _LINK_TYPE,
            )
            .first()
        )
        if existing:
            link_payload = existing.to_dict()

    proposal.status = LinkProposalStatus.ACCEPTED
    db.session.commit()
    return jsonify({"data": {"proposal": proposal.to_dict(), "link": link_payload}})


@api_bp.route("/proposals/<proposal_id>/dismiss", methods=["POST"])
def dismiss_link_proposal(proposal_id):
    proposal = db.session.get(LinkProposal, proposal_id)
    if not proposal:
        return jsonify({"error": "not found"}), 404
    if proposal.status != LinkProposalStatus.PENDING:
        return jsonify({"error": "proposal is not pending"}), 400

    proposal.status = LinkProposalStatus.DISMISSED
    db.session.commit()
    return jsonify({"data": proposal.to_dict()})

