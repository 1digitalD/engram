"""Derived v6 workboard states and grouped portfolio payload."""

from __future__ import annotations

from datetime import datetime, timezone

from extensions import db
from models import AppSetting, Entity, EntityEvent, EntityLink, _iso

DEFAULT_STALE_DAYS = 10
TASK_AT_RISK_DUE_DAYS = 7
SPACE_FINISH_LINE_DAYS = 21
SPACE_ACTIVITY_DAYS = 14
HYSTERESIS_DAYS = 2
OPEN_TASK_STATUSES = {"open", "in_progress", "waiting", "blocked"}
VALID_STATES = {
    "mine",
    "waiting_on",
    "overdue",
    "stale",
    "blocked",
    "at_risk",
}


def get_workboard(*, group="space", state_filters=None, now=None):
    if group not in {"space", "person"}:
        raise ValueError("group must be one of: person, space")

    filters = set(state_filters or [])
    invalid = filters - VALID_STATES
    if invalid:
        raise ValueError(f"invalid state filter: {', '.join(sorted(invalid))}")

    now = now or datetime.now(timezone.utc)
    operator_person_id, operator_configured = operator_identity()
    tasks = _open_workboard_tasks()
    if not tasks:
        return {
            "groups": [],
            "meta": {
                "group": group,
                "state_filters": sorted(filters),
                "operator_person_id": operator_person_id,
                "operator_configured": operator_configured,
                "counts": _empty_counts(),
                "total": 0,
            },
        }

    task_ids = [task.id for task in tasks]
    spaces_by_task, owners_by_task = _task_relationship_maps(task_ids)
    included_tasks = []
    grouped_spaces = {
        task_id: space
        for task_id, space in spaces_by_task.items()
        if space is None or space.lifecycle == "active"
    }
    tasks = [task for task in tasks if task.id in grouped_spaces]
    spaces = [space for space in grouped_spaces.values() if space is not None]
    unique_spaces = {space.id: space for space in spaces}
    stale_days_by_task = _staleness_days_for(tasks, now)
    space_activity_days = _project_staleness_days(list(unique_spaces.values()), now)
    blocked_by_task = _open_blockers_by_task([task.id for task in tasks])

    counts = _empty_counts()
    items = []
    for task in tasks:
        space = grouped_spaces.get(task.id)
        owner = owners_by_task.get(task.id)
        threshold_days = space_stale_threshold_days((space.properties or {}) if space else {})
        task_row = {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "due_at": _ensure_utc(task.due_at),
            "owner_id": owner.id if owner else None,
            "stale_days": stale_days_by_task.get(task.id, 0),
            "space_finish_line_at": _ensure_utc(space.due_at) if space else None,
            "space_id": space.id if space else None,
            "blocked_by_open_ids": [blocker["id"] for blocker in blocked_by_task.get(task.id, [])],
            "prior_at_risk": prior_at_risk_flag(task.properties or {}),
            "stale_threshold_days": threshold_days,
        }
        states = derive_task_states(
            task_row,
            operator_person_id=operator_person_id,
            operator_configured=operator_configured,
            now=now,
        )
        for state_name in VALID_STATES:
            if states[state_name]:
                counts[state_name] += 1
        counts["total"] += 1
        item = {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "due_at": _iso(task.due_at),
            "stale_days": stale_days_by_task.get(task.id, 0),
            "owner": _entity_ref(owner),
            "space": _space_ref(space, threshold_days),
            "blocked_by": blocked_by_task.get(task.id, []),
            "states": {state: states[state] for state in VALID_STATES},
            "at_risk": states["at_risk_detail"],
        }
        if filters and not all(item["states"].get(state) for state in filters):
            continue
        items.append(item)
        included_tasks.append((item, space, owner))

    groups = _group_items(
        included_tasks,
        group=group,
        now=now,
        space_activity_days=space_activity_days,
    )
    return {
        "groups": groups,
        "meta": {
            "group": group,
            "state_filters": sorted(filters),
            "operator_person_id": operator_person_id,
            "operator_configured": operator_configured,
            "counts": counts,
            "total": len(items),
        },
    }


def operator_identity():
    operator_person_id = _clean_text(_get_app_setting("operator_person_id"))
    configured = operator_person_id is not None
    if operator_person_id is None:
        operator_person_id = _clean_text(_get_app_setting("owner_person_id"))
    return operator_person_id, configured


