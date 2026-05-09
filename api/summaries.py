from datetime import datetime, timedelta

from flask import request, jsonify
from openai import OpenAI
import os
import logging

from sqlalchemy import or_

from api import api_bp
from extensions import db
from models import Summary, SummaryGranularity, Note, Project, Area

logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _parse_granularity(raw):
    if raw is None:
        return None
    if isinstance(raw, SummaryGranularity):
        return raw
    try:
        return SummaryGranularity[str(raw).strip().upper()]
    except KeyError:
        return None


def _parse_dt(raw):
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return None


@api_bp.route("/summaries", methods=["GET"])
def list_summaries():
    note_id = request.args.get("note_id")
    granularity = _parse_granularity(request.args.get("granularity"))
    entity_type_filter = request.args.get("entity_type")

    q = Summary.query
    if note_id:
        q = q.filter(Summary.note_id == note_id)
    if granularity is not None:
        q = q.filter(Summary.granularity == granularity)
    if entity_type_filter:
        q = q.filter(Summary.entity_type == entity_type_filter)
    else:
        q = q.filter(or_(Summary.entity_type.is_(None), Summary.entity_type != "system"))

    summaries = q.order_by(Summary.generated_at.desc()).all()
    return jsonify({"data": [s.to_dict() for s in summaries]})


@api_bp.route("/summaries", methods=["POST"])
def create_summary():
    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    note_id = data.get("note_id")
    summary_text = data.get("summary_text")
    if not note_id or summary_text is None:
        return jsonify({"error": "note_id and summary_text required"}), 400

    note = db.session.get(Note, note_id)
    if not note:
        return jsonify({"error": "note not found"}), 404

    gran = _parse_granularity(data.get("granularity")) or SummaryGranularity.WEEKLY
    generated_at = _parse_dt(data.get("generated_at")) or datetime.utcnow()

    summary = Summary(
        note_id=note_id,
        summary_text=summary_text,
        generated_at=generated_at,
        summary_type=data.get("summary_type"),
        granularity=gran,
        date_from=_parse_dt(data.get("date_from")),
        date_to=_parse_dt(data.get("date_to")),
        key_themes=data.get("key_themes"),
        action_items=data.get("action_items"),
        entity_type=data.get("entity_type"),
    )
    db.session.add(summary)
    db.session.commit()
    return jsonify({"data": summary.to_dict()}), 201


@api_bp.route("/summaries/generate", methods=["POST"])
def generate_summary():
    """Generate a weekly summary for a project or area."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    entity_type = data.get("entity_type")  # 'project' or 'area'
    entity_id = data.get("entity_id")

    if not entity_type or not entity_id:
        return jsonify({"error": "entity_type and entity_id required"}), 400

    if entity_type == "project":
        entity = db.session.get(Project, entity_id)
    elif entity_type == "area":
        entity = db.session.get(Area, entity_id)
    else:
        return jsonify({"error": "entity_type must be 'project' or 'area'"}), 400

    if not entity:
        return jsonify({"error": "entity not found"}), 404

    now = datetime.utcnow()
    monday = now - timedelta(days=now.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=7)

    if entity_type == "project":
        notes = (
            Note.query.filter(
                Note.project_id == entity_id,
                Note.created_at >= monday,
                Note.created_at < sunday,
            )
            .order_by(Note.created_at.asc())
            .all()
        )
    else:
        notes = (
            Note.query.filter(
                Note.area_id == entity_id,
                Note.created_at >= monday,
                Note.created_at < sunday,
            )
            .order_by(Note.created_at.asc())
            .all()
        )

    anchor_note_id = data.get("note_id")
    if anchor_note_id:
        anchor = db.session.get(Note, anchor_note_id)
        if not anchor:
            return jsonify({"error": "note_id not found"}), 404
    elif notes:
        anchor_note_id = notes[0].id
    else:
        return jsonify({"error": "no notes in range for this entity; pass note_id"}), 400

    note_texts = "\n".join([f"- {n.raw_text}" for n in notes]) if notes else "(No notes captured this week)"

    prompt = f"""You are generating a weekly summary for {entity_type}: {entity.name}.

Notes from this week:
{note_texts}

Write a concise 2-3 paragraph summary of what happened, what was worked on, and any notable outcomes or next steps. Be specific and reference the notes."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a weekly review assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.5,
        )
        summary_text = response.choices[0].message.content
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return jsonify({"error": f"OpenAI error: {e}"}), 502

    summary = Summary(
        note_id=anchor_note_id,
        summary_text=summary_text,
        generated_at=datetime.utcnow(),
        summary_type=f"{entity_type}_weekly",
        granularity=SummaryGranularity.WEEKLY,
        date_from=monday,
        date_to=sunday,
        key_themes=None,
        action_items=None,
    )
    db.session.add(summary)
    db.session.commit()

    return jsonify({"data": summary.to_dict()}), 201


@api_bp.route("/summaries/<summary_id>", methods=["GET"])
def get_summary(summary_id):
    summary = db.session.get(Summary, summary_id)
    if not summary:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": summary.to_dict()})


@api_bp.route("/summaries/<summary_id>", methods=["PATCH"])
def patch_summary(summary_id):
    summary = db.session.get(Summary, summary_id)
    if not summary:
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    if "summary_text" in data:
        summary.summary_text = data["summary_text"]
    if "summary_type" in data:
        summary.summary_type = data["summary_type"]
    if "granularity" in data:
        gran = _parse_granularity(data["granularity"])
        if gran is None:
            return jsonify({"error": "invalid granularity"}), 400
        summary.granularity = gran
    if "generated_at" in data:
        summary.generated_at = _parse_dt(data["generated_at"]) or summary.generated_at
    if "date_from" in data:
        summary.date_from = _parse_dt(data["date_from"])
    if "date_to" in data:
        summary.date_to = _parse_dt(data["date_to"])
    if "key_themes" in data:
        summary.key_themes = data["key_themes"]
    if "action_items" in data:
        summary.action_items = data["action_items"]
    if "note_id" in data:
        note = db.session.get(Note, data["note_id"])
        if not note:
            return jsonify({"error": "note not found"}), 404
        summary.note_id = data["note_id"]

    db.session.commit()
    return jsonify({"data": summary.to_dict()})


@api_bp.route("/summaries/<summary_id>", methods=["DELETE"])
def delete_summary(summary_id):
    summary = db.session.get(Summary, summary_id)
    if not summary:
        return jsonify({"error": "not found"}), 404
    db.session.delete(summary)
    db.session.commit()
    return jsonify({"ok": True})
