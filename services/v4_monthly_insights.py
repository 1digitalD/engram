"""Monthly portfolio health briefing."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import aliased
from sqlalchemy.orm.attributes import flag_modified

from extensions import db
from models import AppSetting, Entity, EntityLink, _iso
from services.v4_workboard import OPEN_TASK_STATUSES, get_workboard

MONTHLY_HEALTH_CACHE_KEY = "monthly_health_briefing"
EMPTY_MONTHLY_HEALTH_MESSAGE = "Nothing notable surfaced this month."
QUIET_PERSON_DAYS = 21


def get_monthly_health(*, force: bool = False, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")
    setting = db.session.get(AppSetting, MONTHLY_HEALTH_CACHE_KEY)

    if not force and setting is not None:
        cached = setting.value or {}
        if cached.get("month_key") == month_key and cached.get("briefing"):
            return cached["briefing"], True

    briefing = build_monthly_health(now=now)
    payload = {"month_key": month_key, "generated_at": _iso(now), "briefing": briefing}

    if setting is None:
        setting = AppSetting(key=MONTHLY_HEALTH_CACHE_KEY, value=payload)
        db.session.add(setting)
    else:
        setting.value = payload
        flag_modified(setting, "value")

    db.session.commit()
    return briefing, False


def build_monthly_health(*, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    sections = [
        collect_quiet_people(now=now),
        collect_at_risk_spaces(now=now),
        collect_idle_themes(now=now),
        collect_unowned_work(),
    ]
    sections = [section for section in sections if section]
    return {
        "title": f"Portfolio health - {now.strftime('%B %Y')}",
        "month": now.strftime("%Y-%m"),
        "generated_at": _iso(now),
        "message": "" if sections else EMPTY_MONTHLY_HEALTH_MESSAGE,
        "sections": sections,
    }


def collect_quiet_people(*, now: datetime):
    person = aliased(Entity)
    task = aliased(Entity)
    rows = (
        db.session.query(person, task)
        .join(EntityLink, EntityLink.target_entity_id == person.id)
        .join(task, task.id == EntityLink.source_entity_id)
        .filter(
            person.type == "person",
            person.lifecycle == "active",
            EntityLink.relationship_type == "assigned_to",
            task.type == "task",
            task.lifecycle == "active",
            task.status.in_(OPEN_TASK_STATUSES),
        )
        .order_by(person.title.asc(), task.updated_at.desc())
        .all()
    )

    people = {}
    assigned_person_ids = set()
    for person_entity, task_entity in rows:
        assigned_person_ids.add(person_entity.id)
        current = people.setdefault(
            person_entity.id,
            {
                "entity_id": person_entity.id,
                "title": person_entity.title,
                "last_activity_at": None,
                "task_id": task_entity.id,
            },
        )
        current["last_activity_at"] = _latest_timestamp(
            current["last_activity_at"],
            task_entity.updated_at,
            task_entity.created_at,
        )
        current["task_id"] = task_entity.id

    standalone_query = Entity.query.filter(
        Entity.type == "person",
        Entity.lifecycle == "active",
    )
    if assigned_person_ids:
        standalone_query = standalone_query.filter(Entity.id.notin_(assigned_person_ids))
    for person_entity in standalone_query.all():
        people[person_entity.id] = {
            "entity_id": person_entity.id,
            "title": person_entity.title,
            "last_activity_at": _latest_timestamp(
                person_entity.updated_at,
                person_entity.created_at,
            ),
            "task_id": None,
        }

    items = []
    for row in people.values():
        last_activity_at = row["last_activity_at"]
        if last_activity_at is None:
            continue
        quiet_days = max(0, (now - last_activity_at).days)
        if quiet_days < QUIET_PERSON_DAYS:
            continue
        receipts = [{"kind": "person", "entity_id": row["entity_id"], "field": "activity"}]
        if row["task_id"] is not None:
            receipts.append({"kind": "task", "entity_id": row["task_id"], "field": "updated_at"})
        items.append(
            {
                "entity_id": row["entity_id"],
                "title": row["title"],
                "summary": f"No activity on owned work in {quiet_days}d.",
                "receipts": receipts,
            }
        )

    items.sort(key=lambda item: item["title"].lower())
    return _section("quiet_people", "Quiet people", items)


def collect_at_risk_spaces(*, now: datetime):
    payload = get_workboard(group="space", now=now)
    items = []
    for group in payload["groups"]:
        detail = group.get("at_risk") or {}
        if not detail.get("flag"):
            continue
        items.append(
            {
                "entity_id": group.get("entity_id"),
                "title": group.get("label"),
                "summary": detail.get("reason") or "At risk.",
                "receipts": detail.get("receipts") or [],
            }
        )

    items.sort(key=lambda item: item["title"].lower())
    return _section("at_risk_spaces", "At-risk Spaces", items)


def collect_idle_themes(*, now: datetime):
    themes = (
        Entity.query.filter(
            Entity.type == "theme",
            Entity.lifecycle == "active",
            Entity.due_at.isnot(None),
            Entity.due_at < now,
        )
        .order_by(Entity.due_at.asc(), Entity.title.asc())
        .all()
    )

    items = []
    for theme in themes:
        last_activity_at = _latest_timestamp(theme.updated_at, theme.created_at)
        due_at = _ensure_utc(theme.due_at)
        if last_activity_at is None or due_at is None or last_activity_at > due_at:
            continue
        days_past_horizon = max(1, (now.date() - due_at.date()).days)
        items.append(
            {
                "entity_id": theme.id,
                "title": theme.title,
                "summary": f"Horizon passed {days_past_horizon}d ago with no newer activity.",
                "receipts": [{"kind": "theme", "entity_id": theme.id, "field": "due_at"}],
            }
        )

    return _section("idle_themes", "Idle themes", items)


def collect_unowned_work():
    tasks = (
        Entity.query.filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
        )
        .order_by(Entity.due_at.asc().nullslast(), Entity.title.asc())
        .all()
    )
    task_ids = [task.id for task in tasks]
    owners_by_task = _owners_by_task(task_ids)
    spaces_by_task = _spaces_by_task(task_ids)

    items = []
    for task in tasks:
        owner = owners_by_task.get(task.id)
        space = spaces_by_task.get(task.id)
        reasons = []
        receipts = []

        if owner is None:
            reasons.append("no owner")
            receipts.append({"kind": "task", "entity_id": task.id, "field": "assigned_to"})

        if space is None or space.lifecycle != "active":
            reasons.append("not on an active Space")
            receipts.append({"kind": "task", "entity_id": task.id, "field": "parent"})

        if not reasons:
            continue

        items.append(
            {
                "entity_id": task.id,
                "title": task.title,
                "summary": "; ".join(reasons).capitalize() + ".",
                "receipts": receipts,
            }
        )

    return _section("unowned_work", "Unowned work", items)


def _section(key, title, items):
    if not items:
        return None
    return {"key": key, "title": title, "items": items}


def _owners_by_task(task_ids):
    if not task_ids:
        return {}
    person = aliased(Entity)
    rows = (
        db.session.query(EntityLink.source_entity_id, person)
        .join(person, person.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.source_entity_id.in_(task_ids),
            EntityLink.relationship_type == "assigned_to",
            person.type == "person",
            person.lifecycle == "active",
        )
        .order_by(EntityLink.created_at.asc())
        .all()
    )
    owners = {}
    for task_id, owner in rows:
        owners.setdefault(task_id, owner)
    return owners


def _spaces_by_task(task_ids):
    if not task_ids:
        return {}
    space = aliased(Entity)
    rows = (
        db.session.query(EntityLink.source_entity_id, space)
        .join(space, space.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.source_entity_id.in_(task_ids),
            EntityLink.relationship_type == "parent",
            space.type.in_(["project", "area"]),
            space.lifecycle != "deleted",
        )
        .order_by(EntityLink.created_at.asc())
        .all()
    )
    spaces = {}
    for task_id, parent in rows:
        spaces.setdefault(task_id, parent)
    return spaces


def _latest_timestamp(*values):
    normalized = [_ensure_utc(value) for value in values if value is not None]
    return max(normalized) if normalized else None


def _ensure_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