def space_stale_threshold_days(properties):
    thresholds = (properties or {}).get("thresholds") or {}
    raw = thresholds.get("stale_days")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_STALE_DAYS
    return value if value > 0 else DEFAULT_STALE_DAYS


def derive_task_states(task, *, operator_person_id, operator_configured, now):
    owner_id = task.get("owner_id")
    due_at = _ensure_utc(task.get("due_at"))
    stale_days = int(task.get("stale_days") or 0)
    stale_threshold_days = int(task.get("stale_threshold_days") or DEFAULT_STALE_DAYS)
    blocked = bool(task.get("blocked_by_open_ids"))
    mine = True if not operator_configured else owner_id == operator_person_id
    waiting_on = False if not operator_configured else bool(owner_id and owner_id != operator_person_id)
    overdue = due_at is not None and due_at < now
    stale = stale_days >= stale_threshold_days
    at_risk = derive_task_at_risk(
        task,
        stale_days=stale_days,
        stale_threshold_days=stale_threshold_days,
        now=now,
    )
    return {
        "mine": mine,
        "waiting_on": waiting_on,
        "overdue": overdue,
        "stale": stale,
        "blocked": blocked,
        "at_risk": at_risk["flag"],
        "at_risk_detail": at_risk,
    }


def derive_task_at_risk(task, *, stale_days, stale_threshold_days, now):
    due_at = _ensure_utc(task.get("due_at"))
    finish_line_at = _ensure_utc(task.get("space_finish_line_at"))
    prior = bool(task.get("prior_at_risk"))

    current_stale = stale_days >= stale_threshold_days
    sticky_stale = stale_days >= max(0, stale_threshold_days - HYSTERESIS_DAYS)
    due_days = _days_until(due_at, now)
    finish_days = _days_until(finish_line_at, now)
    current_due = due_days is not None and due_days <= TASK_AT_RISK_DUE_DAYS
    sticky_due = due_days is not None and due_days <= TASK_AT_RISK_DUE_DAYS + HYSTERESIS_DAYS
    current_finish = finish_days is not None and finish_days <= SPACE_FINISH_LINE_DAYS
    sticky_finish = finish_days is not None and finish_days <= SPACE_FINISH_LINE_DAYS + HYSTERESIS_DAYS

    flag = (current_stale and (current_due or current_finish)) or (
        prior and sticky_stale and (sticky_due or sticky_finish)
    )
    reason_parts = []
    receipts = []
    if flag:
        reason_parts.append(f"stale {stale_days}d")
        receipts.append({"kind": "task", "entity_id": task["id"], "field": "activity"})
        if due_days is not None and (current_due or (prior and sticky_due)):
            if due_days < 0:
                reason_parts.append(f"overdue {abs(due_days)}d")
            else:
                reason_parts.append(f"due in {due_days}d")
            receipts.append({"kind": "task", "entity_id": task["id"], "field": "due_at"})
        if finish_days is not None and (current_finish or (prior and sticky_finish)):
            if finish_days < 0:
                reason_parts.append(f"space finish line overdue {abs(finish_days)}d")
            else:
                reason_parts.append(f"space finish line in {finish_days}d")
            if task.get("space_id"):
                receipts.append(
                    {"kind": "space", "entity_id": task["space_id"], "field": "due_at"}
                )
    return {"flag": flag, "reason": "; ".join(reason_parts), "receipts": receipts}


def derive_space_at_risk(space, *, now):
    due_at = _ensure_utc(space.get("due_at"))
    finish_days = _days_until(due_at, now)
    prior = bool(space.get("prior_at_risk"))
    quiet_days = int(space.get("last_activity_days") or 0)
    open_tasks_count = int(space.get("open_tasks_count") or 0)
    stale_open_tasks_count = int(space.get("stale_open_tasks_count") or 0)
    stale_ratio = (
        stale_open_tasks_count / open_tasks_count >= 0.5 if open_tasks_count else False
    )
    finish_current = finish_days is not None and finish_days <= SPACE_FINISH_LINE_DAYS
    finish_sticky = finish_days is not None and finish_days <= SPACE_FINISH_LINE_DAYS + HYSTERESIS_DAYS
    quiet_current = quiet_days >= SPACE_ACTIVITY_DAYS
    quiet_sticky = quiet_days >= SPACE_ACTIVITY_DAYS - HYSTERESIS_DAYS
    flag = (finish_current and (stale_ratio or quiet_current)) or (
        prior and finish_sticky and (stale_ratio or quiet_sticky)
    )

    reason_parts = []
    receipts = []
    if flag:
        if finish_days is not None:
            if finish_days < 0:
                reason_parts.append(f"finish line overdue {abs(finish_days)}d")
            else:
                reason_parts.append(f"finish line in {finish_days}d")
            receipts.append({"kind": "space", "entity_id": space["id"], "field": "due_at"})
        if stale_ratio:
            reason_parts.append(
                f"{stale_open_tasks_count} of {open_tasks_count} open tasks stale"
            )
            receipts.append(
                {
                    "kind": "space",
                    "entity_id": space["id"],
                    "field": "stale_open_tasks",
                }
            )
        if quiet_current or (prior and quiet_sticky):
            reason_parts.append(f"no space activity in {quiet_days}d")
            receipts.append({"kind": "space", "entity_id": space["id"], "field": "activity"})
    return {"flag": flag, "reason": "; ".join(reason_parts), "receipts": receipts}


