"""On-demand progressive summarization for selected notes."""

from datetime import datetime

from flask import jsonify, request

from api import api_bp
from api.summaries import _parse_granularity
from extensions import db
from models import Note, Summary, SummaryGranularity
from services.summarizer import Summarizer


@api_bp.route("/summarize", methods=["POST"])
def summarize_notes_endpoint():
    """
    Body: { note_ids: list[str], granularity: str, entity_name: str }
    Loads notes, runs Summarizer, persists a Summary anchored on the first note_id.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    note_ids = data.get("note_ids")
    granularity_raw = data.get("granularity")
    entity_name = data.get("entity_name")

    if not isinstance(note_ids, list) or not note_ids:
        return jsonify({"error": "note_ids must be a non-empty list"}), 400
    if not entity_name or not isinstance(entity_name, str):
        return jsonify({"error": "entity_name is required"}), 400

    gran = _parse_granularity(granularity_raw) or SummaryGranularity.WEEKLY

    # Preserve request order for anchor note; fetch unique ids in that order.
    seen: set[str] = set()
    ordered_ids: list[str] = []
    for raw_id in note_ids:
        sid = str(raw_id)
        if sid not in seen:
            seen.add(sid)
            ordered_ids.append(sid)

    notes: list[Note] = []
    for nid in ordered_ids:
        note = db.session.get(Note, nid)
        if not note:
            return jsonify({"error": f"note not found: {nid}"}), 404
        notes.append(note)

    anchor_note_id = ordered_ids[0]
    times = [n.created_at or datetime.utcnow() for n in notes]
    date_from = min(times)
    date_to = max(times)

    summarizer = Summarizer()
    try:
        result = summarizer.summarize_notes(
            notes, granularity=gran.value, entity_name=entity_name.strip()
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": f"summarization failed: {e}"}), 502

    summary = Summary(
        note_id=anchor_note_id,
        summary_text=result.get("summary_text") or "",
        generated_at=datetime.utcnow(),
        summary_type="progressive_llm",
        granularity=gran,
        date_from=date_from,
        date_to=date_to,
        key_themes=result.get("key_themes"),
        action_items=result.get("action_items"),
    )
    db.session.add(summary)
    db.session.commit()

    payload = summary.to_dict()
    payload["meta"] = {
        "token_count": result.get("token_count"),
        "model_used": result.get("model_used"),
    }
    return jsonify({"data": payload}), 201
