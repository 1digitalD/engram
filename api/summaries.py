from datetime import datetime
from flask import request, jsonify
from api import api_bp
from extensions import db
from models import WeeklySummary, Note, Project, Area
from openai import OpenAI
import os
import logging

logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@api_bp.route("/summaries", methods=["GET"])
def list_summaries():
    entity_type = request.args.get("entity_type")
    entity_id = request.args.get("entity_id")

    q = WeeklySummary.query
    if entity_type:
        q = q.filter(WeeklySummary.entity_type == entity_type)
    if entity_id:
        q = q.filter(WeeklySummary.entity_id == entity_id)

    summaries = q.order_by(WeeklySummary.week_year.desc(), WeeklySummary.week_number.desc()).all()
    return jsonify({"data": [s.to_dict() for s in summaries]})


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

    # Get the entity
    if entity_type == "project":
        entity = db.session.get(Project, entity_id)
    elif entity_type == "area":
        entity = db.session.get(Area, entity_id)
    else:
        return jsonify({"error": "entity_type must be 'project' or 'area'"}), 400

    if not entity:
        return jsonify({"error": "entity not found"}), 404

    # Get notes for this entity in the current week
    now = datetime.utcnow()
    week_year = now.isocalendar()[0]
    week_number = now.isocalendar()[1]

    if entity_type == "project":
        notes = [n for n in entity.notes if n.created_at.isocalendar()[:2] == (week_year, week_number)]
    else:
        notes = [n for n in entity.notes if n.created_at.isocalendar()[:2] == (week_year, week_number)]

    note_texts = "\n".join([f"- {n.raw_text}" for n in notes])

    if not note_texts:
        note_texts = "(No notes captured this week)"

    # Build prompt
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
        summary_content = response.choices[0].message.content
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return jsonify({"error": f"OpenAI error: {e}"}), 502

    summary = WeeklySummary(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity.name,
        week_year=week_year,
        week_number=week_number,
        summary_content=summary_content,
        note_count=len(notes),
        is_manually_generated=True,
    )
    db.session.add(summary)
    db.session.commit()

    return jsonify({"data": summary.to_dict()}), 201


@api_bp.route("/summaries/<summary_id>", methods=["GET"])
def get_summary(summary_id):
    summary = db.session.get(WeeklySummary, summary_id)
    if not summary:
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": summary.to_dict()})