def prior_at_risk_flag(properties):
    workboard = (properties or {}).get("workboard") or {}
    return bool(workboard.get("at_risk"))


def _open_workboard_tasks():
    return (
        Entity.query.filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
        )
        .order_by(Entity.due_at.asc().nullslast(), Entity.updated_at.desc())
        .all()
    )


def _task_relationship_maps(task_ids):
    if not task_ids:
        return {}, {}
    parent_rows = (
        db.session.query(EntityLink.source_entity_id, Entity)
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.source_entity_id.in_(task_ids),
            EntityLink.relationship_type == "parent",
            Entity.type == "project",
            Entity.lifecycle != "deleted",
        )
        .order_by(EntityLink.created_at.asc())
        .all()
    )
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
    spaces_by_task = {}
    owners_by_task = {}
    for task_id, space in parent_rows:
        spaces_by_task.setdefault(task_id, space)
    for task_id, owner in owner_rows:
        owners_by_task.setdefault(task_id, owner)
    for task_id in task_ids:
        spaces_by_task.setdefault(task_id, None)
        owners_by_task.setdefault(task_id, None)
    return spaces_by_task, owners_by_task


def _open_blockers_by_task(task_ids):
    if not task_ids:
        return {}
    rows = (
        db.session.query(EntityLink.target_entity_id, Entity.id, Entity.title)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "blocks",
            EntityLink.target_entity_id.in_(task_ids),
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
        )
        .order_by(Entity.updated_at.desc())
        .all()
    )
    result = {task_id: [] for task_id in task_ids}
    for task_id, blocker_id, blocker_title in rows:
        result.setdefault(task_id, []).append({"id": blocker_id, "title": blocker_title})
    return result


def _group_items(included_tasks, *, group, now, space_activity_days):
    groups = {}
    for item, space, owner in included_tasks:
        if group == "person":
            key = owner.id if owner else "unassigned"
            label = owner.title if owner else "Unassigned"
            kind = "person"
            at_risk = {"flag": False, "reason": "", "receipts": []}
        else:
            key = space.id if space else "no-space"
            label = space.title if space else "No space"
            kind = "space"
            at_risk = {"flag": False, "reason": "", "receipts": []}
        bucket = groups.setdefault(
            key,
            {
                "key": key,
                "label": label,
                "kind": kind,
                "items": [],
                "counts": _empty_counts(),
                "at_risk": at_risk,
            },
        )
        bucket["items"].append(item)
        if kind == "space":
            bucket["at_risk"] = _space_group_risk(
                space,
                bucket["items"],
                space_activity_days,
                now,
            )
        for state_name in VALID_STATES:
            if item["states"][state_name]:
                bucket["counts"][state_name] += 1
        bucket["counts"]["total"] += 1

    result = list(groups.values())
    for group_row in result:
        group_row["items"].sort(key=_task_sort_key)
    result.sort(key=lambda row: (not row["at_risk"]["flag"], row["label"].lower()))
    return result


def _space_group_risk(space, items, space_activity_days, now):
    if space is None:
        return {"flag": False, "reason": "", "receipts": []}
    stale_open_tasks_count = sum(1 for row in items if row["states"]["stale"])
    payload = {
        "id": space.id,
        "due_at": _ensure_utc(space.due_at),
        "open_tasks_count": len(items),
        "stale_open_tasks_count": stale_open_tasks_count,
        "last_activity_days": space_activity_days.get(space.id, 0),
        "prior_at_risk": prior_at_risk_flag(space.properties or {}),
    }
    return derive_space_at_risk(payload, now=now)


