"""Daily notes API — v2 Entity model.

Daily notes are Entity(type='note') records. Creation uses entity_service.
Content replaces raw_text. Inline task extraction removed (handled by AI pipeline).
"""
from datetime import datetime

from flask import jsonify, request

from api import api_bp
from extensions import db
from models import Entity
from services.entity_service import create_entity


DAILY_HEADING_PREFIX = "# Daily — "


def _validate_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _daily_template(date_value):
    return f"# Daily — {date_value}\n\n## Focus\n\n## Notes\n\n## Tasks\n"


def _find_daily_note(date_value):
    return (
        Entity.query.filter(
            Entity.type == "note",
            Entity.lifecycle == "active",
            Entity.content.startswith(f"{DAILY_HEADING_PREFIX}{date_value}"),
        )
        .order_by(Entity.created_at.asc())
        .first()
    )


def _get_or_create_daily_note(date_value):
    note = _find_daily_note(date_value)
    if note:
        return note, False

    note = create_entity(
        entity_type="note",
        title=f"Daily — {date_value}",
        content=_daily_template(date_value),
        source="daily",
        actor="user",
    )
    return note, True


def _append_to_notes_section(content, new_content):
    notes_heading = "## Notes"
    notes_index = content.find(notes_heading)
    block = new_content.strip()

    if notes_index == -1:
        base = content.rstrip()
        if not base:
            return f"{notes_heading}\n\n{block}\n"
        return f"{base}\n\n{notes_heading}\n\n{block}\n"

    insert_start = notes_index + len(notes_heading)
    next_heading_index = content.find("\n## ", insert_start)

    if next_heading_index == -1:
        before = content.rstrip()
        return f"{before}\n\n{block}\n"

    before = content[:next_heading_index].rstrip()
    after = content[next_heading_index:].lstrip("\n")
    return f"{before}\n\n{block}\n\n{after}"


@api_bp.route("/daily", methods=["GET"])
def get_daily_note():
    date_value = _validate_date(request.args.get("date"))
    if not date_value:
        return jsonify({"error": "valid date query parameter is required"}), 400

    note, _created = _get_or_create_daily_note(date_value)
    return jsonify({"data": note.to_dict()})


@api_bp.route("/daily/append", methods=["POST"])
def append_daily_note():
    data = request.get_json()
    if not data:
        return jsonify({"error": "no JSON body"}), 400

    date_value = _validate_date(data.get("date"))
    if not date_value:
        return jsonify({"error": "valid date is required"}), 400

    content = data.get("content")
    if not content or not content.strip():
        return jsonify({"error": "content is required"}), 400

    note, _created = _get_or_create_daily_note(date_value)
    note.content = _append_to_notes_section(note.content, content)
    db.session.commit()

    return jsonify({"data": note.to_dict()})
