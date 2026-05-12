"""Weekly system health snapshots stored as Summary rows (entity_type=system) — DEPRECATED.

This module used v1 models (Note, Summary, BucketType). The v2 system
uses Entity(type='note') and EntityEvent for health tracking.
"""

from __future__ import annotations

from datetime import datetime, timedelta

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
    """DEPRECATED: v1 model removed. Returns anchor ID without creating Note."""
    return SYSTEM_HEALTH_ANCHOR_NOTE_ID


def upsert_weekly_system_health_snapshot(
    *,
    orphan_rate: float,
    weekly_capture_rate: int,
    total_notes: int,
    generated_at: datetime | None = None,
) -> dict | None:
    """
    DEPRECATED: v1 Summary model removed. Returns a dict representation
    instead of persisting a Summary row.
    """
    gen = generated_at or datetime.utcnow()
    week_start, week_end = utc_week_bounds(gen)

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

    return {
        "note_id": SYSTEM_HEALTH_ANCHOR_NOTE_ID,
        "summary_text": summary_line,
        "generated_at": gen,
        "summary_type": "weekly_health_snapshot",
        "date_from": week_start,
        "date_to": week_end,
        "entity_type": "system",
        "key_themes": payload,
    }


def health_history_series(weeks: int = 12) -> list[dict]:
    """
    DEPRECATED: v1 Summary model removed. Returns empty series.
    """
    weeks = max(1, min(int(weeks), 52))
    now = datetime.utcnow()
    cur_start, _ = utc_week_bounds(now)

    anchors = [cur_start - timedelta(weeks=w) for w in range(weeks - 1, -1, -1)]

    out = []
    for ws in anchors:
        we = ws + timedelta(days=7)
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