def _task_sort_key(item):
    due_at = _ensure_utc(item.get("due_at"))
    due_sort = due_at or datetime.max.replace(tzinfo=timezone.utc)
    return (
        not item["states"]["at_risk"],
        not item["states"]["overdue"],
        due_sort,
        (item.get("title") or "").lower(),
    )


def _space_ref(space, threshold_days):
    if space is None:
        return None
    return {
        "id": space.id,
        "title": space.title,
        "due_at": _iso(space.due_at),
        "stale_threshold_days": threshold_days,
    }


def _entity_ref(entity):
    if entity is None:
        return None
    return {"id": entity.id, "title": entity.title}


def _days_until(value, now):
    value = _ensure_utc(value)
    if value is None:
        return None
    return (value.date() - now.date()).days


def _empty_counts():
    counts = {state: 0 for state in VALID_STATES}
    counts["total"] = 0
    return counts


def _clean_text(value):
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _ensure_utc(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _get_app_setting(key, default=None):
    setting = db.session.get(AppSetting, key)
    if setting is None:
        return default
    return setting.value


def _staleness_days_for(entities, now):
    if not entities:
        return {}
    entity_ids = [entity.id for entity in entities]
    latest_updates = _latest_activity_updates(entity_ids)
    latest_events = _latest_non_creation_event_at(entity_ids)
    result = {}
    for entity in entities:
        candidates = [
            _ensure_utc(entity.updated_at),
            _ensure_utc(entity.created_at),
            _ensure_utc(latest_updates.get(entity.id)),
            _ensure_utc(latest_events.get(entity.id)),
        ]
        candidates = [value for value in candidates if value is not None]
        if not candidates:
            result[entity.id] = 0
            continue
        result[entity.id] = max(0, (now - max(candidates)).days)
    return result


def _project_staleness_days(spaces, now):
    if not spaces:
        return {}
    space_ids = [space.id for space in spaces]
    child_rows = (
        db.session.query(EntityLink.target_entity_id, Entity)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "parent",
            EntityLink.target_entity_id.in_(space_ids),
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
        )
        .all()
    )
    tasks_by_space = {space_id: [] for space_id in space_ids}
    all_task_ids = []
    for space_id, task in child_rows:
        tasks_by_space.setdefault(space_id, []).append(task)
        all_task_ids.append(task.id)
    space_updates = _latest_activity_updates(space_ids)
    task_updates = _latest_activity_updates(all_task_ids)
    space_events = _latest_non_creation_event_at(space_ids)
    task_events = _latest_non_creation_event_at(all_task_ids)
    result = {}
    for space in spaces:
        candidates = [
            _ensure_utc(space.created_at),
            _ensure_utc(space.updated_at),
            _ensure_utc(space_updates.get(space.id)),
            _ensure_utc(space_events.get(space.id)),
        ]
        for task in tasks_by_space.get(space.id, []):
            candidates.extend(
                [
                    _ensure_utc(task.created_at),
                    _ensure_utc(task.updated_at),
                    _ensure_utc(task_updates.get(task.id)),
                    _ensure_utc(task_events.get(task.id)),
                ]
            )
        candidates = [value for value in candidates if value is not None]
        result[space.id] = max(0, (now - max(candidates)).days) if candidates else 0
    return result


def _latest_activity_updates(entity_ids):
    if not entity_ids:
        return {}
    rows = (
        db.session.query(EntityLink.target_entity_id, Entity.created_at)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "activity_update",
            EntityLink.target_entity_id.in_(entity_ids),
            Entity.type == "note",
            Entity.lifecycle == "active",
        )
        .order_by(EntityLink.target_entity_id, Entity.created_at.desc())
        .all()
    )
    result = {}
    for entity_id, created_at in rows:
        result.setdefault(entity_id, created_at)
    return result


def _latest_non_creation_event_at(entity_ids):
    if not entity_ids:
        return {}
    rows = (
        db.session.query(EntityEvent.entity_id, db.func.max(EntityEvent.created_at))
        .filter(
            EntityEvent.entity_id.in_(entity_ids),
            EntityEvent.event_type != "created",
        )
        .group_by(EntityEvent.entity_id)
        .all()
    )
    return dict(rows)
