from datetime import datetime

from flask import jsonify, request

from api import api_bp
from extensions import db
from models import BucketType, Note


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
        Note.query.filter(
            Note.bucket == BucketType.INBOX,
            Note.raw_text.startswith(f"{DAILY_HEADING_PREFIX}{date_value}"),
        )
        .order_by(Note.created_at.asc())
        .first()
    )


def _get_or_create_daily_note(date_value):
    note = _find_daily_note(date_value)
    if note:
        return note, False

    note = Note(raw_text=_daily_template(date_value), bucket=BucketType.INBOX)
    db.session.add(note)
    db.session.commit()
    return note, True


def _append_to_notes_section(raw_text, content):
    notes_heading = "## Notes"
    notes_index = raw_text.find(notes_heading)
    block = content.strip()

    if notes_index == -1:
        base = raw_text.rstrip()
        if not base:
            return f"{notes_heading}\n\n{block}\n"
        return f"{base}\n\n{notes_heading}\n\n{block}\n"

    insert_start = notes_index + len(notes_heading)
    next_heading_index = raw_text.find("\n## ", insert_start)

    if next_heading_index == -1:
        before = raw_text.rstrip()
        return f"{before}\n\n{block}\n"

    before = raw_text[:next_heading_index].rstrip()
    after = raw_text[next_heading_index:].lstrip("\n")
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
    note.raw_text = _append_to_notes_section(note.raw_text, content)
    from services.extractor import extract_inline_tasks

    extract_inline_tasks(note.id, note.raw_text, note.project_id, note.area_id)
    db.session.commit()

    return jsonify({"data": note.to_dict()})
