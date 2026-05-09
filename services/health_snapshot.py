"""Weekly system health snapshots stored as Summary rows (entity_type=system)."""

from __future__ import annotations

from datetime import datetime, timedelta

from extensions import db
from models import BucketType, Note, Summary, SummaryGranularity

# Stable anchor note for Summary rows that are not tied to user content.
SYSTEM_HEALTH_ANCHOR_NOTE_ID = "00000000-0000-4000-8000-000000000001"


def utc_week_bounds(dt: datetime | None = None) -> tuple[datetime, datetime]:
    """Monday 00:00 UTC → next Monday 00:00 UTC."""
    now = dt or datetime.utcnow()
    days_since_monday = now.weekday()
    week_start = (now - timedelta(days=days_since_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_end = week_start + timedelta(days=7)
    return week_start, week_end


def ensure_system_health_anchor_note() -> str:
    note = db.session.get(Note, SYSTEM_HEALTH_ANCHOR_NOTE_ID)
    if note:
        return note.id
    note = Note(
        id=SYSTEM_HEALTH_ANCHOR_NOTE_ID,
        raw_text="# Engram system anchor\n\nReserved note for automated health history summaries.",
        bucket=BucketType.ARCHIVES,
        is_archived=False,
    )
    anchor_ts = datetime(2000, 1, 1, 0, 0, 0)
    note.created_at = anchor_ts
    note.modified_at = anchor_ts
    db.session.add(note)
    db.session.commit()
    return note.id


def upsert_weekly_system_health_snapshot(
    *,
    orphan_rate: float,
    weekly_capture_rate: int,
    total_notes: int,
    generated_at: datetime | None = None,
) -> Summary | None:
    """
    Insert or update the UTC-week Summary for entity_type=system.
    Stores orphan_rate and capture_rate (same semantics as /metrics/health) in key_themes JSON.
    """
    gen = generated_at or datetime.utcnow()
    week_start, week_end = utc_week_bounds(gen)

    existing = (
        Summary.query.filter_by(
            entity_type="system",
            granularity=SummaryGranularity.WEEKLY,
            date_from=week_start,
            date_to=week_end,
        ).first()
    )
    anchor_id = ensure_system_health_anchor_note()

    payload = {
        "orphan_rate": float(orphan_rate),
        "capture_rate": int(weekly_capture_rate),
        "total_notes": int(total_notes),
    }
    summary_line = (
        f"Week of {week_start.date().isoformat()} UTC — "
        f"orphan_rate={payload['orphan_rate']:.4f}, "
        f"capture_rate={payload['capture_rate']} captures / 7d"
    )

    if existing:
        existing.summary_text = summary_line
        existing.generated_at = gen
        existing.key_themes = payload
        existing.note_id = anchor_id
        existing.summary_type = "weekly_health_snapshot"
        db.session.commit()
        return existing

    row = Summary(
        note_id=anchor_id,
        summary_text=summary_line,
        generated_at=gen,
        summary_type="weekly_health_snapshot",
        granularity=SummaryGranularity.WEEKLY,
        date_from=week_start,
        date_to=week_end,
        entity_type="system",
        key_themes=payload,
        action_items=None,
        area_id=None,
    )
    db.session.add(row)
    db.session.commit()
    return row


def health_history_series(weeks: int = 12) -> list[dict]:
    """
    Last ``weeks`` UTC weeks (oldest first). Rows without snapshots use null metrics.
    """
    weeks = max(1, min(int(weeks), 52))
    now = datetime.utcnow()
    cur_start, _ = utc_week_bounds(now)

    anchors = [cur_start - timedelta(weeks=w) for w in range(weeks - 1, -1, -1)]

    rows = (
        Summary.query.filter_by(
            entity_type="system",
            granularity=SummaryGranularity.WEEKLY,
        )
        .order_by(Summary.date_from.asc())
        .all()
    )
    by_start = {}
    for s in rows:
        if s.date_from:
            by_start[s.date_from.replace(microsecond=0)] = s

    out = []
    for ws in anchors:
        we = ws + timedelta(days=7)
        s = by_start.get(ws.replace(microsecond=0))
        if s and isinstance(s.key_themes, dict):
            kt = s.key_themes
            out.append(
                {
                    "week_start": ws.isoformat() + "Z",
                    "week_end": we.isoformat() + "Z",
                    "orphan_rate": kt.get("orphan_rate"),
                    "capture_rate": kt.get("capture_rate"),
                    "total_notes": kt.get("total_notes"),
                }
            )
        else:
            out.append(
                {
                    "week_start": ws.isoformat() + "Z",
                    "week_end": we.isoformat() + "Z",
                    "orphan_rate": None,
                    "capture_rate": None,
                    "total_notes": None,
                }
            )
    return out
