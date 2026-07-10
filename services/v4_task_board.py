"""Grouped task board payload for the v6 Tasks surface."""

from __future__ import annotations

from datetime import datetime, time, timezone

from extensions import db
from models import Entity, EntityLink, _iso

DEFAULT_STATUSES = ("open", "in_progress", "waiting", "blocked")
VALID_STATUSES = {"open", "in_progress", "waiting", "blocked", "done", "cancelled"}
VALID_SORT_FIELDS = {"created_at", "follow_up_at"}
NO_PROJECT_KEY = "__no_project__"


def get_task_board(
    *,
    status_filters=None,
    assignee=None,
    due_before=None,
    due_after=None,
    follow_up_before=None,
    follow_up_after=None,
    sort="created_at",
    order=None,
    now=None,
):
    statuses = _normalize_status_filters(status_filters)
    invalid_statuses = set(statuses) - VALID_STATUSES
    if invalid_statuses:
        raise ValueError(f"invalid status filter: {', '.join(sorted(invalid_statuses))}")

    if sort not in VALID_SORT_FIELDS:
        raise ValueError("sort must be one of: created_at, follow_up_at")

    now = now or datetime.now(timezone.utc)
    resolved_order = order or ("desc" if sort == "created_at" else "asc")
    if resolved_order not in {"asc", "desc"}:
        raise ValueError("order must be one of: asc, desc")

    base_query = Entity.query.filter(
        Entity.type == "task",
        Entity.lifecycle == "active",
    )
    base_query = _apply_date_filters(
        base_query,
        due_before=due_before,
        due_after=due_after,
        follow_up_before=follow_up_before,
        follow_up_after=follow_up_after,
        now=now,
    )

    candidate_tasks = base_query.all()
    if not candidate_tasks:
        return _empty_payload(statuses, assignee, sort, resolved_order)

    candidate_ids = [task.id for task in candidate_tasks]
    parents_by_task, owners_by_task = _task_relationship_maps(candidate_ids)
    candidate_tasks = _apply_assignee_filter(candidate_tasks, assignee, owners_by_task)

    status_counts = {status: 0 for status in VALID_STATUSES}
    eligible_tasks = []
    for task in candidate_tasks:
        parent = parents_by_task.get(task.id)
        if parent is not None and parent.lifecycle != "active":
            continue
        status_counts[task.status] = status_counts.get(task.status, 0) + 1
        if task.status in statuses:
            eligible_tasks.append(task)

    items = []
    for task in eligible_tasks:
        parent = parents_by_task.get(task.id)
        owner = owners_by_task.get(task.id)
        items.append(
            {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "due_at": _iso(task.due_at),
                "follow_up_at": _iso(task.follow_up_at),
                "created_at": _iso(task.created_at),
                "owner": _entity_ref(owner),
                "space": _parent_ref(parent),
            }
        )

    groups = _group_items(items, parents_by_task, sort=sort, order=resolved_order)
    return {
        "groups": groups,
        "meta": {
            "total": len(items),
            "counts": {"by_status": {key: status_counts.get(key, 0) for key in sorted(VALID_STATUSES)}},
            "filters": {
                "status": statuses,
                "assignee": assignee,
                "due_before": _iso(due_before) if due_before else None,
                "due_after": _iso(due_after) if due_after else None,
                "follow_up_before": _iso(follow_up_before) if follow_up_before else None,
                "follow_up_after": _iso(follow_up_after) if follow_up_after else None,
            },
            "sort": sort,
            "order": resolved_order,
        },
    }


def _apply_assignee_filter(tasks, assignee, owners_by_task):
    if assignee == "unassigned":
        return [task for task in tasks if owners_by_task.get(task.id) is None]
    if assignee:
        return [
            task
            for task in tasks
            if owners_by_task.get(task.id) and owners_by_task[task.id].id == assignee
        ]
    return tasks


def _normalize_status_filters(status_filters):
    if not status_filters:
        return list(DEFAULT_STATUSES)
    values = []
    for raw in status_filters:
        for part in str(raw).split(","):
            cleaned = part.strip()
            if cleaned:
                values.append(cleaned)
    return values or list(DEFAULT_STATUSES)


