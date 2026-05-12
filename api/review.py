"""Review-facing aggregates backed by DB queries."""

from datetime import datetime, timedelta, timezone

from flask import jsonify, request
from sqlalchemy import func, select

from api import api_bp
from extensions import db
from models import Entity, EntityLink


def _digest_since(days: int = 7) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


@api_bp.route("/review/weekly-digest", methods=["GET"])
def weekly_digest():
    """
    Rolling UTC window: last `days` days (default 7).
    - notes_captured: entities of type 'note' created in window
    - tasks_created: entities of type 'task' created in window
    - projects_completed: archived projects whose updated_at falls in window
    - connections_made: entity links created in window
    """
    raw_days = request.args.get("days")
    days = 7
    if raw_days is not None:
        try:
            days = max(1, min(366, int(raw_days)))
        except (TypeError, ValueError):
            days = 7

    since = _digest_since(days)
    now = datetime.now(timezone.utc)

    notes_count = db.session.scalar(
        select(func.count(Entity.id))
        .where(Entity.type == "note", Entity.created_at >= since)
    )
    tasks_count = db.session.scalar(
        select(func.count(Entity.id))
        .where(Entity.type == "task", Entity.created_at >= since)
    )
    links_count = db.session.scalar(
        select(func.count(EntityLink.id))
        .where(EntityLink.created_at >= since)
    )
    projects_completed = db.session.scalar(
        select(func.count(Entity.id))
        .where(
            Entity.type == "project",
            Entity.lifecycle == "archived",
            Entity.updated_at >= since,
        )
    )

    return jsonify(
        {
            "days": days,
            "date_from": since.isoformat() + "Z",
            "date_to": now.isoformat() + "Z",
            "notes_captured": int(notes_count or 0),
            "tasks_created": int(tasks_count or 0),
            "projects_completed": int(projects_completed or 0),
            "connections_made": int(links_count or 0),
        }
    )
