"""Review-facing aggregates backed by DB queries."""

from datetime import datetime, timedelta

from flask import jsonify, request
from sqlalchemy import func, select

from api import api_bp
from extensions import db
from models import Link, Note, Project, Task


def _digest_since(days: int = 7) -> datetime:
    return datetime.utcnow() - timedelta(days=days)


@api_bp.route("/review/weekly-digest", methods=["GET"])
def weekly_digest():
    """
    Rolling UTC window: last `days` days (default 7).
    - notes_captured: notes created in window
    - tasks_created: tasks created in window
    - projects_completed: archived projects whose modified_at falls in window
    - connections_made: links created in window
    """
    raw_days = request.args.get("days")
    days = 7
    if raw_days is not None:
        try:
            days = max(1, min(366, int(raw_days)))
        except (TypeError, ValueError):
            days = 7

    since = _digest_since(days)
    now = datetime.utcnow()

    notes_q = db.session.scalar(select(func.count(Note.id)).where(Note.created_at >= since))
    tasks_q = db.session.scalar(select(func.count(Task.id)).where(Task.created_at >= since))
    links_q = db.session.scalar(select(func.count(Link.id)).where(Link.created_at >= since))
    projects_q = db.session.scalar(
        select(func.count(Project.id)).where(
            Project.is_archived.is_(True),
            Project.modified_at >= since,
        )
    )

    return jsonify(
        {
            "days": days,
            "date_from": since.isoformat() + "Z",
            "date_to": now.isoformat() + "Z",
            "notes_captured": int(notes_q or 0),
            "tasks_created": int(tasks_q or 0),
            "projects_completed": int(projects_q or 0),
            "connections_made": int(links_q or 0),
        }
    )