def _apply_date_filters(
    query,
    *,
    due_before,
    due_after,
    follow_up_before,
    follow_up_after,
    now,
):
    if due_before is not None:
        query = query.filter(Entity.due_at.isnot(None), Entity.due_at <= _end_of_day(due_before, now))
    if due_after is not None:
        query = query.filter(Entity.due_at.isnot(None), Entity.due_at >= _start_of_day(due_after, now))
    if follow_up_before is not None:
        query = query.filter(
            Entity.follow_up_at.isnot(None),
            Entity.follow_up_at <= _end_of_day(follow_up_before, now),
        )
    if follow_up_after is not None:
        query = query.filter(
            Entity.follow_up_at.isnot(None),
            Entity.follow_up_at >= _start_of_day(follow_up_after, now),
        )
    return query


def _task_relationship_maps(task_ids):
    if not task_ids:
        return {}, {}

    parent_rows = (
        db.session.query(EntityLink.source_entity_id, Entity)
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.source_entity_id.in_(task_ids),
            EntityLink.relationship_type == "parent",
            Entity.type.in_(("project", "area")),
            Entity.lifecycle != "deleted",
        )
        .order_by(EntityLink.created_at.asc())
        .all()
    )
    owners_by_task = {}
    owner_rows = (
        db.session.query(EntityLink.source_entity_id, Entity)
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.source_entity_id.in_(task_ids),
            EntityLink.relationship_type == "assigned_to",
            Entity.type == "person",
            Entity.lifecycle == "active",
        )
        .order_by(EntityLink.created_at.asc())
        .all()
    )
    for task_id, owner in owner_rows:
        owners_by_task.setdefault(task_id, owner)

    project_by_task = {}
    area_by_task = {}
    for task_id, parent in parent_rows:
        if parent.type == "project":
            project_by_task.setdefault(task_id, parent)
        elif parent.type == "area":
            area_by_task.setdefault(task_id, parent)

    parents_by_task = {}
    for task_id in task_ids:
        parents_by_task[task_id] = project_by_task.get(task_id) or area_by_task.get(task_id)
    return parents_by_task, owners_by_task


def _group_items(items, parents_by_task, *, sort, order):
    groups = {}
    for item in items:
        parent = parents_by_task.get(item["id"])
        if parent is None:
            key = NO_PROJECT_KEY
            label = "No project"
            kind = "none"
            entity_id = None
        else:
            key = parent.id
            label = parent.title or "Untitled"
            kind = parent.type
            entity_id = parent.id
        bucket = groups.setdefault(
            key,
            {
                "key": key,
                "label": label,
                "kind": kind,
                "entity_id": entity_id,
                "counts": {"total": 0},
                "items": [],
            },
        )
        bucket["items"].append(item)
        bucket["counts"]["total"] += 1

    for bucket in groups.values():
        bucket["items"].sort(key=lambda row: _sort_key(row, sort=sort, order=order))

    result = list(groups.values())
    result.sort(key=lambda row: (row["key"] == NO_PROJECT_KEY, row["label"].lower()))
    return result


def _sort_key(item, *, sort, order):
    parsed = _ensure_utc(item.get(sort))
    title = (item.get("title") or "").lower()
    if parsed is None:
        return (1, 0, title)
    timestamp = parsed.timestamp()
    if order == "desc":
        timestamp = -timestamp
    return (0, timestamp, title)


def _empty_payload(statuses, assignee, sort, order):
    return {
        "groups": [],
        "meta": {
            "total": 0,
            "counts": {"by_status": {key: 0 for key in sorted(VALID_STATUSES)}},
            "filters": {
                "status": statuses,
                "assignee": assignee,
                "due_before": None,
                "due_after": None,
                "follow_up_before": None,
                "follow_up_after": None,
            },
            "sort": sort,
            "order": order,
        },
    }


def _entity_ref(entity):
    if entity is None:
        return None
    return {"id": entity.id, "title": entity.title}


def _parent_ref(parent):
    if parent is None:
        return None
    return {
        "id": parent.id,
        "title": parent.title,
        "type": parent.type,
        "due_at": _iso(parent.due_at),
    }


def parse_date_param(value):
    if value is None or str(value).strip() == "":
        return None
    cleaned = str(value).strip()
    if len(cleaned) == 10:
        parsed = datetime.fromisoformat(cleaned)
        return parsed.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _ensure_utc(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _start_of_day(value, now):
    value = _ensure_utc(value)
    if value is None:
        return None
    return datetime.combine(value.date(), time.min, tzinfo=timezone.utc)


def _end_of_day(value, now):
    value = _ensure_utc(value)
    if value is None:
        return None
    return datetime.combine(value.date(), time.max, tzinfo=timezone.utc)
