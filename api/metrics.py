"""Knowledge-base health metrics (aggregates from the DB) — v2 rewrite.

Rewritten to use Entity model instead of v1 Note/Project/Link models.
"""

from datetime import datetime, timedelta

from flask import jsonify, request
from sqlalchemy import func, or_, select, text

from api import api_bp
from extensions import db
from models import Entity, EntityLink
from services.health_snapshot import (
    SYSTEM_HEALTH_ANCHOR_NOTE_ID,
    health_history_series,
    upsert_weekly_system_health_snapshot,
)


def _safe_ratio(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return float(num) / float(den)


@api_bp.route("/metrics/health", methods=["GET"])
def metrics_health():
    """
    Snapshot of knowledge graph / inbox health — v2 version using Entity model.
    """
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    stale_cutoff = now - timedelta(days=30)

    total_notes = int(
        db.session.scalar(
            select(func.count(Entity.id)).where(
                Entity.type == "note",
                Entity.id != SYSTEM_HEALTH_ANCHOR_NOTE_ID,
            )
        )
        or 0
    )

    inbox_count = int(
        db.session.scalar(
            select(func.count(Entity.id)).where(
                Entity.type == "note",
                Entity.properties["bucket"].as_string() == "INBOX",
                Entity.id != SYSTEM_HEALTH_ANCHOR_NOTE_ID,
            )
        )
        or 0
    )

    total_links = int(db.session.scalar(select(func.count(EntityLink.id))) or 0)
    avg_links = (2.0 * total_links) / total_notes if total_notes else 0.0

    # Orphan: not archived, not INBOX, no links, no project association
    linked_entity_ids = (
        select(EntityLink.src_id.label("endpoint_id"))
        .union_all(select(EntityLink.dst_id.label("endpoint_id")))
        .subquery()
    )

    orphan_count = int(
        db.session.scalar(
            select(func.count(Entity.id)).where(
                Entity.type == "note",
                Entity.lifecycle == "active",
                Entity.properties["bucket"].as_string() != "INBOX",
                Entity.id != SYSTEM_HEALTH_ANCHOR_NOTE_ID,
                Entity.id.not_in(select(linked_entity_ids.c.endpoint_id)),
            )
        )
        or 0
    )
    orphan_rate = _safe_ratio(orphan_count, total_notes)

    archived_notes = int(
        db.session.scalar(
            select(func.count(Entity.id)).where(
                Entity.type == "note",
                Entity.lifecycle == "archived",
                Entity.id != SYSTEM_HEALTH_ANCHOR_NOTE_ID,
            )
        )
        or 0
    )
    archive_ratio = _safe_ratio(archived_notes, total_notes)

    # Tag coverage: notes with at least one EntityTag
    from models import EntityTag
    notes_tagged = int(
        db.session.scalar(
            select(func.count(func.distinct(EntityTag.entity_id))).where(
                EntityTag.entity_id != SYSTEM_HEALTH_ANCHOR_NOTE_ID,
                EntityTag.entity_id.in_(
                    select(Entity.id).where(Entity.type == "note")
                ),
            )
        )
        or 0
    )
    tag_coverage = _safe_ratio(notes_tagged, total_notes)

    active_projects = int(
        db.session.scalar(
            select(func.count(Entity.id)).where(
                Entity.type == "project",
                Entity.lifecycle == "active",
            )
        )
        or 0
    )

    stale_projects = int(
        db.session.scalar(
            select(func.count(Entity.id)).where(
                Entity.type == "project",
                Entity.lifecycle == "active",
                Entity.updated_at < stale_cutoff,
            )
        )
        or 0
    )

    weekly_capture_rate = int(
        db.session.scalar(
            select(func.count(Entity.id)).where(
                Entity.type == "note",
                Entity.created_at >= week_ago,
                Entity.id != SYSTEM_HEALTH_ANCHOR_NOTE_ID,
            )
        )
        or 0
    )

    # Oldest → newest week (4 rolling 7-day windows)
    weekly_capture_counts = []
    for start_days in (28, 21, 14, 7):
        win_start = now - timedelta(days=start_days)
        win_end = now - timedelta(days=start_days - 7)
        cnt = int(
            db.session.scalar(
                select(func.count(Entity.id)).where(
                    Entity.type == "note",
                    Entity.created_at >= win_start,
                    Entity.created_at < win_end,
                    Entity.id != SYSTEM_HEALTH_ANCHOR_NOTE_ID,
                )
            )
            or 0
        )
        weekly_capture_counts.append(cnt)

    payload = {
        "total_notes": total_notes,
        "orphan_rate": orphan_rate,
        "avg_links_per_note": avg_links,
        "inbox_count": inbox_count,
        "archive_ratio": archive_ratio,
        "tag_coverage": tag_coverage,
        "active_projects": active_projects,
        "stale_projects": stale_projects,
        "weekly_capture_rate": weekly_capture_rate,
        "weekly_capture_counts": weekly_capture_counts,
    }

    upsert_weekly_system_health_snapshot(
        orphan_rate=orphan_rate,
        weekly_capture_rate=weekly_capture_rate,
        total_notes=total_notes,
    )

    return jsonify(payload)


@api_bp.route("/metrics/health/history", methods=["GET"])
def metrics_health_history():
    """Last N UTC weeks of stored health snapshots."""
    raw = request.args.get("weeks", "12")
    try:
        weeks = int(raw)
    except ValueError:
        weeks = 12
    return jsonify({"data": health_history_series(weeks)})
