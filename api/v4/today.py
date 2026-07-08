"""Engram v4 today API."""

from api import api_v4_bp
from api.v4._shared import *

@api_v4_bp.route("/today", methods=["GET"])
def today():
    return jsonify(_build_today_payload(datetime.now(timezone.utc)))


@api_v4_bp.route("/today/review", methods=["POST"])
def mark_today_reviewed():
    now = db.session.execute(text("SELECT now()")).scalar_one()
    start_of_today = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    last_reviewed_at = _set_app_setting("last_reviewed_at", now.isoformat())
    return jsonify({
        "last_reviewed_at": last_reviewed_at,
        "reviewed_today": _parse_datetime(last_reviewed_at) >= start_of_today,
    })


@api_v4_bp.route("/inbox", methods=["GET"])
def inbox():
    limit = max(1, min(request.args.get("limit", 30, type=int), 200))

    needs_review = (
        _needs_review_query()
        .order_by(Entity.updated_at.desc(), Entity.created_at.desc())
        .all()
    )
    needs_review_ids = {n.id for n in needs_review}

    recent = (
        _entity_query()
        .filter(
            Entity.type == "note",
            Entity.lifecycle == "active",
            ~Entity.id.in_(needs_review_ids) if needs_review_ids else Entity.id.is_not(None),
        )
        .order_by(Entity.created_at.desc())
        .all()
    )

    # Single query: pending-suggestion counts per source note in this page.
    note_ids = [n.id for n in needs_review] + [n.id for n in recent]
    pending_counts = {}
    if note_ids:
        rows = (
            db.session.query(AiSuggestion.source_entity_id, func.count(AiSuggestion.id))
            .filter(AiSuggestion.source_entity_id.in_(note_ids), AiSuggestion.status == "pending")
            .group_by(AiSuggestion.source_entity_id)
            .all()
        )
        pending_counts = {sid: cnt for sid, cnt in rows}

    needs_review = _sort_inbox_notes(needs_review, pending_counts, mode="needs_review")[:limit]
    recent = _sort_inbox_notes(recent, pending_counts, mode="recent")[:limit]

    def annotate(note):
        d = note.to_dict()
        d["pending_suggestion_count"] = pending_counts.get(note.id, 0)
        d["attention"] = attention_for_entity(
            note,
            pending_suggestion_count=d["pending_suggestion_count"],
            context=["needs_review"] if note.id in needs_review_ids else None,
        )
        return d

    return jsonify({
        "needs_review": [annotate(n) for n in needs_review],
        "recent": [annotate(n) for n in recent],
    })


