"""v6 Today feed: needs-you vs in-motion, ripened follow-ups, at-risk diff."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from extensions import db
from models import AppSetting
from services.job_worker import register_handler
from services.v4_workboard import get_workboard, operator_identity

logger = logging.getLogger(__name__)

AT_RISK_SNAPSHOT_KEY = "today_at_risk_snapshot"
AT_RISK_SNAPSHOT_JOB_TYPE = "today_at_risk_snapshot"
AT_RISK_SNAPSHOT_INTERVAL_HOURS = 24

NEEDS_YOU_KINDS = {
    "overdue",
    "due_today",
    "overdue_follow_up",
    "follow_up_today",
    "blocked",
    "waiting",
    "fired_marker",
    "ripened_follow_up",
    "newly_at_risk",
    "dependency_intervention",
    "unscheduled_attention",
    "pending_suggestions",
}


def extend_today_payload(payload, now=None):
    """Attach v6 Today sections to the legacy /today payload."""
    now = now or datetime.now(timezone.utc)
    ripened = ripened_follow_ups_from_payload(payload)
    newly_at_risk = compute_newly_at_risk(now)
    needs_you, in_motion = partition_today_sections(
        payload,
        ripened_follow_ups=ripened,
        newly_at_risk=newly_at_risk,
        now=now,
    )
    payload["ripened_follow_ups"] = ripened
    payload["newly_at_risk"] = newly_at_risk
    payload["needs_you"] = needs_you
    payload["in_motion"] = in_motion
    payload["counts"] = {
        "needs_you": len(needs_you),
        "in_motion": len(in_motion),
        "fired_markers": len(payload.get("fired_markers") or []),
        "ripened_follow_ups": len(ripened),
        "newly_at_risk": len(newly_at_risk),
    }
    return payload


def ripened_follow_ups_from_payload(payload):
    """Waiting-on follow-ups that have gone quiet with receipt context."""
    items = []
    for entity in payload.get("delegations_quiet") or []:
        person = (entity.get("people") or [None])[0]
        person_name = person.get("title") if person else "Someone"
        days = entity.get("days_silent")
        summary = f"{person_name} — quiet {days}d" if days is not None else f"{person_name} — follow-up ripe"
        receipts = []
        if entity.get("follow_up_at"):
            receipts.append(
                {
                    "kind": "task",
                    "entity_id": entity.get("id"),
                    "field": "follow_up_at",
                    "value": entity.get("follow_up_at"),
                }
            )
        if entity.get("last_update"):
            receipts.append(
                {
                    "kind": "task",
                    "entity_id": entity.get("id"),
                    "field": "last_update",
                    "value": entity.get("last_update"),
                }
            )
        items.append(
            {
                "id": entity.get("id"),
                "kind": "ripened_follow_up",
                "title": entity.get("title") or "Untitled commitment",
                "summary": summary,
                "receipts": receipts,
                "entity": entity,
                "person": person,
                "days_silent": days,
            }
        )
    return items


def partition_today_sections(payload, *, ripened_follow_ups, newly_at_risk, now):
    needs_you = []
    in_motion = []
    seen = set()

    def add_item(target, item):
        key = f"{item.get('kind')}:{item.get('id')}"
        if key in seen:
            return
        seen.add(key)
        target.append(item)

    operator_person_id, operator_configured = operator_identity()

    def is_mine(entity):
        if not operator_configured:
            return True
        people = entity.get("people") or []
        return any(person.get("id") == operator_person_id for person in people)

    entity_buckets = [
        ("overdue", payload.get("overdue") or []),
        ("due_today", payload.get("due_today") or []),
        ("overdue_follow_up", payload.get("overdue_follow_ups") or []),
        ("follow_up_today", payload.get("follow_ups") or []),
        ("blocked", payload.get("blocked_tasks") or []),
        ("waiting", payload.get("waiting_tasks") or []),
        ("unscheduled_attention", payload.get("unscheduled_attention_tasks") or []),
    ]
    for kind, entities in entity_buckets:
        for entity in entities:
            mine = is_mine(entity)
            target = needs_you if mine or kind in {"blocked", "waiting", "unscheduled_attention"} else in_motion
            summary = _attention_summary(entity, kind)
            add_item(
                target,
                {
                    "id": entity.get("id"),
                    "kind": kind,
                    "title": entity.get("title") or "Untitled",
                    "summary": summary,
                    "receipts": _entity_receipts(entity),
                    "entity": entity,
                },
            )

    for marker in payload.get("fired_markers") or []:
        entity = marker.get("entity") or {}
        add_item(
            needs_you,
            {
                "id": marker.get("id"),
                "kind": "fired_marker",
                "title": marker.get("note") or entity.get("title") or "Follow-up marker",
                "summary": f"{marker.get('kind', 'marker')} marker fired",
                "receipts": [
                    {
                        "kind": "marker",
                        "entity_id": marker.get("id"),
                        "field": "due_at",
                        "value": marker.get("due_at"),
                    }
                ],
                "marker": marker,
                "entity": entity,
            },
        )

    for item in ripened_follow_ups:
        add_item(needs_you, item)

    for item in newly_at_risk:
        add_item(needs_you, item)

    for intervention in payload.get("dependency_interventions") or []:
        entity = intervention.get("entity") or {}
        add_item(
            needs_you,
            {
                "id": entity.get("id") or intervention.get("label"),
                "kind": "dependency_intervention",
                "title": entity.get("title") or intervention.get("label") or "Dependency",
                "summary": intervention.get("label") or "Dependency needs attention",
                "receipts": _entity_receipts(entity),
                "entity": entity,
                "intervention": intervention,
            },
        )

    suggestions = payload.get("pending_suggestions") or []
    if suggestions:
        add_item(
            needs_you,
            {
                "id": "pending-suggestions",
                "kind": "pending_suggestions",
                "title": f"{len(suggestions)} suggestion{'s' if len(suggestions) != 1 else ''} ready to review",
                "summary": "From recent captures",
                "receipts": [],
                "count": len(suggestions),
            },
        )

    upcoming_buckets = [
        ("upcoming_follow_up", payload.get("upcoming_follow_ups") or []),
        ("upcoming_due", payload.get("upcoming_due_tasks") or []),
    ]
    for kind, entities in upcoming_buckets:
        for entity in entities:
            add_item(
                in_motion,
                {
                    "id": entity.get("id"),
                    "kind": kind,
                    "title": entity.get("title") or "Untitled",
                    "summary": _attention_summary(entity, kind),
                    "receipts": _entity_receipts(entity),
                    "entity": entity,
                },
            )

    for note in payload.get("recent_notes") or []:
        add_item(
            in_motion,
            {
                "id": note.get("id"),
                "kind": "recent_note",
                "title": note.get("title") or "Recent capture",
                "summary": str((note.get("ai") or {}).get("intent") or "recent note").replace("_", " "),
                "receipts": _entity_receipts(note),
                "entity": note,
            },
        )

    for entity in (payload.get("stale_projects") or []) + (payload.get("suggested_archival") or []):
        add_item(
            in_motion,
            {
                "id": entity.get("id"),
                "kind": "stale_project",
                "title": entity.get("title") or "Untitled space",
                "summary": f"No activity in {entity.get('stale_days', '?')} days",
                "receipts": _entity_receipts(entity),
                "entity": entity,
            },
        )

    needs_you.sort(key=_needs_you_sort_key)
    in_motion.sort(key=_in_motion_sort_key)
    return needs_you, in_motion


def list_at_risk_items(now=None):
    now = now or datetime.now(timezone.utc)
    board = get_workboard(group="space", now=now)
    items = []
    seen = set()
    for group in board.get("groups") or []:
        if group.get("at_risk", {}).get("flag") and group.get("entity_id"):
            key = f"space:{group['entity_id']}"
            if key not in seen:
                seen.add(key)
                items.append(
                    {
                        "id": group["entity_id"],
                        "type": "project",
                        "kind": "space_at_risk",
                        "title": group.get("label") or "Space",
                        "reason": group["at_risk"].get("reason") or "",
                        "receipts": group["at_risk"].get("receipts") or [],
                    }
                )
        for row in group.get("items") or []:
            if not row.get("at_risk", {}).get("flag"):
                continue
            key = f"task:{row['id']}"
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "id": row["id"],
                    "type": "task",
                    "kind": "task_at_risk",
                    "title": row.get("title") or "Commitment",
                    "reason": row["at_risk"].get("reason") or "",
                    "receipts": row["at_risk"].get("receipts") or [],
                    "entity": row,
                }
            )
    return items


def at_risk_keys(items):
    return sorted(f"{item['type']}:{item['id']}" for item in items)


def load_at_risk_snapshot():
    setting = db.session.get(AppSetting, AT_RISK_SNAPSHOT_KEY)
    if setting is None or not setting.value:
        return None
    try:
        data = setting.value if isinstance(setting.value, dict) else json.loads(setting.value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    keys = data.get("keys")
    if not isinstance(keys, list):
        return None
    return {
        "captured_at": data.get("captured_at"),
        "keys": set(keys),
    }


def save_at_risk_snapshot(items, now=None):
    now = now or datetime.now(timezone.utc)
    payload = {
        "captured_at": now.isoformat(),
        "keys": at_risk_keys(items),
    }
    setting = db.session.get(AppSetting, AT_RISK_SNAPSHOT_KEY)
    if setting is None:
        setting = AppSetting(key=AT_RISK_SNAPSHOT_KEY, value=payload)
        db.session.add(setting)
    else:
        setting.value = payload
    db.session.commit()
    return payload


def compute_newly_at_risk(now=None):
    now = now or datetime.now(timezone.utc)
    current = list_at_risk_items(now)
    snapshot = load_at_risk_snapshot()
    if snapshot is None:
        return []
    prior_keys = snapshot.get("keys") or set()
    newly = []
    for item in current:
        key = f"{item['type']}:{item['id']}"
        if key in prior_keys:
            continue
        newly.append(
            {
                "id": item["id"],
                "kind": "newly_at_risk",
                "title": item.get("title") or "At-risk item",
                "summary": item.get("reason") or "Newly at risk since yesterday",
                "receipts": item.get("receipts") or [],
                "entity": item.get("entity"),
                "entity_type": item.get("type"),
            }
        )
    return newly


def run_at_risk_snapshot():
    now = datetime.now(timezone.utc)
    items = list_at_risk_items(now)
    payload = save_at_risk_snapshot(items, now)
    logger.info("today at-risk snapshot captured %s keys", len(payload["keys"]))
    return {"captured": len(payload["keys"]), "captured_at": payload["captured_at"]}


def schedule_next_at_risk_snapshot(hours=AT_RISK_SNAPSHOT_INTERVAL_HOURS):
    from models import Job

    existing = Job.query.filter_by(job_type=AT_RISK_SNAPSHOT_JOB_TYPE, status="pending").first()
    if existing is not None:
        return existing
    job = Job(
        job_type=AT_RISK_SNAPSHOT_JOB_TYPE,
        payload={"scheduled": True},
        run_after=datetime.now(timezone.utc) + timedelta(hours=hours),
    )
    db.session.add(job)
    db.session.commit()
    return job


@register_handler(AT_RISK_SNAPSHOT_JOB_TYPE)
def handle_at_risk_snapshot_job(payload):
    try:
        run_at_risk_snapshot()
    finally:
        schedule_next_at_risk_snapshot()


def ensure_at_risk_snapshot_scheduled(app):
    from models import Job

    with app.app_context():
        existing = Job.query.filter_by(job_type=AT_RISK_SNAPSHOT_JOB_TYPE, status="pending").first()
        if existing is not None:
            return
        job = Job(
            job_type=AT_RISK_SNAPSHOT_JOB_TYPE,
            payload={"scheduled": True, "bootstrap": True},
            run_after=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        db.session.add(job)
        db.session.commit()


def _attention_summary(entity, kind):
    reasons = (entity.get("attention") or {}).get("reasons") or []
    if reasons:
        return reasons[0].get("label") or kind.replace("_", " ")
    labels = {
        "overdue": "overdue",
        "due_today": "due today",
        "overdue_follow_up": "overdue follow-up",
        "follow_up_today": "follow-up today",
        "blocked": "blocked",
        "waiting": "waiting",
        "upcoming_follow_up": "follow-up later this week",
        "upcoming_due": "due later this week",
        "unscheduled_attention": "needs attention",
    }
    return labels.get(kind, kind.replace("_", " "))


def _entity_receipts(entity):
    receipts = []
    if not entity:
        return receipts
    for field in ("due_at", "follow_up_at", "updated_at", "created_at"):
        if entity.get(field):
            receipts.append(
                {
                    "kind": entity.get("type") or "entity",
                    "entity_id": entity.get("id"),
                    "field": field,
                    "value": entity.get(field),
                }
            )
    return receipts[:3]


def _needs_you_sort_key(item):
    priority = {
        "fired_marker": 0,
        "newly_at_risk": 1,
        "overdue": 2,
        "overdue_follow_up": 3,
        "due_today": 4,
        "follow_up_today": 5,
        "blocked": 6,
        "ripened_follow_up": 7,
        "dependency_intervention": 8,
        "waiting": 9,
        "unscheduled_attention": 10,
        "pending_suggestions": 11,
    }
    return (priority.get(item.get("kind"), 20), (item.get("title") or "").lower())


def _in_motion_sort_key(item):
    priority = {
        "upcoming_due": 0,
        "upcoming_follow_up": 1,
        "recent_note": 2,
        "stale_project": 3,
    }
    return (priority.get(item.get("kind"), 10), (item.get("title") or "").lower())
