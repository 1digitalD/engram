"""Knowledge-base health metrics (aggregates from the DB)."""

from datetime import datetime, timedelta

from flask import jsonify
from sqlalchemy import func, or_, select

from api import api_bp
from extensions import db
from models import (
    BucketType,
    Link,
    LinkProposal,
    LinkProposalStatus,
    Note,
    Project,
    note_projects,
    note_tags,
)


def _safe_ratio(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return float(num) / float(den)


@api_bp.route("/metrics/health", methods=["GET"])
def metrics_health():
    """
    Snapshot of knowledge graph / inbox health.
    - orphan_rate: orphans / total_notes (orphan = not archived, not INBOX, no links,
      no project_id, no note_projects rows, no area).
    - avg_links_per_note: mean undirected degree (2 * |links| / |notes|).
    - archive_ratio: notes marked archived or in ARCHIVES bucket / total_notes.
    - tag_coverage: share of notes with at least one tag.
    - stale_projects: active projects with modified_at older than 30 days.
    - weekly_capture_rate: notes created in the rolling last 7 days (notes/week activity).
    - weekly_capture_counts: four ints, notes per week in oldest→newest rolling windows
      (same span as weekly_capture_rate for the last element).
    """
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    stale_cutoff = now - timedelta(days=30)

    total_notes = int(db.session.scalar(select(func.count(Note.id))) or 0)

    inbox_count = int(
        db.session.scalar(
            select(func.count(Note.id)).where(Note.bucket == BucketType.INBOX)
        )
        or 0
    )

    total_links = int(db.session.scalar(select(func.count(Link.id))) or 0)
    avg_links = (2.0 * total_links) / total_notes if total_notes else 0.0

    link_union = (
        select(Link.src_id.label("endpoint_id"))
        .union_all(select(Link.dst_id.label("endpoint_id")))
        .subquery()
    )
    linked_note_ids = select(link_union.c.endpoint_id)
    m2m_project_ids = select(note_projects.c.note_id)

    orphan_count = int(
        db.session.scalar(
            select(func.count(Note.id)).where(
                Note.is_archived.is_(False),
                Note.bucket != BucketType.INBOX,
                Note.project_id.is_(None),
                Note.area_id.is_(None),
                Note.id.not_in(m2m_project_ids),
                Note.id.not_in(linked_note_ids),
            )
        )
        or 0
    )
    orphan_rate = _safe_ratio(orphan_count, total_notes)

    archived_notes = int(
        db.session.scalar(
            select(func.count(Note.id)).where(
                or_(Note.is_archived.is_(True), Note.bucket == BucketType.ARCHIVES)
            )
        )
        or 0
    )
    archive_ratio = _safe_ratio(archived_notes, total_notes)

    notes_tagged = int(
        db.session.scalar(select(func.count(func.distinct(note_tags.c.note_id))))
        or 0
    )
    tag_coverage = _safe_ratio(notes_tagged, total_notes)

    active_projects = int(
        db.session.scalar(
            select(func.count(Project.id)).where(Project.is_archived.is_(False))
        )
        or 0
    )

    stale_projects = int(
        db.session.scalar(
            select(func.count(Project.id)).where(
                Project.is_archived.is_(False),
                Project.modified_at < stale_cutoff,
            )
        )
        or 0
    )

    weekly_capture_rate = int(
        db.session.scalar(
            select(func.count(Note.id)).where(Note.created_at >= week_ago)
        )
        or 0
    )

    # Oldest → newest week (4 rolling 7-day windows) for sparkline / mini bar chart
    weekly_capture_counts = []
    for start_days in (28, 21, 14, 7):
        win_start = now - timedelta(days=start_days)
        win_end = now - timedelta(days=start_days - 7)
        cnt = int(
            db.session.scalar(
                select(func.count(Note.id)).where(
                    Note.created_at >= win_start,
                    Note.created_at < win_end,
                )
            )
            or 0
        )
        weekly_capture_counts.append(cnt)

    link_proposals_pending = int(
        db.session.scalar(
            select(func.count(LinkProposal.id)).where(
                LinkProposal.status == LinkProposalStatus.PENDING
            )
        )
        or 0
    )

    return jsonify(
        {
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
            "link_proposals_pending": link_proposals_pending,
        }
    )
