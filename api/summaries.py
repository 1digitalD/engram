"""Summaries API — v2 rewrite using Entity model.

The v1 Summary model has been removed. Summaries are now stored as
Entity(type='summary') records with content holding the summary text.
"""
from datetime import datetime, timedelta

from flask import request, jsonify
from openai import OpenAI
import os
import logging

from sqlalchemy import or_

from api import api_bp
from extensions import db
from models import Entity, EntityLink

logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Granularity values are now stored as strings in Entity.properties
VALID_GRANULARITIES = {"DAILY", "WEEKLY", "MONTHLY"}


def _parse_granularity(raw):
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.strip().upper()
    if raw in VALID_GRANULARITIES:
        return raw
    return None


def _parse_dt(raw):
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return None


def _summary_to_dict(entity):
    """Convert Entity(type='summary') to summary response shape."""
    props = entity.properties or {}
    return {
        "id": entity.id,
        "summary_text": entity.content or "",
        "note_id": props.get("note_id"),
        "area_id": props.get("area_id"),
        "summary_type": props.get("summary_type"),
        "granularity": props.get("granularity", "WEEKLY"),
        "date_from": props.get("date_from"),
        "date_to": props.get("date_to"),
        "key_themes": props.get("key_themes"),
        "action_items": props.get("action_items"),
        "entity_type": props.get("entity_type"),
        "generated_at": props.get("generated_at"),
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
    }


@api_bp.route("/summaries", methods=["GET"])
def list_summaries():
    note_id = request.args.get("note_id")
    granularity = _parse_granularity(request.args.get("granularity"))
    entity_type_filter = request.args.get("entity_type")

    q = Entity.query.filter(Entity.type == "summary")
    if note_id:
        q = q.filter(Entity.properties["note_id"].as_string() == note_id)
    if granularity is not None:
        q = q.filter(Entity.properties["granularity"].as_string() == granularity)
    if entity_type_filter:
        q = q.filter(Entity.properties["entity_type"].as_string() == entity_type_filter)
    else:
        q = q.filter(
            or_(
                Entity.properties["entity_type"].as_string().is_(None),
                Entity.properties["entity_type"].as_string() != "system",
            )
        )

    summaries = q.order_by(Entity.created_at.desc()).all()
    return jsonify({"data": [_summary_to_dict(s) for s in summaries]})


@api_bp.route("/summaries", methods=["POST"])
def create_summary():
    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    note_id = data.get("note_id")
    summary_text = data.get("summary_text")
    if not note_id or summary_text is None:
        return jsonify({"error": "note_id and summary_text required"}), 400

    entity = db.session.get(Entity, note_id)
    if not entity:
        return jsonify({"error": "note not found"}), 404

    gran = _parse_granularity(data.get("granularity")) or "WEEKLY"
    generated_at = _parse_dt(data.get("generated_at")) or datetime.utcnow()

    summary_entity = Entity(
        type="summary",
        title=f"Summary ({gran})",
        content=summary_text,
        properties={
            "note_id": note_id,
            "area_id": data.get("area_id"),
            "summary_type": data.get("summary_type"),
            "granularity": gran,
            "date_from": _parse_dt(data.get("date_from")),
            "date_to": _parse_dt(data.get("date_to")),
            "key_themes": data.get("key_themes"),
            "action_items": data.get("action_items"),
            "entity_type": data.get("entity_type"),
            "generated_at": generated_at.isoformat() if generated_at else None,
        },
    )
    db.session.add(summary_entity)
    db.session.commit()
    return jsonify({"data": _summary_to_dict(summary_entity)}), 201


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

    if entity_type not in ("project", "area"):
        return jsonify({"error": "entity_type must be 'project' or 'area'"}), 400

    entity = Entity.query.filter(
        Entity.type == entity_type,
        Entity.id == entity_id,
    ).first()

    if not entity:
        return jsonify({"error": "entity not found"}), 404

    now = datetime.utcnow()
    monday = now - timedelta(days=now.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=7)

    # Find notes linked to this entity via EntityLink
    linked_note_ids = (
        db.session.query(EntityLink.src_id)
        .filter(
            EntityLink.dst_id == entity_id,
            EntityLink.link_type == entity_type,
        )
        .subquery()
    )
    notes = (
        Entity.query.filter(
            Entity.type == "note",
            Entity.created_at >= monday,
            Entity.created_at < sunday,
            Entity.id.in_(linked_note_ids),
        )
        .order_by(Entity.created_at.asc())
        .all()
    )

    anchor_note_id = data.get("note_id")
    if anchor_note_id:
        anchor = db.session.get(Entity, anchor_note_id)
        if not anchor:
            return jsonify({"error": "note_id not found"}), 404
    elif notes:
        anchor_note_id = notes[0].id
    else:
        return jsonify({"error": "no notes in range for this entity; pass note_id"}), 400

    note_texts = "\n".join([f"- {n.content}" for n in notes]) if notes else "(No notes captured this week)"

    prompt = f"""You are generating a weekly summary for {entity_type}: {entity.title}.

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

    summary_entity = Entity(
        type="summary",
        title=f"Weekly Summary ({entity_type})",
        content=summary_text,
        properties={
            "note_id": anchor_note_id,
            "summary_type": f"{entity_type}_weekly",
            "granularity": "WEEKLY",
            "date_from": monday.isoformat(),
            "date_to": sunday.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
        },
    )
    db.session.add(summary_entity)
    db.session.commit()

    return jsonify({"data": _summary_to_dict(summary_entity)}), 201


@api_bp.route("/summaries/<summary_id>", methods=["GET"])
def get_summary(summary_id):
    summary = db.session.get(Entity, summary_id)
    if not summary or summary.type != "summary":
        return jsonify({"error": "not found"}), 404
    return jsonify({"data": _summary_to_dict(summary)})


@api_bp.route("/summaries/<summary_id>", methods=["PATCH"])
def patch_summary(summary_id):
    summary = db.session.get(Entity, summary_id)
    if not summary or summary.type != "summary":
        return jsonify({"error": "not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    props = summary.properties or {}
    if "summary_text" in data:
        summary.content = data["summary_text"]
    if "summary_type" in data:
        props["summary_type"] = data["summary_type"]
    if "granularity" in data:
        gran = _parse_granularity(data["granularity"])
        if gran is None:
            return jsonify({"error": "invalid granularity"}), 400
        props["granularity"] = gran
    if "generated_at" in data:
        props["generated_at"] = (_parse_dt(data["generated_at"]) or summary.created_at).isoformat()
    if "date_from" in data:
        props["date_from"] = _parse_dt(data["date_from"])
    if "date_to" in data:
        props["date_to"] = _parse_dt(data["date_to"])
    if "key_themes" in data:
        props["key_themes"] = data["key_themes"]
    if "action_items" in data:
        props["action_items"] = data["action_items"]
    if "note_id" in data:
        entity = db.session.get(Entity, data["note_id"])
        if not entity:
            return jsonify({"error": "note not found"}), 404
        props["note_id"] = data["note_id"]

    summary.properties = props
    db.session.commit()
    return jsonify({"data": _summary_to_dict(summary)})


@api_bp.route("/summaries/<summary_id>", methods=["DELETE"])
def delete_summary(summary_id):
    from services.entity_service import delete_entity
    summary = db.session.get(Entity, summary_id)
    if not summary or summary.type != "summary":
        return jsonify({"error": "not found"}), 404
    delete_entity(summary_id, cascade_orphans=True)
    return jsonify({"ok": True})
