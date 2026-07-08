"""Follow-up marker CRUD, firing job, and prep payload helpers."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from extensions import db
from models import Entity, FollowupMarker, Job
from services.job_worker import register_handler

MARKER_KINDS = {"nudge", "discuss", "custom"}
FIREABLE_KINDS = {"nudge", "custom"}
DONE_TASK_STATUSES = {"done", "completed", "cancelled"}
MARKER_FIRING_JOB_TYPE = "fire_markers"
MARKER_FIRING_INTERVAL_HOURS = 24


def _ensure_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _start_of_day(now):
    now = _ensure_utc(now)
    return datetime.combine(now.date(), time.min, tzinfo=timezone.utc)


def _end_of_day(now):
    now = _ensure_utc(now)
    return datetime.combine(now.date(), time.max, tzinfo=timezone.utc)


def _entity_blocks_firing(entity):
    if entity is None:
        return True
    if entity.lifecycle != "active":
        return True
    if entity.type in {"task", "project"} and entity.status in DONE_TASK_STATUSES:
        return True
    return False


def _validate_marker_payload(data, *, partial=False):
    if not partial:
        kind = data.get("kind")
        entity_id = data.get("entity_id")
        if kind not in MARKER_KINDS:
            return f"kind must be one of: {', '.join(sorted(MARKER_KINDS))}"
        if not entity_id:
            return "entity_id is required"

    kind = data.get("kind")
    if kind is not None and kind not in MARKER_KINDS:
        return f"kind must be one of: {', '.join(sorted(MARKER_KINDS))}"

    if kind == "discuss" and not partial and not data.get("person_entity_id"):
        return "person_entity_id is required for discuss markers"

    if kind in FIREABLE_KINDS and not partial and not data.get("due_at"):
        return "due_at is required for nudge markers"

    return None


def create_marker(data):
    error = _validate_marker_payload(data)
    if error:
        raise ValueError(error)

    entity = db.session.get(Entity, data["entity_id"])
    if entity is None:
        raise LookupError("entity not found")

    person_entity_id = data.get("person_entity_id")
    if person_entity_id:
        person = db.session.get(Entity, person_entity_id)
        if person is None:
            raise LookupError("person entity not found")
        if person.type != "person":
            raise ValueError("person_entity_id must reference a person entity")

    due_at = _parse_due_at(data.get("due_at"))

    marker = FollowupMarker(
        entity_id=data["entity_id"],
        kind=data["kind"],
        due_at=due_at,
        person_entity_id=person_entity_id,
        note=data.get("note"),
    )
    db.session.add(marker)
    db.session.commit()
    return marker


def update_marker(marker_id, data):
    marker = db.session.get(FollowupMarker, marker_id)
    if marker is None:
        raise LookupError("marker not found")
    if marker.resolved_at is not None:
        raise ValueError("resolved markers cannot be updated")

    error = _validate_marker_payload(data, partial=True)
    if error:
        raise ValueError(error)

    if "kind" in data:
        marker.kind = data["kind"]
    if "due_at" in data:
        marker.due_at = _parse_due_at(data["due_at"])
    if "person_entity_id" in data:
        person_entity_id = data["person_entity_id"]
        if person_entity_id:
            person = db.session.get(Entity, person_entity_id)
            if person is None:
                raise LookupError("person entity not found")
            if person.type != "person":
                raise ValueError("person_entity_id must reference a person entity")
        marker.person_entity_id = person_entity_id
    if "note" in data:
        marker.note = data["note"]

    db.session.commit()
    return marker


def delete_marker(marker_id):
    marker = db.session.get(FollowupMarker, marker_id)
    if marker is None:
        raise LookupError("marker not found")
    db.session.delete(marker)
    db.session.commit()


def list_markers(*, entity_id=None):
    query = FollowupMarker.query
    if entity_id:
        query = query.filter(FollowupMarker.entity_id == entity_id)
    return query.order_by(FollowupMarker.created_at.desc()).all()


def get_marker(marker_id):
    return db.session.get(FollowupMarker, marker_id)


def resolve_markers_for_entity(entity, now=None):
    """Auto-resolve open markers when the host entity is archived or done."""
    now = now or datetime.now(timezone.utc)
    if not _entity_blocks_firing(entity):
        return 0

    markers = (
        FollowupMarker.query.filter(
            FollowupMarker.entity_id == entity.id,
            FollowupMarker.resolved_at.is_(None),
        )
        .all()
    )
    for marker in markers:
        marker.resolved_at = now
    if markers:
        db.session.commit()
    return len(markers)


def fire_due_markers(now=None):
    """Fire due nudge/custom markers once; auto-resolve markers on closed entities."""
    now = now or datetime.now(timezone.utc)
    fired = []
    resolved = 0

    pending = (
        FollowupMarker.query.filter(
            FollowupMarker.fired_at.is_(None),
            FollowupMarker.resolved_at.is_(None),
            FollowupMarker.kind.in_(tuple(FIREABLE_KINDS)),
            FollowupMarker.due_at.isnot(None),
            FollowupMarker.due_at <= now,
        )
        .order_by(FollowupMarker.due_at.asc(), FollowupMarker.created_at.asc())
        .all()
    )

    for marker in pending:
        entity = db.session.get(Entity, marker.entity_id)
        if _entity_blocks_firing(entity):
            marker.resolved_at = now
            resolved += 1
            continue
        marker.fired_at = now
        fired.append(marker)

    if fired or resolved:
        db.session.commit()
    return {"fired": fired, "resolved": resolved}


def fired_markers_for_today(now=None):
    """Markers that fired today for inclusion in the Today feed."""
    now = now or datetime.now(timezone.utc)
    start = _start_of_day(now)
    end = _end_of_day(now)
    return (
        FollowupMarker.query.filter(
            FollowupMarker.kind.in_(tuple(FIREABLE_KINDS)),
            FollowupMarker.fired_at.isnot(None),
            FollowupMarker.fired_at >= start,
            FollowupMarker.fired_at <= end,
        )
        .order_by(FollowupMarker.fired_at.asc(), FollowupMarker.created_at.asc())
        .all()
    )


def discuss_markers_for_person(person_entity_id):
    """Open discuss markers filed for a person (meeting prep payloads)."""
    return (
        FollowupMarker.query.filter(
            FollowupMarker.kind == "discuss",
            FollowupMarker.person_entity_id == person_entity_id,
            FollowupMarker.resolved_at.is_(None),
        )
        .order_by(FollowupMarker.created_at.asc())
        .all()
    )


def marker_to_today_item(marker):
    entity = db.session.get(Entity, marker.entity_id)
    item = marker.to_dict()
    if entity is not None:
        item["entity"] = {
            "id": entity.id,
            "type": entity.type,
            "title": entity.title,
            "status": entity.status,
            "lifecycle": entity.lifecycle,
        }
    return item


def prep_payload_for_person(person_entity_id):
    markers = discuss_markers_for_person(person_entity_id)
    return [marker_to_today_item(marker) for marker in markers]


def schedule_next_marker_firing(hours=MARKER_FIRING_INTERVAL_HOURS):
    existing = Job.query.filter_by(job_type=MARKER_FIRING_JOB_TYPE, status="pending").first()
    if existing is not None:
        return existing

    job = Job(
        job_type=MARKER_FIRING_JOB_TYPE,
        payload={"scheduled": True},
        run_after=datetime.now(timezone.utc) + timedelta(hours=hours),
    )
    db.session.add(job)
    db.session.commit()
    return job


@register_handler(MARKER_FIRING_JOB_TYPE)
def handle_marker_firing_job(payload):
    try:
        fire_due_markers()
    finally:
        schedule_next_marker_firing()


def ensure_marker_firing_scheduled(app):
    with app.app_context():
        existing = Job.query.filter_by(job_type=MARKER_FIRING_JOB_TYPE, status="pending").first()
        if existing is not None:
            return
        job = Job(
            job_type=MARKER_FIRING_JOB_TYPE,
            payload={"scheduled": True, "bootstrap": True},
            run_after=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db.session.add(job)
        db.session.commit()


def _parse_due_at(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_utc(value)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return _ensure_utc(datetime.fromisoformat(text))
    raise ValueError("due_at must be an ISO8601 datetime string")
