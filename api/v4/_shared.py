"""Engram v4 canonical entity API."""

from datetime import datetime, time, timezone, timedelta
import hashlib
import json
import logging
import re
import time as time_module

from flask import Response, current_app, jsonify, request, stream_with_context
from sqlalchemy import func, or_, text
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import selectinload

from extensions import db
from models import AiSuggestion, AppSetting, Decision, Entity, EntityChunk, EntityEvent, EntityLink, EntityTag, Job, Tag, _iso
from services import runtime_health
from services.v4_attention import attention_for_entity, today_attention_count, today_attention_items
from services.v4_narration import narrate_event
from services.title_utils import title_or_placeholder

logger = logging.getLogger(__name__)

TOPIC_CLUSTER_SIMILARITY = 0.7
TOPIC_CLUSTER_TIME_BUDGET_MS = 500

STATUS_BY_TYPE = {
    "note": ["active", "processed", "archived"],
    "task": ["open", "in_progress", "waiting", "blocked", "done", "cancelled"],
    "project": ["active", "on_hold", "completed", "cancelled"],
    "area": ["active", "archived"],
    "person": ["active", "archived"],
    "resource": ["active", "archived"],
}

ENTITY_TYPES = {"note", "task", "project", "area", "resource", "person"}
PRIORITY_LEVELS = {"low", "medium", "high", "urgent"}
PRIORITY_ORDER = {"low": 1, "medium": 2, "high": 3, "urgent": 4}
DEFAULT_STATUS = {
    "note": "active",
    "task": "open",
    "project": "active",
    "area": "active",
    "resource": "active",
    "person": "active",
}
VALID_STATUS = {
    "note": {"active", "processed", "archived"},
    "task": {"open", "in_progress", "waiting", "blocked", "done", "cancelled"},
    "project": {"active", "on_hold", "completed", "cancelled"},
    "area": {"active", "archived"},
    "resource": {"active", "archived"},
    "person": {"active", "archived"},
}
VALID_LIFECYCLE = {"active", "archived", "deleted", "redacted"}
REDACTED_TOMBSTONE = "[Content redacted]"
REDACTED_TITLE = "[Redacted note]"
REDACTED_CITATION_LABEL = "cites a redacted entry"
OPEN_ASSIGNED_TASK_STATUSES = {"open", "in_progress", "waiting", "blocked"}
WRITABLE_FIELDS = {
    "title",
    "content",
    "status",
    "lifecycle",
    "due_at",
    "follow_up_at",
    "source",
    "reference_url",
    "properties",
}
RELATIONSHIP_PROPERTY_KEYS = {
    f"{prefix}{suffix}"
    for prefix in ("project", "area", "person", "note", "source_note", "parent")
    for suffix in ("_id", "_ids")
}
RELATIONSHIP_TYPES = {
    "parent",
    "related",
    "derived_from",
    "mentions",
    "assigned_to",
    "references",
    "blocks",
    "activity_update",
}
# Semantic source/target type constraints for manually-created relationships.
# Derived from the detail-section type filters and the canonical examples in
# docs/V4_PRINCIPLES.md.
RELATIONSHIP_COMPATIBILITY = {
    "parent": {
        "task": {"project", "area"},
        "project": {"area"},
    },
    "assigned_to": {
        "task": {"person"},
    },
    "derived_from": {
        "task": {"note"},
    },
    "mentions": {
        "note": {"person", "project", "area"},
        "task": {"person"},
        "project": {"person"},
        "area": {"person"},
        "person": {"project", "person"},
        "resource": {"person", "project", "task", "area", "resource"},
    },
    "references": {
        "note": {"resource"},
        "task": {"resource"},
        "project": {"resource"},
        "area": {"resource"},
        "person": {"resource"},
        "resource": {"project", "task", "area", "person", "resource", "note"},
    },
    "related": {
        "task": {"task", "note", "resource", "person", "project", "area"},
        "project": {"project", "note", "resource", "person", "area"},
        "area": {"note", "resource", "person", "project", "area"},
        "note": {"note", "project", "area", "person", "resource", "task"},
        "person": {"person", "project", "resource", "task", "area"},
        "resource": {"resource", "project", "task", "area", "person", "note"},
    },
    "blocks": {
        "task": {"task"},
        "project": {"project"},
    },
    "activity_update": {
        "note": {"task", "project", "area"},
    },
}
DEFAULT_OWNER_ALIASES = ["dan"]
DEFAULT_DELEGATION_CADENCE_DAYS = 3

# SQ-09: confidence thresholds are tiebreakers, not primary gates. Every path
# that consults them first checks a structural precondition (SQ-07/SQ-08 task
# and person hygiene, reconciler action, near-duplicate score, explicit status
# language, etc.). Production data showed extractor confidence is not
# predictive (deleted vs surviving tasks averaged 0.94 vs 0.95), so the model
# is no longer asked to self-grade for gating decisions.
AUTO_APPLY_CONFIDENCE = 0.8
LOW_CONFIDENCE_THRESHOLD = 0.5

RISKY_ENTITY_CREATION_TYPES = {"task", "project", "area", "resource", "person"}
# Entity types that can anchor ingest_candidates / reconciliation thread context.
THREAD_INGEST_SOURCE_TYPES = {"project", "task", "area"}
# Types that are always routed to the review queue rather than created
# directly from capture.
SUGGEST_ONLY_CREATION_TYPES = {"project", "area"}
# SQ-07: task suggest gate. A task candidate must pass structural checks
# before confidence is consulted; confidence is a tiebreaker, not the gate.
# Score interpretation (documented inline in _task_structural_score):
#   2-4 checks passed: suggest if confidence is above the low threshold, else drop.
#   0-1 checks passed: drop (meeting logistics, stance fragments, restatements).
TASK_SUGGESTION_CAP_PER_NOTE = 8
# Reconciliation similarity at or above which a "new" decision is treated as
# a potential duplicate and routed to the review queue.
NEAR_DUPLICATE_SCORE = 0.75
CAPTURE_INTENTS = {"update", "task_signal", "follow_up", "blocker", "delegation", "reference", "junk", "note"}
INBOX_INTENT_PRIORITY = {
    "blocker": 0,
    "follow_up": 1,
    "delegation": 2,
    "task_signal": 3,
    "update": 4,
    "reference": 5,
    "note": 6,
    "junk": 7,
}
INTENT_SUGGESTION_CONFIDENCE_FLOOR = 0.9
# SQ-09: intent-confidence threshold for routing a capture to the
# activity-update pipeline. The structural precondition is a recognized
# update/follow_up intent plus short content; confidence is the tiebreaker
# that routes borderline cases through the safer full extraction pipeline.
INTENT_ROUTE_CONFIDENCE = 0.7
# Long captures (meeting notes) stay on the full pipeline even when the
# top-level intent looks like an update — they usually carry more than one
# actionable signal.
INTENT_ROUTE_MAX_CONTENT_CHARS = 1200
# Minimum cosine similarity for resolving an update target by embedding search
# (ladder step 3). Deliberately strict: a wrong guess applies a status change.
UPDATE_TARGET_SIMILARITY = 0.75
SUGGESTION_DUPLICATE_MEMORY_DAYS = 14
# SQ-10: semantic duplicate memory window. Longer than the exact-fingerprint
# window because reworded duplicates are worth remembering for a full month.
SUGGESTION_SEMANTIC_MEMORY_DAYS = 30
SUGGESTION_SEMANTIC_SIMILARITY_THRESHOLD = 0.85
COMPACT_LINK_COUNT_RULES = {
    "person": {
        "notes": ("incoming", {"mentions"}, {"note"}),
        "tasks": ("incoming", {"assigned_to"}, {"task"}),
        "projects": ("both", {"assigned_to", "mentions", "related"}, {"project"}),
    },
    "area": {
        "notes": ("both", {"related", "mentions"}, {"note"}),
        "tasks": ("incoming", {"parent", "related"}, {"task"}),
        "projects": ("incoming", {"parent", "related"}, {"project"}),
    },
}


CAPTURE_STREAM_EVENTS = (
    "reading",
    "extracting",
    "candidates",
    "reconciling",
    "applying",
    "linking",
    "summarizing",
    "done",
)


def _format_capture_sse_event(event_type, payload):
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


def _create_capture_note(data, content, user_title):
    note = Entity(
        type="note",
        title=user_title or _title_from_content(content),
        content=content,
        status="active",
        lifecycle="active",
        source=data.get("source") or "quick_capture",
        properties={},
        ai_meta={"title_auto": user_title is None},
        ai_status="pending",
    )
    db.session.add(note)
    db.session.flush()
    _clear_review_resolution(note)
    _write_event(note, "created", new_value=note.to_dict())
    db.session.add(Job(job_type="embed", entity_id=note.id, payload={"entity_id": note.id, "reason": "capture"}))
    return note


def _entity_brief(entity_id):
    if not entity_id:
        return None
    entity = db.session.get(Entity, entity_id)
    if entity is None:
        return None
    return {"id": entity.id, "type": entity.type, "title": entity.title}


def _event_reason_for_applied_change(change, events):
    change_type = change.get("type")
    if change_type == "entity_created":
        entity_id = change.get("entity_id")
        for event in events:
            if event.event_type == "created" and event.entity_id == entity_id:
                return event.reason
    elif change_type == "entity_updated":
        entity_id = change.get("entity_id")
        for event in events:
            if event.event_type == "ai_updated" and event.entity_id == entity_id:
                return event.reason
    elif change_type == "activity_update_added":
        target_id = change.get("target_entity_id")
        for event in events:
            if event.event_type == "activity_update_added" and event.entity_id == target_id:
                return event.reason
    elif change_type == "relationship_added":
        target_id = change.get("target_entity_id")
        source_id = change.get("source_entity_id")
        rel_type = change.get("relationship_type")
        for event in events:
            if event.event_type != "relationship_added":
                continue
            link_value = event.new_value or {}
            if rel_type and link_value.get("relationship_type") != rel_type:
                continue
            if target_id and link_value.get("target_entity_id") == target_id:
                return event.reason
            if source_id and link_value.get("source_entity_id") == source_id:
                return event.reason
    elif change_type == "title_updated":
        for event in events:
            if event.event_type == "ai_updated" and event.reason == "ai_title_set":
                return event.reason
    return None


def _matched_entity_for_applied_change(change):
    change_type = change.get("type")
    if change_type in ("entity_updated", "activity_update_added"):
        return _entity_brief(change.get("entity_id") or change.get("target_entity_id"))
    if change_type == "relationship_added":
        return _entity_brief(change.get("target_entity_id"))
    if change_type == "entity_created":
        return _entity_brief(change.get("entity_id"))
    return None


def _enrich_applied_change(change, events):
    enriched = dict(change)
    if not enriched.get("reason"):
        reason = _event_reason_for_applied_change(change, events)
        if reason:
            enriched["reason"] = reason
    if "match_confidence" not in enriched and enriched.get("confidence") is not None:
        enriched["match_confidence"] = enriched["confidence"]
    if "matched_entity" not in enriched:
        matched = _matched_entity_for_applied_change(change)
        if matched:
            enriched["matched_entity"] = matched
    return enriched


def _enrich_suggestion_item(suggestion):
    enriched = dict(suggestion)
    payload = enriched.get("payload") or {}
    near_match = payload.get("near_match")
    if near_match and "matched_entity" not in enriched:
        entity_id = near_match.get("entity_id")
        if entity_id:
            enriched["matched_entity"] = {
                "id": entity_id,
                "type": payload.get("target_type") or near_match.get("type"),
                "title": near_match.get("title") or payload.get("title"),
            }
    if "match_confidence" not in enriched:
        if near_match and near_match.get("score") is not None:
            enriched["match_confidence"] = near_match["score"]
        elif enriched.get("confidence") is not None:
            enriched["match_confidence"] = enriched["confidence"]
    return enriched


def _capture_result_payload(note, applied_changes, suggestions, warnings, report_id=None):
    events = (
        EntityEvent.query.filter_by(source_note_id=note.id)
        .order_by(EntityEvent.created_at.asc())
        .all()
    )
    payload = {
        "source_note": _load_entity(note.id).to_dict(),
        "applied_changes": [_enrich_applied_change(change, events) for change in applied_changes],
        "suggestions": [_enrich_suggestion_item(suggestion) for suggestion in suggestions],
        "warnings": warnings,
        "report_id": report_id,
    }
    return payload


def _count_extraction_candidates(extraction):
    if not extraction:
        return 0
    return len(extraction.get("entities") or []) + len(extraction.get("links") or [])


def _count_capture_summarize_jobs():
    return (
        db.session.query(Job)
        .filter(
            Job.job_type == "summarize",
            Job.status.in_(["pending", "running"]),
        )
        .count()
    )


def _timeline_thread_entity_ids(thread_id):
    """Return entity IDs whose events belong to the given thread."""
    entity_ids = {thread_id}
    thread = db.session.get(Entity, thread_id)
    if thread is None:
        return entity_ids

    if thread.type == "project":
        rows = (
            db.session.query(EntityLink.source_entity_id)
            .filter(
                EntityLink.target_entity_id == thread_id,
                EntityLink.relationship_type == "parent",
            )
            .all()
        )
    elif thread.type == "person":
        rows = (
            db.session.query(EntityLink.source_entity_id)
            .filter(
                EntityLink.target_entity_id == thread_id,
                EntityLink.relationship_type.in_(["assigned_to", "mentions"]),
            )
            .all()
        )
    else:
        rows = []

    entity_ids.update(r[0] for r in rows)
    return entity_ids


def _timeline_thread_map(entity_ids):
    """Map entity_id -> derived thread_id for a batch of entities.

    Priority: parent project, assigned person, mentions person, entity itself.
    """
    if not entity_ids:
        return {}

    rows = (
        db.session.query(EntityLink.source_entity_id, EntityLink.target_entity_id, EntityLink.relationship_type)
        .filter(
            EntityLink.source_entity_id.in_(entity_ids),
            EntityLink.relationship_type.in_(["parent", "assigned_to", "mentions"]),
        )
        .all()
    )

    target_ids = {r.target_entity_id for r in rows}
    targets = {
        e.id: e.type
        for e in db.session.query(Entity.id, Entity.type).filter(Entity.id.in_(target_ids)).all()
    }

    result = {}
    for source_id, target_id, rel_type in rows:
        target_type = targets.get(target_id)
        if rel_type == "parent" and target_type == "project":
            result[source_id] = target_id
        elif rel_type == "assigned_to" and target_type == "person" and source_id not in result:
            result[source_id] = target_id
        elif rel_type == "mentions" and target_type == "person" and source_id not in result:
            result[source_id] = target_id

    for entity_id in entity_ids:
        result.setdefault(entity_id, entity_id)

    return result


ENTITY_TYPE_PLURAL = {t: ("people" if t == "person" else f"{t}s") for t in ENTITY_TYPES}
ENTITY_TYPE_BY_PLURAL = {plural: t for t, plural in ENTITY_TYPE_PLURAL.items()}

MENTION_TYPES_PER_GROUP = 5


DONE_TASK_STATUSES = {"done", "completed", "cancelled"}
OPEN_TASK_STATUSES = {"open", "in_progress", "waiting", "blocked"}
FOLLOW_UP_ENTITY_TYPES = {"task", "project"}

# Phase F (proactive monitoring): an active project with no activity update,
# event, or field change in this many days is "stale"; at the longer
# threshold, archival is suggested (never applied automatically).
STALE_PROJECT_DAYS = 14
ARCHIVAL_SUGGESTION_DAYS = 30
PERSON_PULSE_QUIET_DAYS = 7


def _build_today_payload(now):
    start_of_today = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    end_of_today = datetime.combine(now.date(), time.max, tzinfo=timezone.utc)

    overdue = (
        _entity_query()
        .filter(
            Entity.lifecycle == "active",
            Entity.type.in_(FOLLOW_UP_ENTITY_TYPES),
            Entity.due_at.isnot(None),
            Entity.due_at < start_of_today,
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(Entity.due_at.asc())
        .limit(50)
        .all()
    )
    due_today = (
        _entity_query()
        .filter(
            Entity.lifecycle == "active",
            Entity.type.in_(FOLLOW_UP_ENTITY_TYPES),
            Entity.due_at.isnot(None),
            Entity.due_at >= start_of_today,
            Entity.due_at <= end_of_today,
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(Entity.due_at.asc())
        .limit(50)
        .all()
    )
    overdue_follow_ups = (
        _entity_query()
        .filter(
            Entity.lifecycle == "active",
            Entity.type.in_(FOLLOW_UP_ENTITY_TYPES),
            Entity.follow_up_at.isnot(None),
            Entity.follow_up_at < start_of_today,
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(Entity.follow_up_at.asc())
        .limit(50)
        .all()
    )
    follow_ups = (
        _entity_query()
        .filter(
            Entity.lifecycle == "active",
            Entity.type.in_(FOLLOW_UP_ENTITY_TYPES),
            Entity.follow_up_at.isnot(None),
            Entity.follow_up_at >= start_of_today,
            Entity.follow_up_at <= end_of_today,
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(Entity.follow_up_at.asc())
        .limit(50)
        .all()
    )
    end_of_week = end_of_today + timedelta(days=7)
    upcoming_follow_ups = (
        _entity_query()
        .filter(
            Entity.lifecycle == "active",
            Entity.type.in_(FOLLOW_UP_ENTITY_TYPES),
            Entity.follow_up_at.isnot(None),
            Entity.follow_up_at > end_of_today,
            Entity.follow_up_at <= end_of_week,
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(Entity.follow_up_at.asc())
        .limit(50)
        .all()
    )
    upcoming_due_tasks = (
        _entity_query()
        .filter(
            Entity.lifecycle == "active",
            Entity.type.in_(FOLLOW_UP_ENTITY_TYPES),
            Entity.due_at.isnot(None),
            Entity.due_at > end_of_today,
            Entity.due_at <= end_of_week,
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(Entity.due_at.asc())
        .limit(50)
        .all()
    )
    blocked_tasks = (
        _entity_query()
        .filter(Entity.type == "task", Entity.lifecycle == "active", Entity.status == "blocked")
        .order_by(Entity.updated_at.desc())
        .limit(50)
        .all()
    )
    waiting_tasks = (
        _entity_query()
        .filter(Entity.type == "task", Entity.lifecycle == "active", Entity.status == "waiting")
        .order_by(Entity.updated_at.desc())
        .limit(50)
        .all()
    )
    # Single query: which active projects have at least one open task parent-linked.
    projects_with_open_subquery = (
        db.session.query(EntityLink.target_entity_id)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "parent",
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
        )
        .distinct()
        .subquery()
    )
    projects_without_open_tasks = (
        _entity_query()
        .filter(
            Entity.type == "project",
            Entity.lifecycle == "active",
            Entity.status == "active",
            ~Entity.id.in_(db.session.query(projects_with_open_subquery.c.target_entity_id)),
        )
        .order_by(Entity.updated_at.desc())
        .limit(25)
        .all()
    )
    # Open tasks with no due/follow-up date of their own — invisible to the
    # date-based buckets above. Ranked by impact + staleness so neglected or
    # blocking work still surfaces.
    unscheduled_tasks = (
        _entity_query()
        .filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
            Entity.due_at.is_(None),
            Entity.follow_up_at.is_(None),
        )
        .order_by(Entity.updated_at.desc())
        .limit(100)
        .all()
    )

    delegations_quiet = _delegations_quiet(now)
    dependency_interventions = _today_dependency_interventions(now)

    active_projects = (
        _entity_query()
        .filter(Entity.type == "project", Entity.lifecycle == "active", Entity.status == "active")
        .all()
    )
    project_staleness = _project_staleness_days(active_projects, now)
    stale_projects = []
    suggested_archival = []
    for project in active_projects:
        days = project_staleness.get(project.id, 0)
        if days >= STALE_PROJECT_DAYS:
            entry = _entity_with_attention(project)
            entry["stale_days"] = days
            if days >= ARCHIVAL_SUGGESTION_DAYS:
                suggested_archival.append(entry)
            else:
                stale_projects.append(entry)
    stale_projects.sort(key=lambda item: item["stale_days"], reverse=True)
    suggested_archival.sort(key=lambda item: item["stale_days"], reverse=True)

    pending_suggestions = (
        AiSuggestion.query.filter_by(status="pending")
        .order_by(AiSuggestion.created_at.desc())
        .limit(25)
        .all()
    )
    recent_notes = (
        _entity_query()
        .filter(
            Entity.type == "note",
            Entity.lifecycle == "active",
            Entity.source != "activity_update",
        )
        .order_by(Entity.updated_at.desc(), Entity.created_at.desc())
        .limit(25)
        .all()
    )

    all_tasks = (
        overdue + due_today + overdue_follow_ups + follow_ups + upcoming_follow_ups
        + upcoming_due_tasks + blocked_tasks + waiting_tasks + unscheduled_tasks
    )
    inherited_priorities = _inherited_task_priorities(all_tasks)
    staleness_by_id = _staleness_days_for(all_tasks, now)
    impact_by_id = _blocking_impact_counts(all_tasks)
    _attach_task_context(all_tasks)

    def with_priority(entity, **kwargs):
        return _entity_with_attention(
            entity,
            inherited_priority=inherited_priorities.get(entity.id),
            staleness_days=staleness_by_id.get(entity.id),
            blocks_count=impact_by_id.get(entity.id, 0),
            **kwargs,
        )

    unscheduled_attention = sorted(
        (with_priority(entity) for entity in unscheduled_tasks),
        key=lambda item: item["attention"]["score"],
        reverse=True,
    )
    unscheduled_attention = [item for item in unscheduled_attention if item["attention"]["score"] > 0][:20]

    last_reviewed_at = _get_app_setting("last_reviewed_at")
    reviewed_today = bool(
        last_reviewed_at and _parse_datetime(last_reviewed_at) >= start_of_today
    )

    payload = {
        "overdue": [with_priority(entity) for entity in overdue],
        "due_today": [with_priority(entity) for entity in due_today],
        "overdue_follow_ups": [with_priority(entity) for entity in overdue_follow_ups],
        "follow_ups": [with_priority(entity) for entity in follow_ups],
        "upcoming_follow_ups": [with_priority(entity) for entity in upcoming_follow_ups],
        "upcoming_due_tasks": [with_priority(entity) for entity in upcoming_due_tasks],
        "blocked_tasks": [with_priority(entity) for entity in blocked_tasks],
        "waiting_tasks": [with_priority(entity) for entity in waiting_tasks],
        "unscheduled_attention_tasks": unscheduled_attention,
        "last_reviewed_at": last_reviewed_at,
        "reviewed_today": reviewed_today,
        "projects_without_open_tasks": [
            _entity_with_attention(entity, context=["project_without_open_tasks"])
            for entity in projects_without_open_tasks
        ],
        "recent_notes": [_entity_with_attention(entity) for entity in recent_notes],
        "delegations_quiet": delegations_quiet,
        "dependency_interventions": dependency_interventions,
        "stale_projects": stale_projects,
        "suggested_archival": suggested_archival,
        "pending_suggestions": [suggestion.to_dict() for suggestion in pending_suggestions],
        # Retained for any external callers; matches the new bucket structure semantically.
        "blocked_or_waiting_tasks": [with_priority(e) for e in (blocked_tasks + waiting_tasks)],
    }

    # Phase F (proactive monitoring): "N new items since yesterday" — items in
    # today's actionable set created within the last 24h, or since the last
    # day-review if that was more recent (so re-checking shortly after a
    # review doesn't re-surface the same items as "new").
    since_cutoff = now - timedelta(hours=24)
    if last_reviewed_at:
        reviewed_dt = _parse_datetime(last_reviewed_at)
        if reviewed_dt > since_cutoff:
            since_cutoff = reviewed_dt
    new_since_yesterday_count = sum(
        1
        for item in today_attention_items(payload)
        if item.get("created_at") and _parse_datetime(item["created_at"]) >= since_cutoff
    )
    payload["new_since_yesterday_count"] = new_since_yesterday_count

    return payload


def _decisions_count_for_entity(entity_id):
    """Count active (non-superseded) decisions recorded for an entity."""
    return Decision.query.filter(
        Decision.thread_id == entity_id,
        Decision.superseded_by.is_(None),
    ).count()


def _needs_review_query():
    unresolved_review = or_(
        Entity.ai_meta["review_state"].as_string().is_(None),
        Entity.ai_meta["review_state"].as_string() != "resolved",
    )

    # Notes with pending AI suggestions linked to them.
    notes_with_suggestions = {
        row[0] for row in db.session.query(AiSuggestion.source_entity_id)
        .filter(AiSuggestion.status == "pending")
        .distinct().all()
    }

    return _entity_query().filter(
        Entity.type == "note",
        Entity.lifecycle == "active",
        unresolved_review,
        or_(
            Entity.ai_status == "pending",
            Entity.ai_status == "failed",
            Entity.id.in_(notes_with_suggestions) if notes_with_suggestions else Entity.id.is_(None),
        ),
    )


def _needs_review_count():
    return _needs_review_query().count()


def _pending_suggestions_count():
    return db.session.query(AiSuggestion.id).filter(AiSuggestion.status == "pending").count()


def _entity_with_attention(
    entity,
    *,
    pending_suggestion_count=0,
    context=None,
    inherited_priority=None,
    staleness_days=None,
    blocks_count=0,
):
    data = entity.to_dict()
    data["attention"] = attention_for_entity(
        entity,
        pending_suggestion_count=pending_suggestion_count,
        context=context,
        inherited_priority=inherited_priority,
        staleness_days=staleness_days,
        blocks_count=blocks_count,
    )
    if inherited_priority and not (entity.properties or {}).get("priority"):
        data["inherited_priority"] = inherited_priority
    return data


def _inherited_task_priorities(tasks):
    """Map task_id -> parent project's properties.priority, for tasks that
    have no priority of their own and a 'parent' project link. Batched."""
    candidates = [t for t in tasks if t.type == "task" and not (t.properties or {}).get("priority")]
    if not candidates:
        return {}
    task_ids = [t.id for t in candidates]
    rows = (
        db.session.query(EntityLink.source_entity_id, Entity.properties)
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.source_entity_id.in_(task_ids),
            EntityLink.relationship_type == "parent",
            Entity.type == "project",
        )
        .all()
    )
    result = {}
    for task_id, properties in rows:
        priority = (properties or {}).get("priority")
        if priority:
            result[task_id] = priority
    return result


def _staleness_days_for(entities, now):
    """Map entity_id -> days since its last activity (most recent
    activity-update note, falling back to updated_at). Batched (no N+1)."""
    if not entities:
        return {}
    entity_ids = [e.id for e in entities]
    latest_update = _latest_activity_updates(entity_ids)
    result = {}
    for entity in entities:
        last = latest_update.get(entity.id)
        reference = last[0] if last else entity.created_at
        if reference is None:
            continue
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        result[entity.id] = max(0, (now - reference).days)
    return result


def _child_task_ids_by_project(project_ids):
    """Map project_id -> non-deleted child task ids (parent-linked). Batched."""
    if not project_ids:
        return {}
    rows = (
        db.session.query(EntityLink.target_entity_id, EntityLink.source_entity_id)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "parent",
            EntityLink.target_entity_id.in_(project_ids),
            Entity.type == "task",
            Entity.lifecycle != "deleted",
        )
        .all()
    )
    result = {project_id: [] for project_id in project_ids}
    for project_id, task_id in rows:
        result.setdefault(project_id, []).append(task_id)
    return result


def _project_staleness_days(entities, now):
    """Map entity_id -> days since the most recent of: an activity-update
    note or EntityEvent on the project itself, or on any parent-linked child
    task. Batched."""
    if not entities:
        return {}
    entity_ids = [e.id for e in entities]
    child_by_project = _child_task_ids_by_project(entity_ids)
    all_child_ids = [task_id for task_ids in child_by_project.values() for task_id in task_ids]
    tracked_ids = entity_ids + all_child_ids
    latest_update = _latest_activity_updates(tracked_ids)
    latest_event = _latest_event_at(tracked_ids)
    result = {}
    for entity in entities:
        candidates = [entity.created_at]
        if entity.id in latest_update:
            candidates.append(latest_update[entity.id][0])
        if entity.id in latest_event:
            candidates.append(latest_event[entity.id])
        for task_id in child_by_project.get(entity.id, []):
            if task_id in latest_update:
                candidates.append(latest_update[task_id][0])
            if task_id in latest_event:
                candidates.append(latest_event[task_id])
        candidates = [c for c in candidates if c is not None]
        reference = max(candidates)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        result[entity.id] = max(0, (now - reference).days)
    return result


def _latest_event_at(entity_ids):
    """Map entity_id -> created_at of its most recent non-creation
    EntityEvent (the `created` event is already covered by `created_at`)."""
    if not entity_ids:
        return {}
    rows = (
        db.session.query(EntityEvent.entity_id, func.max(EntityEvent.created_at))
        .filter(EntityEvent.entity_id.in_(entity_ids), EntityEvent.event_type != "created")
        .group_by(EntityEvent.entity_id)
        .all()
    )
    return dict(rows)


def _blocking_impact_counts(entities):
    """Map entity_id -> count of other active, non-done entities it blocks
    (via a `blocks` relationship link). Batched (no N+1)."""
    if not entities:
        return {}
    entity_ids = [e.id for e in entities]
    rows = (
        db.session.query(EntityLink.source_entity_id, func.count(EntityLink.target_entity_id))
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.source_entity_id.in_(entity_ids),
            EntityLink.relationship_type == "blocks",
            Entity.lifecycle == "active",
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .group_by(EntityLink.source_entity_id)
        .all()
    )
    return {source_id: count for source_id, count in rows}


def _agent_event_item(event):
    entity = event.entity
    category = "review_action" if event.event_type in {"suggestion_accepted", "suggestion_dismissed"} else "auto_applied"
    return {
        "id": event.id,
        "kind": "event",
        "category": category,
        "event_type": event.event_type,
        "actor": event.actor,
        "entity": _audit_entity(entity),
        "confidence": event.confidence,
        "reason": event.reason,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _agent_suggestion_item(suggestion):
    return {
        "id": suggestion.id,
        "kind": "suggestion",
        "category": "suggested",
        "event_type": suggestion.suggestion_type,
        "actor": "agent:v4-capture",
        "entity": _audit_entity(suggestion.source_entity),
        "confidence": suggestion.confidence,
        "reason": suggestion.reason,
        "created_at": suggestion.created_at.isoformat() if suggestion.created_at else None,
    }


def _agent_failed_note_item(note):
    return {
        "id": f"failed:{note.id}",
        "kind": "failed_note",
        "category": "failed",
        "event_type": "ai_failed",
        "actor": "agent:v4-capture",
        "entity": _audit_entity(note),
        "confidence": None,
        "reason": "capture extraction failed",
        "created_at": note.updated_at.isoformat() if note.updated_at else None,
    }


def _audit_entity(entity):
    if entity is None:
        return None
    return {"id": entity.id, "type": entity.type, "title": entity.title}


def _clear_review_resolution(entity):
    ai_meta = dict(entity.ai_meta or {})
    changed = False
    for key in ("review_state", "reviewed_at", "review_resolution"):
        if key in ai_meta:
            ai_meta.pop(key, None)
            changed = True
    if changed:
        entity.ai_meta = ai_meta
        flag_modified(entity, "ai_meta")


def _mark_review_resolved(entity):
    ai_meta = dict(entity.ai_meta or {})
    ai_meta["review_state"] = "resolved"
    ai_meta["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    ai_meta["review_resolution"] = "no_change_needed"
    entity.ai_meta = ai_meta
    flag_modified(entity, "ai_meta")


def _merge_entities(loser, survivor, actor="user"):
    """Re-point all references from loser to survivor and tombstone the loser.

    Returns a summary dict of what moved. Caller commits.
    """
    loser_snapshot = loser.to_dict()
    links_moved = 0
    links_dropped = 0

    # Re-point links in both directions. Links that would become self-links
    # or duplicate an existing survivor link are dropped (the survivor
    # relationship already exists or is meaningless).
    for link in EntityLink.query.filter_by(source_entity_id=loser.id).all():
        if link.target_entity_id == survivor.id or EntityLink.query.filter_by(
            source_entity_id=survivor.id,
            target_entity_id=link.target_entity_id,
            relationship_type=link.relationship_type,
        ).first():
            db.session.delete(link)
            links_dropped += 1
        else:
            link.source_entity_id = survivor.id
            links_moved += 1
    db.session.flush()
    for link in EntityLink.query.filter_by(target_entity_id=loser.id).all():
        if link.source_entity_id == survivor.id or EntityLink.query.filter_by(
            source_entity_id=link.source_entity_id,
            target_entity_id=survivor.id,
            relationship_type=link.relationship_type,
        ).first():
            db.session.delete(link)
            links_dropped += 1
        else:
            link.target_entity_id = survivor.id
            links_moved += 1
    db.session.flush()

    # Tags: union onto the survivor.
    survivor_tag_ids = {et.tag_id for et in EntityTag.query.filter_by(entity_id=survivor.id).all()}
    tags_moved = 0
    for entity_tag in EntityTag.query.filter_by(entity_id=loser.id).all():
        tag_id = entity_tag.tag_id
        db.session.delete(entity_tag)
        if tag_id not in survivor_tag_ids:
            db.session.add(EntityTag(entity_id=survivor.id, tag_id=tag_id))
            tags_moved += 1
    db.session.flush()

    # Pending suggestions and jobs that reference the loser follow the survivor.
    for suggestion in AiSuggestion.query.filter_by(status="pending").all():
        changed = False
        if suggestion.source_entity_id == loser.id:
            suggestion.source_entity_id = survivor.id
            changed = True
        payload = dict(suggestion.payload or {})
        for key in ("target_entity_id", "source_entity_id"):
            if payload.get(key) == loser.id:
                payload[key] = survivor.id
                changed = True
        if changed:
            suggestion.payload = payload
            flag_modified(suggestion, "payload")
    for job in Job.query.filter_by(entity_id=loser.id, status="pending").all():
        job.entity_id = survivor.id
        payload = dict(job.payload or {})
        if payload.get("entity_id") == loser.id:
            payload["entity_id"] = survivor.id
            job.payload = payload
            flag_modified(job, "payload")

    # Backfill scalar fields the survivor is missing — never overwrite.
    fields_copied = []
    for field in ("content", "due_at", "follow_up_at", "reference_url"):
        if not getattr(survivor, field, None) and getattr(loser, field, None):
            setattr(survivor, field, getattr(loser, field))
            fields_copied.append(field)

    # The loser must stop matching future captures: drop its chunks and
    # tombstone it. All read paths already exclude lifecycle="deleted".
    from models import EntityChunk
    EntityChunk.query.filter_by(entity_id=loser.id).delete()
    loser.lifecycle = "deleted"
    properties = dict(loser.properties or {})
    properties["merged_into"] = survivor.id
    loser.properties = properties
    flag_modified(loser, "properties")

    survivor.updated_at = datetime.now(timezone.utc)

    summary = {
        "merged_from_id": loser.id,
        "merged_into_id": survivor.id,
        "links_moved": links_moved,
        "links_dropped": links_dropped,
        "tags_moved": tags_moved,
        "fields_copied": fields_copied,
    }
    _write_event(
        survivor,
        "merged",
        old_value={"merged_from": loser_snapshot},
        new_value=summary,
        actor=actor,
        reason=f"merged duplicate '{loser_snapshot.get('title')}'",
    )
    _write_event(
        loser,
        "merged_into",
        old_value={"lifecycle": loser_snapshot["lifecycle"]},
        new_value={"lifecycle": "deleted", "merged_into": survivor.id},
        actor=actor,
    )
    _queue_embed_job(survivor.id, "entity_merge")
    return summary


TYPE_CONVERSIONS = {("project", "task"), ("task", "project")}
CONVERSION_STATUS_MAP = {
    ("project", "task"): {"active": "open", "on_hold": "waiting", "completed": "done", "cancelled": "cancelled"},
    ("task", "project"): {"open": "active", "in_progress": "active", "waiting": "on_hold", "blocked": "on_hold", "done": "completed", "cancelled": "cancelled"},
}


CAPTURE_CHANGE_EVENT_TYPES = {
    "created",
    "ai_updated",
    "relationship_added",
    "activity_update_added",
}


DEFAULT_ACTIVITY_UPDATES_PAGE_SIZE = 30
MAX_ACTIVITY_UPDATES_PAGE_SIZE = 100
DETAIL_ACTIVITY_UPDATES_LIMIT = 5
ACTIVITY_UPDATE_DEDUP_HOURS = 24
NEAR_DUPLICATE_ACTIVITY_UPDATE_THRESHOLD = 0.85


def _normalize_activity_update_content(content):
    text = (content or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def _activity_update_content_tokens(content):
    return set(re.findall(r"[a-z0-9]+", _normalize_activity_update_content(content)))


def _activity_update_content_similarity(left, right):
    tokens_left = _activity_update_content_tokens(left)
    tokens_right = _activity_update_content_tokens(right)
    if not tokens_left or not tokens_right:
        return 0.0
    if tokens_left == tokens_right:
        return 1.0
    union = tokens_left | tokens_right
    return len(tokens_left & tokens_right) / len(union)


def _recent_activity_update_notes(target_id, hours=ACTIVITY_UPDATE_DEDUP_HOURS):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return (
        Entity.query.join(
            EntityLink,
            (EntityLink.source_entity_id == Entity.id) & (EntityLink.target_entity_id == target_id),
        )
        .filter(
            Entity.type == "note",
            Entity.source == "activity_update",
            EntityLink.relationship_type == "activity_update",
            Entity.updated_at >= cutoff,
        )
        .order_by(Entity.updated_at.desc())
        .all()
    )


def _find_near_duplicate_activity_update(target, content):
    for note in _recent_activity_update_notes(target.id):
        if (note.content or "").strip() == (content or "").strip():
            continue
        if _activity_update_content_similarity(note.content, content) >= NEAR_DUPLICATE_ACTIVITY_UPDATE_THRESHOLD:
            return note
    return None


def _create_activity_update_note(target, content, actor="user", confidence=None, evidence=None, source_note_id=None, change_batch_id=None):
    """Create (or reuse) an activity-update note linked to `target`.

    Returns (note, created, skip_reason). skip_reason is set when created is
    False: ``exact_duplicate`` or ``near_duplicate``.
    """
    existing = (
        Entity.query.join(
            EntityLink,
            (EntityLink.source_entity_id == Entity.id) & (EntityLink.target_entity_id == target.id),
        )
        .filter(
            Entity.type == "note",
            Entity.source == "activity_update",
            EntityLink.relationship_type == "activity_update",
            Entity.content == content,
            Entity.updated_at >= datetime.now(timezone.utc) - timedelta(hours=ACTIVITY_UPDATE_DEDUP_HOURS),
        )
        .first()
    )
    if existing is not None:
        return existing, False, "exact_duplicate"

    near_duplicate = _find_near_duplicate_activity_update(target, content)
    if near_duplicate is not None:
        return near_duplicate, False, "near_duplicate"

    note = Entity(
        type="note",
        title=_activity_update_title(target),
        content=content,
        status="active",
        source="activity_update",
        ai_status="done",
    )
    db.session.add(note)
    db.session.flush()

    link = EntityLink(
        source_entity_id=note.id,
        target_entity_id=target.id,
        relationship_type="activity_update",
        source="activity_update",
    )
    db.session.add(link)

    target.updated_at = datetime.now(timezone.utc)
    db.session.flush()

    event_source_note_id = source_note_id or note.id
    _write_event(
        target,
        "activity_update_added",
        new_value={"note_id": note.id, "content_preview": content[:120]},
        actor=actor,
        confidence=confidence,
        reason=evidence,
        source_note_id=event_source_note_id,
        change_batch_id=change_batch_id,
    )
    _refresh_delegation_cadence(target, source_note_id=event_source_note_id, actor=actor, change_batch_id=change_batch_id)
    if target.type == "task":
        _touch_parent_projects(target)
    return note, True, None


def _refresh_delegation_cadence(target, source_note_id=None, actor="user", change_batch_id=None):
    """If `target` is a task delegated to a non-owner person, push follow_up_at
    forward by the delegation cadence following an activity update."""
    if target.type != "task":
        return
    assignee_link = (
        EntityLink.query.filter_by(
            source_entity_id=target.id,
            relationship_type="assigned_to",
        )
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(Entity.type == "person")
        .first()
    )
    if assignee_link is None:
        return
    person = db.session.get(Entity, assignee_link.target_entity_id)
    if person is None or _is_owner(person.title, person.id):
        return
    old_follow_up = target.follow_up_at
    cadence_days = _delegation_cadence_days(person.id)
    target.follow_up_at = _add_working_days(datetime.now(timezone.utc), cadence_days)
    _write_event(
        target,
        "ai_updated",
        old_value={"follow_up_at": old_follow_up.isoformat() if old_follow_up else None},
        new_value={"follow_up_at": target.follow_up_at.isoformat()},
        actor=actor,
        reason="delegation cadence refresh",
        source_note_id=source_note_id,
        change_batch_id=change_batch_id,
    )


def _pin_reason_with_context(reason, pin_reason):
    if reason and pin_reason:
        return f"{reason}; {pin_reason}"
    return pin_reason or reason


def _record_relationship_pin_event(
    entity,
    relationship_type,
    actor,
    reason,
    confidence=None,
    source_note_id=None,
    change_batch_id=None,
    on_behalf=None,
):
    pin_field = relationship_pin_field(relationship_type)
    if not pin_field:
        return False
    old_snapshot = entity.to_dict()
    if not record_pin(entity, pin_field, actor, on_behalf=on_behalf):
        return False
    _write_event(
        entity,
        "updated",
        old_value={"pinned_fields": old_snapshot.get("pinned_fields", [])},
        new_value={"pinned_fields": entity.to_dict().get("pinned_fields", []), "field": pin_field},
        actor=actor,
        confidence=confidence,
        reason=reason,
        source_note_id=source_note_id,
        change_batch_id=change_batch_id,
    )
    return True


def _apply_activity_update_policy(note, target, content, extraction, suggestions, actor="agent:activity-update", change_batch_id=None):
    """Shared Add-update policy: status auto-apply/suggest, follow-up routing
    (sq-02 semantics), and spin-off task suggestions.

    ``note`` is the note suggestions and events are sourced from (the activity
    update note on the endpoint path, the capture note on the intent-routed
    capture path). Appends to ``suggestions`` in place and returns the
    "extracted" summary dict used in API responses.
    """
    extracted_tasks = []
    extracted_status = extraction.get("status")
    status_confidence = extraction.get("confidence", 0.0) or 0.0
    status_auto_applied = False

    # ── Status change ───────────────────────────────────────────────────
    # SQ-09: status auto-apply requires explicit status language in the
    # update text in addition to the confidence tiebreaker. Without the
    # structural signal the change becomes a reviewable suggestion.
    if (
        extracted_status
        and extracted_status in VALID_STATUS.get(target.type, set())
        and extracted_status != target.status
        and _status_change_is_explicit(content, extracted_status)
    ):
        if status_confidence >= AUTO_APPLY_CONFIDENCE:
            old_status = target.status
            target.status = extracted_status
            status_auto_applied = True
            _write_event(
                target,
                "ai_updated",
                old_value={"status": old_status},
                new_value={"status": extracted_status},
                actor=actor,
                confidence=status_confidence,
                reason="extracted from activity update",
                source_note_id=note.id,
                change_batch_id=change_batch_id,
            )
            _queue_embed_job(target.id, "activity_update_auto_status")
        else:
            suggestion = _create_suggestion(
                note,
                suggestion_type=f"update_{target.type}",
                operation_type="update_entity",
                payload={
                    "target_entity_id": target.id,
                    "target_type": target.type,
                    "title": target.title,
                    "fields": {"status": extracted_status},
                    "evidence": content[:200],
                },
                confidence=status_confidence,
                reason=f"extracted status from activity update: {extracted_status}",
            )
            if suggestion:
                suggestions.append(suggestion.to_dict())

    # ── Follow-up date ──────────────────────────────────────────────────
    explicit_follow_up = extraction.get("follow_up_at")
    task_candidates = extraction.get("tasks") or []

    closing_statuses = (
        {"done", "cancelled"} if target.type == "task" else {"completed", "cancelled"}
    )
    target_is_closing = (
        extracted_status in closing_statuses
        or target.status in closing_statuses
    )
    # Trust the extractor's own placement of the follow-up date: the prompt already
    # puts it on the target when it stays open, and on spin-off task payloads when
    # the target is closing. New task candidates alone must not reroute it —
    # only a closing status suppresses applying the top-level date to the target.
    apply_follow_up_to_target = bool(explicit_follow_up and not target_is_closing)
    route_follow_up_to_tasks = bool(explicit_follow_up and task_candidates and target_is_closing)

    if apply_follow_up_to_target:
        old_follow_up = target.follow_up_at
        target.follow_up_at = _parse_iso_date(explicit_follow_up)
        _write_event(
            target,
            "ai_updated",
            old_value={"follow_up_at": old_follow_up.isoformat() if old_follow_up else None},
            new_value={"follow_up_at": target.follow_up_at.isoformat()},
            actor=actor,
            reason="extracted from activity update",
            source_note_id=note.id,
            change_batch_id=change_batch_id,
        )

    # ── New tasks from update content ────────────────────────────────────
    for task_candidate in task_candidates:
        confidence = task_candidate.get("confidence", 0.0)
        task_follow_up = task_candidate.get("follow_up_at")
        task_due_at = task_candidate.get("due_at")
        if route_follow_up_to_tasks and explicit_follow_up and not task_follow_up and not task_due_at:
            task_follow_up = explicit_follow_up

        suggestion = _create_suggestion(
            note,
            suggestion_type="create_task",
            operation_type="create_new_entity",
            payload={
                "type": "task",
                "title": task_candidate.get("title"),
                "content": task_candidate.get("content"),
                "due_at": task_due_at,
                "follow_up_at": task_follow_up,
                "assigned_to": task_candidate.get("assigned_to"),
                "evidence": task_candidate.get("title"),
                "target_entity_id": target.id,
                "relationship_type": "derived_from",
            },
            confidence=confidence,
            reason=f"extracted from activity update: {task_candidate.get('title', '')[:80]}",
        )
        if suggestion:
            suggestions.append(suggestion.to_dict())
            extracted_tasks.append({
                "title": task_candidate.get("title"),
                "confidence": confidence,
                "auto_created": False,
                "suggestion_id": suggestion.id,
            })

    return {
        "status": extracted_status,
        "status_auto_applied": status_auto_applied,
        "follow_up_at": explicit_follow_up,
        "follow_up_auto_set": apply_follow_up_to_target,
        "tasks": extracted_tasks,
    }


VALID_DISMISS_REASONS = {
    "not a task",
    "not mine",
    "duplicate",
    "wrong target",
    "other",
}


def _entity_query():
    return Entity.query.options(
        selectinload(Entity.entity_tags).selectinload(EntityTag.tag),
        selectinload(Entity.incoming_links),
        selectinload(Entity.outgoing_links),
    )


def _load_entity(entity_id):
    return _entity_query().filter(Entity.id == entity_id).first()


def _relationship_detail_sections(entity):
    links = (
        EntityLink.query.filter(
            (EntityLink.source_entity_id == entity.id) | (EntityLink.target_entity_id == entity.id)
        )
        .order_by(EntityLink.created_at.asc())
        .all()
    )
    related_entities = _entity_map_for_links(entity.id, links)
    builders = {
        "task": _task_detail_sections,
        "project": _project_detail_sections,
        "area": _area_detail_sections,
        "note": _note_detail_sections,
        "person": _person_detail_sections,
        "resource": _resource_detail_sections,
    }
    return builders[entity.type](entity, links, related_entities)


def _task_detail_sections(entity, links, related_entities):
    return [
        _section("project", "Project", _link_items(entity, links, related_entities, "outgoing", {"parent"}, {"project"})),
        _section("area", "Area", _link_items(entity, links, related_entities, "outgoing", {"parent"}, {"area"})),
        _section("people", "People", _link_items(entity, links, related_entities, "outgoing", {"assigned_to"}, {"person"})),
        _section("people_mentioned", "People Mentioned", _link_items(entity, links, related_entities, "outgoing", {"mentions"}, {"person"})),
        _section("source_notes", "Source Notes", _link_items(entity, links, related_entities, "outgoing", {"derived_from"}, {"note"})),
        _section("related_notes", "Related Notes", _link_items(entity, links, related_entities, "both", {"related"}, {"note"})),
        _section("resources", "Resources", _link_items(entity, links, related_entities, "outgoing", {"references", "related"}, {"resource"})),
        _section("blocking", "Blocking / Blocked By", _link_items(entity, links, related_entities, "both", {"blocks"}, {"task"})),
        _section("related_tasks", "Related Tasks", _link_items(entity, links, related_entities, "both", {"related"}, {"task"})),
        _activity_updates_section(entity.id),
    ]


def _activity_updates_order():
    return (Entity.updated_at.desc(), Entity.id.desc())


def _activity_updates_query(entity_id):
    return (
        Entity.query.join(
            EntityLink,
            (EntityLink.source_entity_id == Entity.id) & (EntityLink.target_entity_id == entity_id),
        )
        .filter(
            Entity.type == "note",
            Entity.source == "activity_update",
            EntityLink.relationship_type == "activity_update",
            Entity.lifecycle == "active",
        )
    )


def _serialize_activity_update(note):
    return {
        "id": note.id,
        "title": note.title,
        "content": note.content or "",
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


def _activity_updates_section(entity_id, limit=DETAIL_ACTIVITY_UPDATES_LIMIT):
    base_query = _activity_updates_query(entity_id)
    total = base_query.count()
    notes = base_query.order_by(*_activity_updates_order()).limit(limit).all()
    return {
        "key": "activity_updates",
        "title": "Activity",
        "items": [_serialize_activity_update(note) for note in notes],
        "meta": {"total": total, "limit": limit, "offset": 0},
    }


def _fetch_activity_updates(entity_id, limit=DETAIL_ACTIVITY_UPDATES_LIMIT):
    """Fetch recent activity update notes for an entity."""
    notes = _activity_updates_query(entity_id).order_by(*_activity_updates_order()).limit(limit).all()
    return [_serialize_activity_update(note) for note in notes]


def _project_detail_sections(entity, links, related_entities):
    return [
        _section("area", "Area", _link_items(entity, links, related_entities, "outgoing", {"parent"}, {"area"})),
        _section(
            "open_tasks",
            "Open Tasks",
            _link_items(entity, links, related_entities, "incoming", {"parent"}, {"task"}, exclude_statuses={"done", "cancelled"}),
        ),
        _section(
            "completed_tasks",
            "Completed Tasks",
            _link_items(entity, links, related_entities, "incoming", {"parent"}, {"task"}, statuses={"done"}),
        ),
        _section("notes", "Notes", _link_items(entity, links, related_entities, "both", {"related", "mentions", "references"}, {"note"})),
        _section("resources", "Resources", _link_items(entity, links, related_entities, "both", {"references", "related"}, {"resource"})),
        _section("people", "People", _link_items(entity, links, related_entities, "both", {"assigned_to", "mentions", "related"}, {"person"})),
        _section("related_projects", "Related Projects", _link_items(entity, links, related_entities, "both", {"related"}, {"project"})),
        _section("blocked_by_blocks", "Blocked By / Blocks", _link_items(entity, links, related_entities, "both", {"blocks"}, {"project"})),
        _activity_updates_section(entity.id),
    ]


def _area_detail_sections(entity, links, related_entities):
    return [
        _section("projects", "Projects", _link_items(entity, links, related_entities, "incoming", {"parent", "related"}, {"project"})),
        _section("tasks", "Tasks", _link_items(entity, links, related_entities, "incoming", {"parent", "related"}, {"task"})),
        _section("notes", "Notes", _link_items(entity, links, related_entities, "both", {"related", "mentions"}, {"note"})),
        _section("resources", "Resources", _link_items(entity, links, related_entities, "both", {"references", "related"}, {"resource"})),
        _section("people", "People", _link_items(entity, links, related_entities, "both", {"mentions", "assigned_to", "related"}, {"person"})),
        _activity_updates_section(entity.id),
    ]


def _note_detail_sections(entity, links, related_entities):
    return [
        # For activity-update notes: the task/project/area this note is an
        # update on. Standard {entity, relationship} item shape so the UI can
        # navigate from the update back to its target.
        _section("update_on", "Update on", _link_items(entity, links, related_entities, "outgoing", {"activity_update"}, {"task", "project", "area"})),
        _section("projects", "Projects", _link_items(entity, links, related_entities, "outgoing", {"related", "mentions"}, {"project"})),
        _section("areas", "Areas", _link_items(entity, links, related_entities, "outgoing", {"related", "mentions"}, {"area"})),
        _section("people_mentioned", "People Mentioned", _link_items(entity, links, related_entities, "outgoing", {"mentions"}, {"person"})),
        _section("derived_tasks", "Derived Tasks", _link_items(entity, links, related_entities, "incoming", {"derived_from"}, {"task"})),
        _section("referenced_resources", "Referenced Resources", _link_items(entity, links, related_entities, "outgoing", {"references"}, {"resource"})),
        _section("related_notes", "Related Notes", _link_items(entity, links, related_entities, "both", {"related"}, {"note"})),
    ]


def _person_detail_sections(entity, links, related_entities):
    return [
        _section("assigned_tasks", "Assigned Tasks", _link_items(entity, links, related_entities, "incoming", {"assigned_to"}, {"task"})),
        _section("mentioned_in_notes", "Mentioned In Notes", _link_items(entity, links, related_entities, "incoming", {"mentions"}, {"note"})),
        _section("projects", "Projects", _link_items(entity, links, related_entities, "both", {"assigned_to", "mentions", "related"}, {"project"})),
        _section("resources", "Resources", _link_items(entity, links, related_entities, "both", {"references", "related"}, {"resource"})),
        _section("related_people", "Related People", _link_items(entity, links, related_entities, "both", {"related"}, {"person"})),
    ]


def _resource_detail_sections(entity, links, related_entities):
    return [
        _section("referenced_by_notes", "Referenced By Notes", _link_items(entity, links, related_entities, "incoming", {"references"}, {"note"})),
        _section("projects", "Projects", _link_items(entity, links, related_entities, "both", {"references", "related"}, {"project"})),
        _section("tasks", "Tasks", _link_items(entity, links, related_entities, "both", {"references", "related"}, {"task"})),
        _section("areas", "Areas", _link_items(entity, links, related_entities, "both", {"references", "related"}, {"area"})),
        _section("people", "People", _link_items(entity, links, related_entities, "both", {"references", "related"}, {"person"})),
        _section("related_resources", "Related Resources", _link_items(entity, links, related_entities, "both", {"related"}, {"resource"})),
    ]


def _section(key, title, items):
    return {"key": key, "title": title, "items": items}


def _link_items(entity, links, related_entities, direction, relationship_types, related_types, statuses=None, exclude_statuses=None):
    items = []
    for link in links:
        related_entity, resolved_direction = _related_entity_for_link(entity, link, related_entities, direction)
        if related_entity is None or related_entity.lifecycle == "deleted":
            continue
        if link.relationship_type not in relationship_types:
            continue
        if related_entity.type not in related_types:
            continue
        if statuses is not None and related_entity.status not in statuses:
            continue
        if exclude_statuses is not None and related_entity.status in exclude_statuses:
            continue
        item = {
            "entity": related_entity.to_dict(),
            "relationship": link.to_dict(),
            "direction": resolved_direction,
        }
        if related_entity.lifecycle == "redacted":
            item["citation_state"] = "redacted"
            item["citation_label"] = REDACTED_CITATION_LABEL
        items.append(item)
    return items


def _related_entity_for_link(entity, link, related_entities, direction):
    if direction in {"outgoing", "both"} and link.source_entity_id == entity.id:
        return related_entities.get(link.target_entity_id), "outgoing"
    if direction in {"incoming", "both"} and link.target_entity_id == entity.id:
        return related_entities.get(link.source_entity_id), "incoming"
    return None, None


def _entity_map_for_links(entity_id, links):
    related_ids = {
        link.target_entity_id if link.source_entity_id == entity_id else link.source_entity_id
        for link in links
    }
    if not related_ids:
        return {}
    related_entities = _entity_query().filter(Entity.id.in_(related_ids)).all()
    _attach_project_task_counts(related_entities)
    return {related.id: related for related in related_entities}


def _attach_project_task_counts(entities):
    project_ids = [entity.id for entity in entities if entity.type == "project"]
    if not project_ids:
        return

    counts_by_project = {project_id: {"open": 0, "total": 0} for project_id in project_ids}
    rows = (
        db.session.query(EntityLink.target_entity_id, Entity.status)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "parent",
            EntityLink.target_entity_id.in_(project_ids),
            Entity.type == "task",
            Entity.lifecycle == "active",
        )
        .all()
    )
    for project_id, status in rows:
        counts = counts_by_project[project_id]
        counts["total"] += 1
        if status in OPEN_TASK_STATUSES:
            counts["open"] += 1

    for entity in entities:
        if entity.type == "project":
            entity._task_counts = counts_by_project.get(entity.id, {"open": 0, "total": 0})


def _attach_project_context(entities):
    """Attach parent area refs to project rows."""
    project_ids = [entity.id for entity in entities if entity.type == "project"]
    if not project_ids:
        return

    project_areas = {project_id: [] for project_id in project_ids}
    rows = (
        db.session.query(EntityLink.source_entity_id, EntityLink.id, Entity.id, Entity.title)
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.relationship_type == "parent",
            EntityLink.source_entity_id.in_(project_ids),
            Entity.type == "area",
            Entity.lifecycle == "active",
        )
        .all()
    )
    for project_id, rel_id, area_id, area_title in rows:
        project_areas.setdefault(project_id, []).append({"id": area_id, "title": area_title, "relationship_id": rel_id})

    for entity in entities:
        if entity.type == "project":
            entity._areas = project_areas.get(entity.id, [])


def _attach_task_context(entities):
    """Attach parent project/area refs and assignee refs to task rows."""
    task_ids = [entity.id for entity in entities if entity.type == "task"]
    if not task_ids:
        return

    task_context = {
        task_id: {"projects": [], "areas": [], "people": []}
        for task_id in task_ids
    }
    parent_rows = (
        db.session.query(EntityLink.source_entity_id, EntityLink.id, Entity.id, Entity.title, Entity.type)
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.relationship_type == "parent",
            EntityLink.source_entity_id.in_(task_ids),
            Entity.type.in_(("project", "area")),
            Entity.lifecycle == "active",
        )
        .all()
    )
    for task_id, rel_id, target_id, target_title, target_type in parent_rows:
        bucket = task_context.setdefault(task_id, {"projects": [], "areas": [], "people": []})
        if target_type == "project":
            bucket["projects"].append({"id": target_id, "title": target_title, "relationship_id": rel_id})
        elif target_type == "area":
            bucket["areas"].append({"id": target_id, "title": target_title, "relationship_id": rel_id})

    assignee_rows = (
        db.session.query(EntityLink.source_entity_id, Entity.id, Entity.title)
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.relationship_type == "assigned_to",
            EntityLink.source_entity_id.in_(task_ids),
            Entity.type == "person",
            Entity.lifecycle == "active",
        )
        .all()
    )
    for task_id, person_id, person_title in assignee_rows:
        bucket = task_context.setdefault(task_id, {"projects": [], "areas": [], "people": []})
        bucket["people"].append({"id": person_id, "title": person_title})

    for entity in entities:
        if entity.type == "task":
            context = task_context.get(entity.id, {"projects": [], "areas": [], "people": []})
            entity._projects = context["projects"]
            entity._areas = context["areas"]
            entity._people = context["people"]


def _enrich_search_results_with_task_context(results):
    """Re-serialize task hits in search results with parent/assignee context."""
    task_ids = [
        row["entity"]["id"]
        for row in results
        if row.get("entity", {}).get("type") == "task" and row["entity"].get("id")
    ]
    if not task_ids:
        return results

    entities = Entity.query.filter(Entity.id.in_(task_ids)).all()
    _attach_task_context(entities)
    by_id = {entity.id: entity.to_dict() for entity in entities}
    enriched = []
    for row in results:
        entity = row.get("entity") or {}
        entity_id = entity.get("id")
        if entity.get("type") == "task" and entity_id in by_id:
            enriched.append({**row, "entity": by_id[entity_id]})
        else:
            enriched.append(row)
    return enriched


def _attach_compact_link_counts(entities):
    """Attach lightweight note/task/project link counts to compact list rows."""
    compact_entities = [entity for entity in entities if entity.type in COMPACT_LINK_COUNT_RULES]
    if not compact_entities:
        return

    related_ids = set()
    links_by_entity_id = {}
    for entity in compact_entities:
        links = [*entity.incoming_links, *entity.outgoing_links]
        links_by_entity_id[entity.id] = links
        for link in links:
            related_ids.add(link.source_entity_id if link.target_entity_id == entity.id else link.target_entity_id)

    related_entities = {}
    if related_ids:
        related_entities = {
            related.id: related
            for related in Entity.query.filter(
                Entity.id.in_(related_ids),
                Entity.lifecycle != "deleted",
            ).all()
        }

    for entity in compact_entities:
        counts = {"notes": 0, "tasks": 0, "projects": 0}
        for bucket, (direction, relationship_types, related_types) in COMPACT_LINK_COUNT_RULES[entity.type].items():
            items = _link_items(
                entity,
                links_by_entity_id[entity.id],
                related_entities,
                direction,
                relationship_types,
                related_types,
            )
            counts[bucket] = len({item["entity"]["id"] for item in items})
        entity._linked_counts = counts


def _replace_tags(entity, tag_names):
    EntityTag.query.filter_by(entity_id=entity.id).delete(synchronize_session=False)
    for raw_name in tag_names:
        name = str(raw_name).strip()
        if not name:
            continue
        tag = Tag.query.filter_by(name=name).first()
        if tag is None:
            tag = Tag(name=name)
            db.session.add(tag)
            db.session.flush()
        db.session.add(EntityTag(entity_id=entity.id, tag_id=tag.id))


def _add_tag(entity, raw_name):
    name = str(raw_name or "").strip()
    if not name:
        return None
    tag = Tag.query.filter_by(name=name).first()
    if tag is None:
        tag = Tag(name=name)
        db.session.add(tag)
        db.session.flush()
    if EntityTag.query.filter_by(entity_id=entity.id, tag_id=tag.id).first() is None:
        db.session.add(EntityTag(entity_id=entity.id, tag_id=tag.id))
    return tag


def _write_event(entity, event_type, old_value=None, new_value=None, actor="user", confidence=None, reason=None, source_note_id=None, change_batch_id=None):
    db.session.add(
        EntityEvent(
            entity_id=entity.id,
            event_type=event_type,
            actor=actor,
            old_value=old_value,
            new_value=new_value,
            confidence=confidence,
            reason=reason,
            source_note_id=source_note_id,
            change_batch_id=change_batch_id,
        )
    )


def _validate_status(entity_type, status):
    if status not in VALID_STATUS[entity_type]:
        return _error(f"invalid status for {entity_type}: {status}")
    return None


def _is_relationship_compatible(relationship_type, source_type, target_type):
    allowed = RELATIONSHIP_COMPATIBILITY.get(relationship_type, {})
    return target_type in allowed.get(source_type, set())


def _validate_lifecycle(lifecycle):
    if lifecycle not in VALID_LIFECYCLE:
        return _error(f"invalid lifecycle: {lifecycle}")
    return None


def _person_has_open_assigned_tasks(person_id):
    return (
        Entity.query.join(EntityLink, EntityLink.source_entity_id == Entity.id)
        .filter(
            EntityLink.target_entity_id == person_id,
            EntityLink.relationship_type == "assigned_to",
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_ASSIGNED_TASK_STATUSES),
        )
        .count()
        > 0
    )


def _validate_properties(properties):
    if not isinstance(properties, dict):
        return _error("properties must be an object")
    bad_key = _find_relationship_property_key(properties)
    if bad_key:
        return _error(f"properties must not contain relationship IDs: {bad_key}")
    return None


def _find_relationship_property_key(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in RELATIONSHIP_PROPERTY_KEYS or key.endswith("_id") or key.endswith("_ids"):
                return key
            found = _find_relationship_property_key(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_relationship_property_key(child)
            if found:
                return found
    return None


def _parse_datetime(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"invalid datetime: {value}") from None


def _parse_datetime_or_error(value):
    try:
        return _parse_datetime(value), None
    except ValueError as exc:
        return None, _error(str(exc))


def _error(message, status=400):
    return jsonify({"error": message}), status


def _title_from_content(content):
    first_line = content.splitlines()[0].strip()
    return first_line[:80] if first_line else "Untitled note"


def _activity_update_title(target):
    """Deterministic title for an activity-update note.

    An update's identity is its target plus when it happened; a truncated
    first sentence ("There was no update on this during the week. Will ch…")
    is unreadable in note lists.
    """
    target_title = title_or_placeholder(target).strip()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"Update: {target_title[:130]} ({today})"


def _capture_thread_id_from_data(data):
    thread_id = _clean_text((data or {}).get("thread_id"))
    if not thread_id:
        return None
    entity = db.session.get(Entity, thread_id)
    if entity is None or entity.lifecycle == "deleted":
        return None
    return thread_id


def _capture_thread_entity_dict(thread_id):
    if not thread_id:
        return None
    entity = db.session.get(Entity, thread_id)
    if entity is None or entity.lifecycle == "deleted":
        return None
    from services.v4_extraction import _thread_entity_dict
    return _thread_entity_dict(entity)


def _run_basic_capture_extraction(note, mode, thread_id=None):
    from services.v4_extraction import extract_capture_candidates

    return extract_capture_candidates(
        note.content or "",
        mode=mode,
        exclude_note_id=note.id,
        thread_entity=_capture_thread_entity_dict(thread_id),
    )


def _extract_decision_candidates(note, thread_id=None):
    from api import v4_entities as _v4e
    """Extract explicit-commitment decision candidates from a note.

    Returns candidates with a resolved thread_id (linked project/person, capture
    thread attachment, or the note itself as a fallback) and a high confidence
    value. These are always turned into reviewable suggestions, never auto-created.
    """
    from services.v4_decisions import extract_decisions_from_note

    candidates = extract_decisions_from_note(note.content or "")
    if not candidates:
        return []
    resolved_thread_id = thread_id or _v4e._decision_thread_id_for_note(note)
    for candidate in candidates:
        candidate["thread_id"] = resolved_thread_id
        candidate["confidence"] = 0.9
    return candidates


def _decision_thread_id_for_note(note):
    """Pick the most relevant project/person thread for a decision.

    Falls back to the note itself when no project/person is linked.
    """
    links = EntityLink.query.filter(
        EntityLink.source_entity_id == note.id,
        EntityLink.relationship_type.in_(["parent", "related", "mentions", "assigned_to"]),
    ).all()
    for link in links:
        target = db.session.get(Entity, link.target_entity_id)
        if target is not None and target.type in {"project", "person"} and target.lifecycle == "active":
            return target.id
    return note.id


def _valid_decided_by(value):
    if value == "user":
        return True
    if isinstance(value, str) and value.startswith("agent:") and len(value) > 6:
        return True
    return False


def _apply_capture_extraction_metadata(note, extraction, applied_changes):
    """Apply note-level extraction output: title, summary, intent, tags.

    These come from the already-completed extraction call, so applying them
    costs no extra LLM spend regardless of which pipeline the capture routes
    through afterwards.
    """
    summary = _clean_text(extraction.get("summary"))
    ai_title = _clean_text(extraction.get("title"))
    ai_meta = dict(note.ai_meta or {})
    title_auto = ai_meta.get("title_auto", False)

    if ai_title and title_auto and note.type == "note":
        old_title = note.title
        note.title = ai_title[:160]
        applied_changes.append({"type": "title_updated", "title": note.title})
        _write_event(
            note,
            "ai_updated",
            old_value={"title": old_title},
            new_value={"title": note.title},
            actor="agent:v4-capture",
            confidence=extraction.get("confidence"),
            reason="ai_title_set",
            source_note_id=note.id,
        )

    if summary and note.type == "note":
        ai_meta["summary"] = summary
        if extraction.get("confidence") is not None:
            ai_meta["confidence"] = extraction.get("confidence")
        note.ai_meta = ai_meta
        note.ai_status = "done"
        flag_modified(note, "ai_meta")
        applied_changes.append({"type": "summary_updated", "summary": summary})
        _write_event(
            note,
            "ai_processed",
            new_value={"summary": summary},
            actor="agent:v4-capture",
            confidence=extraction.get("confidence"),
            source_note_id=note.id,
        )
    elif ai_title and title_auto:
        # Title set but no summary — still need to persist ai_meta if we touched it.
        note.ai_meta = ai_meta
        flag_modified(note, "ai_meta")

    if note.type == "note":
        _apply_capture_intent(note, extraction)

    if note.type != "note":
        return

    for tag_candidate in extraction.get("tags") or []:
        name = _candidate_value(tag_candidate, "name")
        confidence = _candidate_confidence(tag_candidate)
        # SQ-09: tags are safe metadata. The structural precondition is simply
        # a non-empty tag name; confidence is the tiebreaker for auto-apply.
        if not name or confidence < AUTO_APPLY_CONFIDENCE:
            continue
        tag = _add_tag(note, name)
        if tag is None:
            continue
        applied_changes.append({"type": "tag_added", "tag": tag.name, "confidence": confidence})
        _write_event(
            note,
            "tag_added",
            new_value={"tag_id": tag.id, "tag": tag.name},
            actor="agent:v4-capture",
            confidence=confidence,
            source_note_id=note.id,
        )


def _capture_intent_route(extraction, content):
    """Pick the capture pipeline from the extraction-reported intent (SQ-05).

    Routing keys off the raw LLM intent, not the heuristic fallback — an
    absent/unknown intent always stays on the full pipeline.
    Returns "junk", "activity_update", or "full".
    """
    extraction = extraction or {}
    intent = extraction.get("intent")
    if intent not in CAPTURE_INTENTS:
        return "full"
    if intent == "junk":
        return "junk"
    confidence = _candidate_confidence({"confidence": extraction.get("intent_confidence")})
    # SQ-09: intent routing is a coarse pipeline switch. The structural
    # precondition is a recognized update/follow_up intent plus short content;
    # confidence is the tiebreaker that routes borderline cases through the
    # safer full extraction pipeline instead.
    if (
        intent in {"update", "follow_up"}
        and confidence >= INTENT_ROUTE_CONFIDENCE
        and len(content or "") <= INTENT_ROUTE_MAX_CONTENT_CHARS
    ):
        return "activity_update"
    return "full"


def _process_capture_extraction(note, content, extraction, thread_id=None):
    """Shared post-extraction step for both capture paths (single-shot + SSE).

    Branches on intent before reconciliation: junk skips reconciliation
    entirely, update/follow_up routes through activity-update semantics, and
    everything else runs the existing full reconciliation pipeline.
    """
    route = _capture_intent_route(extraction, content)
    if route == "full":
        return _reconcile_capture_candidates(note, extraction, thread_id=thread_id)

    applied_changes = []
    suggestions = []
    _apply_capture_extraction_metadata(note, extraction, applied_changes)
    if route == "activity_update":
        _route_capture_update_intent(
            note, content, extraction, thread_id, applied_changes, suggestions
        )
    # route == "junk": note-level metadata only; no reconciliation spend.
    _append_decision_suggestions(note, thread_id, suggestions)
    if note.ai_status == "pending":
        note.ai_status = "done"

    report_id = _assemble_report_for_note_sync(note.id)

    return applied_changes, suggestions, report_id


def _route_capture_update_intent(note, content, extraction, thread_id, applied_changes, suggestions):
    """Treat an update/follow_up-intent capture as an activity update (SQ-05).

    Resolves a target via the ladder (thread attachment → explicit mention →
    embedding similarity), then applies the same policy as Add update. With no
    target it files a single reviewable update_unresolved suggestion instead
    of running entity-extraction reconciliation.
    """
    from services.v4_extraction import extract_dates_and_tasks_from_update

    intent_confidence = _candidate_confidence({"confidence": extraction.get("intent_confidence")})
    target = _resolve_update_target(note, content, thread_id)
    parent_context = {"type": target.type, "title": target.title} if target and target.title else None
    au_extraction = extract_dates_and_tasks_from_update(content, parent_context=parent_context)

    if target is None:
        suggestion = _create_suggestion(
            note,
            suggestion_type="update_unresolved",
            operation_type="update_unresolved",
            payload={
                "content": (content or "")[:300],
                "status": au_extraction.get("status"),
                "status_confidence": au_extraction.get("confidence"),
                "follow_up_at": au_extraction.get("follow_up_at"),
                "tasks": au_extraction.get("tasks") or [],
            },
            confidence=intent_confidence or None,
            reason="update captured but no target could be resolved",
        )
        if suggestion is not None:
            suggestions.append(suggestion.to_dict())
        return

    au_note, created, _skip_reason = _create_activity_update_note(
        target,
        content,
        actor="agent:v4-capture",
        confidence=intent_confidence or None,
        source_note_id=note.id,
    )
    if au_note is None:
        return
    applied_changes.append({
        "type": "activity_update_added",
        "target_entity_id": target.id,
        "note_id": au_note.id,
        "content": content,
        "confidence": intent_confidence,
        "created": created,
    })
    if not created:
        # Duplicate update within the dedup window — same early-exit semantics
        # as the Add update endpoint.
        return

    result = _apply_activity_update_policy(
        note, target, content, au_extraction, suggestions, actor="agent:v4-capture"
    )
    if result["status_auto_applied"]:
        applied_changes.append({
            "type": "entity_updated",
            "entity_id": target.id,
            "entity_type": target.type,
            "title": target.title,
            "changes": {"status": result["status"]},
        })
    if result["follow_up_auto_set"]:
        applied_changes.append({
            "type": "entity_updated",
            "entity_id": target.id,
            "entity_type": target.type,
            "title": target.title,
            "changes": {"follow_up_at": result["follow_up_at"]},
        })

    from services.v4_summarization import queue_summarize_if_needed

    queue_summarize_if_needed(target.id, has_existing_summary=bool(target.ai_summary))


def _resolve_update_target(note, content, thread_id):
    """Resolve the entity an update-intent capture is talking about.

    Ladder: (1) capture thread attachment, (2) explicit @/[[ mention of a
    task/project in the content, (3) embedding similarity against active
    tasks and projects. Returns None when nothing is confident enough.
    """
    if thread_id:
        entity = db.session.get(Entity, thread_id)
        if entity is not None and entity.lifecycle != "deleted":
            return entity

    for match in EXPLICIT_MENTION_PATTERN.finditer(content or ""):
        entity_type = ENTITY_TYPE_BY_PLURAL.get(match.group("plural"))
        if entity_type not in {"task", "project"}:
            continue
        target = db.session.get(Entity, match.group("id"))
        if (
            target is not None
            and target.type == entity_type
            and target.lifecycle != "deleted"
            and target.id != note.id
        ):
            return target

    return _embedding_update_target(content)


def _embedding_update_target(content):
    """Ladder step 3: embed the capture content and search active tasks and
    projects; accept only a strong (>= UPDATE_TARGET_SIMILARITY) top match."""
    from services.v4_reconciliation import _cosine, _embed_texts, _load_chunks_for_type

    if not content:
        return None
    vectors = _embed_texts([content[:2000]])
    if not vectors:
        return None
    query_vec = vectors[0]

    closed_statuses = {"done", "cancelled", "completed"}
    best_id = None
    best_score = 0.0
    for entity_type in ("task", "project"):
        for entity_id, _chunk_text, embedding, entity_data in _load_chunks_for_type(entity_type):
            if embedding is None or len(embedding) == 0:
                continue
            if (entity_data or {}).get("status") in closed_statuses:
                continue
            score = _cosine(query_vec, embedding)
            if score > best_score:
                best_id = entity_id
                best_score = score

    if best_id is None or best_score < UPDATE_TARGET_SIMILARITY:
        return None
    entity = db.session.get(Entity, best_id)
    if entity is None or entity.lifecycle == "deleted":
        return None
    return entity


def _assemble_report_for_note_sync(note_id):
    """Assemble the distillation report for a note synchronously.

    Returns the report id, or None if there is nothing to report.
    """
    from services.v4_report import assemble_report_for_note

    report = assemble_report_for_note(note_id)
    return report.id if report is not None else None


def _reconcile_capture_candidates(note, extraction, thread_id=None):
    applied_changes = []
    suggestions = []

    _apply_capture_extraction_metadata(note, extraction, applied_changes)

    # Flatten link and entity candidates into a single list for reconciliation.
    # Links carry an explicit relationship_type from extraction; entity candidates
    # get a default that the reconciliation model can override.
    all_candidates = []
    for lc in extraction.get("links") or []:
        target_type = _candidate_value(lc, "target_type") or _candidate_value(lc, "type")
        if target_type not in RISKY_ENTITY_CREATION_TYPES:
            continue
        all_candidates.append({
            **lc,
            "type": target_type,
            "_source": "link",
        })
    for ec in extraction.get("entities") or []:
        if _candidate_value(ec, "type") not in RISKY_ENTITY_CREATION_TYPES:
            continue
        all_candidates.append({**ec, "_source": "entity"})

    # Dedup within this capture by (type, normalized title). The model is
    # supposed to handle this itself (prompt rule), but defense-in-depth: a
    # link candidate and an entity candidate for the same real-world thing
    # would otherwise each trigger a create/update path independently. We
    # keep the link-sourced candidate when both exist (it carries an explicit
    # relationship_type from extraction); otherwise the first seen wins.
    deduped = []
    seen = {}
    for cand in all_candidates:
        title = _candidate_value(cand, "title") or ""
        ctype = _candidate_value(cand, "type") or ""
        key = (ctype, title.casefold())
        if not title or not ctype:
            deduped.append(cand)
            continue
        if key not in seen:
            seen[key] = len(deduped)
            deduped.append(cand)
        elif cand.get("_source") == "link" and deduped[seen[key]].get("_source") != "link":
            deduped[seen[key]] = cand
    all_candidates = deduped

    # SQ-08: identify people who carry work in this note (assignees / delegation
    # targets / follow-up owners). Bare mentions without an existing match are
    # dropped instead of auto-created.
    work_carrying_persons = _collect_work_carrying_persons(all_candidates)

    if all_candidates:
        from services.v4_reconciliation import reconcile_candidates
        decisions = reconcile_candidates(all_candidates, thread_id=thread_id)
        for candidate, decision in zip(all_candidates, decisions):
            _apply_reconciliation_decision(
                note,
                candidate,
                decision,
                applied_changes,
                suggestions,
                work_carrying_persons=work_carrying_persons,
            )

    # Decision extraction: explicit commitments always become reviewable
    # suggestions, never auto-created. Notes only — thread ingest supplies
    # structured candidates and should not re-scan stored entity content.
    if note.type == "note":
        _append_decision_suggestions(note, thread_id, suggestions)

    # SQ-07: cap task suggestions per note and group survivors under the note id
    # so the review sheet can render "N action items from this note" with an
    # accept-all control.
    _cap_and_group_task_suggestions(note, suggestions)

    # Reconciliation ran to completion — mark the note as AI-processed regardless
    # of whether extraction produced a summary. Previously notes with empty
    # extraction stayed `ai_status="pending"` forever, polluting the Needs review
    # queue indefinitely.
    if note.ai_status == "pending":
        note.ai_status = "done"

    report_id = _assemble_report_for_note_sync(note.id)

    return applied_changes, suggestions, report_id


def _apply_reconciliation_decision(note, candidate, decision, applied_changes, suggestions, work_carrying_persons=None):
    action = (decision.get("action") or "new").lower()
    candidate_confidence = _candidate_confidence(candidate)
    if action == "skip":
        # SQ-09: a skip is a no-action decision. Very low-confidence skips are
        # dropped silently; medium/high-confidence skips are surfaced for review.
        # The reconciler has already structurally declined the candidate, so
        # confidence here only decides whether to stay silent or emit a suggestion.
        if candidate_confidence < LOW_CONFIDENCE_THRESHOLD:
            return
        # A medium/high-confidence candidate should still surface for review
        # even if the reconciliation model declines to act on it.
        action = "new"
        uncertain = True
    else:
        uncertain = action == "uncertain"
        if uncertain:
            action = "new"

    decision_confidence = _candidate_confidence(decision)
    confidence = _reconciliation_confidence(candidate, decision)
    if action == "new" and candidate_confidence > 0:
        # Preserve extraction confidence for uncertain/converted-skip paths and
        # for trivial model/extraction deltas, while still honoring an explicit
        # low reconciliation confidence that should block auto-apply.
        if uncertain or decision_confidence <= 0 or abs(candidate_confidence - decision_confidence) <= 0.05:
            confidence = candidate_confidence
    evidence = _candidate_value(candidate, "evidence")
    entity_type = _candidate_value(candidate, "type")
    title = _candidate_value(candidate, "title")
    rel_from_decision = decision.get("relationship_type")
    if rel_from_decision is not None:
        relationship_type = rel_from_decision
    else:
        relationship_type = _default_relationship_type(entity_type)
    if relationship_type not in RELATIONSHIP_TYPES:
        relationship_type = _default_relationship_type(entity_type)
    # Tasks extracted from notes should always trace back to their source
    # note via derived_from for provenance/audit. The parent link to the
    # project is added separately by _link_task_to_note_projects. Applies
    # to both "new" (mint a task) and "link" (re-use existing task via
    # exact-title dedup) so the source note→task trace is preserved either
    # way. We override the LLM's suggestion of "mentions" or "related" for
    # tasks because notes aren't merely mentioning tasks — they're producing them.
    if entity_type == "task" and relationship_type in {"related", "mentions", None}:
        relationship_type = "derived_from"

    if action in ("update", "link"):
        target_id = decision.get("target_id")
        target = db.session.get(Entity, target_id) if target_id else None
        if target is None:
            # Match is gone or id was hallucinated — fall through to "new"
            action = "new"

    if action == "progress_update":
        # SQ-06: thread-attached captures used to silently drop these decisions
        # (old AU8 rule); they now behave exactly like unattached ones.
        target_id = decision.get("target_id")
        target = db.session.get(Entity, target_id) if target_id else None
        if target is None:
            # No entity to attach the update to — nothing safe to do. Unlike
            # "update"/"link", we don't fall through to "new": a progress
            # note about an existing thing shouldn't spawn a fresh
            # project/task just because the model hallucinated/lost the id.
            return
        update_text = _clean_text(decision.get("update_text")) or evidence
        if not update_text:
            return
        au_note, created, _skip_reason = _create_activity_update_note(
            target, update_text, actor="agent:v4-capture", confidence=confidence, evidence=evidence, source_note_id=note.id
        )
        if au_note is None:
            return
        applied_changes.append({
            "type": "activity_update_added",
            "target_entity_id": target.id,
            "note_id": au_note.id,
            "content": update_text,
            "confidence": confidence,
            "created": created,
        })
        if not created:
            return

        new_status = (decision.get("fields") or {}).get("status")
        # SQ-09: auto-apply a captured status only when the progress text
        # explicitly names the status. Confidence alone is not predictive enough.
        if (
            new_status in VALID_STATUS.get(target.type, set())
            and new_status != target.status
            and _status_change_is_explicit(update_text, new_status)
        ):
            if confidence >= AUTO_APPLY_CONFIDENCE:
                old_status = target.status
                target.status = new_status
                applied_changes.append({
                    "type": "entity_updated",
                    "entity_id": target.id,
                    "entity_type": target.type,
                    "title": target.title,
                    "changes": {"status": new_status},
                })
                _write_event(
                    target,
                    "ai_updated",
                    old_value={"status": old_status},
                    new_value={"status": new_status},
                    actor="agent:v4-capture",
                    confidence=confidence,
                    reason=decision.get("reason"),
                    source_note_id=note.id,
                )
                _queue_embed_job(target.id, "capture_auto_update")

                if new_status in {"blocked", "waiting"}:
                    blocker_id = decision.get("blocked_by_id")
                    blocker = db.session.get(Entity, blocker_id) if blocker_id else None
                    if blocker is not None and blocker.id != target.id:
                        link = _create_entity_link(blocker, target, "blocks", confidence, evidence)
                        if link is not None:
                            applied_changes.append({
                                "type": "relationship_added",
                                "source_entity_id": blocker.id,
                                "target_entity_id": target.id,
                                "relationship_type": "blocks",
                                "confidence": confidence,
                            })
                            _write_event(
                                target,
                                "relationship_added",
                                new_value=link.to_dict(),
                                actor="agent:v4-capture",
                                confidence=confidence,
                                reason=decision.get("reason"),
                                source_note_id=note.id,
                            )
            else:
                _append_capture_suggestion(
                    note,
                    candidate,
                    action="update",
                    entity_type=target.type,
                    relationship_type=relationship_type,
                    confidence=confidence,
                    evidence=evidence,
                    suggestions=suggestions,
                    suggestion_type=f"update_{target.type}",
                    operation_type="update_entity",
                    payload={
                        "target_entity_id": target.id,
                        "target_type": target.type,
                        "title": target.title,
                        "fields": {"status": new_status},
                        "relationship_type": relationship_type,
                        "assigned_to": _candidate_value(candidate, "assigned_to"),
                        "evidence": evidence,
                    },
                    reason=decision.get("reason"),
                )

        new_priority = (decision.get("fields") or {}).get("priority")
        if new_priority in PRIORITY_LEVELS:
            current_priority = (target.properties or {}).get("priority")
            if PRIORITY_ORDER.get(new_priority, 0) > PRIORITY_ORDER.get(current_priority, 0):
                _append_capture_suggestion(
                    note,
                    candidate,
                    action="update",
                    entity_type=target.type,
                    relationship_type=relationship_type,
                    confidence=confidence,
                    evidence=evidence,
                    suggestions=suggestions,
                    suggestion_type=f"update_{target.type}",
                    operation_type="update_entity",
                    payload={
                        "target_entity_id": target.id,
                        "target_type": target.type,
                        "title": target.title,
                        "fields": {"priority": new_priority},
                        "relationship_type": relationship_type,
                        "evidence": evidence,
                    },
                    reason=decision.get("reason"),
                )
        return

    if action == "update":
        # SQ-09: the structural precondition for an update auto-apply is the
        # reconciler's explicit "update" decision with a resolved target.
        # Confidence is only the tiebreaker between applying now and surfacing
        # a reviewable suggestion; _apply_entity_update further restricts the
        # mutable fields to status/due_at/follow_up_at.
        if confidence >= AUTO_APPLY_CONFIDENCE:
            _apply_entity_update(
                note,
                target,
                candidate,
                decision,
                relationship_type,
                confidence,
                evidence,
                applied_changes,
                suggestions,
            )
        else:
            _append_capture_suggestion(
                note,
                candidate,
                action="update",
                entity_type=entity_type,
                relationship_type=relationship_type,
                confidence=confidence,
                evidence=evidence,
                suggestions=suggestions,
                suggestion_type=f"update_{entity_type}",
                operation_type="update_entity",
                payload={
                    "target_entity_id": target.id,
                    "target_type": entity_type,
                    "title": target.title,
                    "fields": decision.get("fields") or {},
                    "relationship_type": relationship_type,
                    "assigned_to": _candidate_value(candidate, "assigned_to"),
                    "evidence": evidence,
                },
                reason=decision.get("reason"),
            )
        return

    if action == "link":
        # SQ-09: linking to an existing entity is safe metadata once the
        # reconciler has explicitly chosen "link" and resolved a target.
        # Confidence is the tiebreaker between auto-linking and offering the
        # link as a reviewable suggestion.
        if confidence >= AUTO_APPLY_CONFIDENCE:
            link_source, link_target = _candidate_link_endpoints(note, target, relationship_type)
            link = _create_entity_link(link_source, link_target, relationship_type, confidence, evidence)
            if link is not None:
                applied_changes.append({
                    "type": "relationship_added",
                    "target_entity_id": target.id,
                    "relationship_type": relationship_type,
                    "confidence": confidence,
                })
                _write_event(note, "relationship_added", new_value=link.to_dict(), actor="agent:v4-capture", confidence=confidence, reason=evidence, source_note_id=note.id)
        else:
            _append_capture_suggestion(
                note,
                candidate,
                action="link",
                entity_type=target.type,
                relationship_type=relationship_type,
                confidence=confidence,
                evidence=evidence,
                suggestions=suggestions,
                suggestion_type="link_existing",
                operation_type="link_existing",
                payload={
                    "source_entity_id": note.id,
                    "target_entity_id": target.id,
                    "target_type": target.type,
                    "title": target.title,
                    "relationship_type": relationship_type,
                    "evidence": evidence,
                },
                reason=decision.get("reason"),
            )
        return

    # action == "new"
    if not title or not entity_type:
        return
    # SQ-09: globally drop very low-confidence "new" candidates as noise before
    # spending a review slot. Tasks are further guarded by _task_suggest_ok;
    # persons are guarded by SQ-08 hygiene below. Here confidence is the only
    # available signal, so it acts as a coarse noise filter rather than a gate.
    if action == "new" and _candidate_confidence(candidate) < LOW_CONFIDENCE_THRESHOLD:
        return
    content = _candidate_value(candidate, "content")
    top_match_score = decision.get("top_match_score") or 0.0
    suggestion_reason = _capture_suggestion_reason(decision, confidence, uncertain=uncertain, evidence=evidence)

    # SQ-08 person hygiene: bare person mentions must either match an existing
    # person or carry work in this note. A near-duplicate existing person is
    # linked instead of creating a duplicate; a bare mention with no match and
    # no associated work is dropped silently.
    if entity_type == "person":
        if top_match_score >= NEAR_DUPLICATE_SCORE and decision.get("top_match_id"):
            target = db.session.get(Entity, decision.get("top_match_id"))
            if target is not None:
                # SQ-09: the near-duplicate/top_match structural check has
                # already decided the link; confidence is the tiebreaker for
                # auto-linking vs. surfacing a suggestion.
                if confidence >= AUTO_APPLY_CONFIDENCE:
                    link_source, link_target = _candidate_link_endpoints(note, target, relationship_type)
                    link = _create_entity_link(link_source, link_target, relationship_type, confidence, evidence)
                    if link is not None:
                        applied_changes.append({
                            "type": "relationship_added",
                            "target_entity_id": target.id,
                            "relationship_type": relationship_type,
                            "confidence": confidence,
                        })
                        _write_event(note, "relationship_added", new_value=link.to_dict(), actor="agent:v4-capture", confidence=confidence, reason=evidence, source_note_id=note.id)
                else:
                    _append_capture_suggestion(
                        note,
                        candidate,
                        action="link",
                        entity_type=target.type,
                        relationship_type=relationship_type,
                        confidence=confidence,
                        evidence=evidence,
                        suggestions=suggestions,
                        suggestion_type="link_existing",
                        operation_type="link_existing",
                        payload={
                            "source_entity_id": note.id,
                            "target_entity_id": target.id,
                            "target_type": target.type,
                            "title": target.title,
                            "relationship_type": relationship_type,
                            "evidence": evidence,
                        },
                        reason=decision.get("reason"),
                    )
                return
        if not _person_carries_work(title, work_carrying_persons):
            return

    # SQ-09: tentative task phrasing is a structural drop signal.
    if entity_type == "task" and _task_candidate_looks_tentative(candidate):
        return

    if entity_type in {"project", "area"}:
        # Projects/areas proposed as "new" from a capture have never been a
        # useful suggestion in practice (0% acceptance) — they're almost
        # always either an existing project described slightly differently,
        # or a topic mentioned in passing within a multi-topic note (standup
        # digest, meeting transcript). If there's a plausible existing match,
        # offer that as a link suggestion instead; otherwise drop it silently
        # rather than adding to the review queue.
        top_match_id = decision.get("top_match_id")
        if top_match_id and top_match_score >= NEAR_DUPLICATE_SCORE:
            target = db.session.get(Entity, top_match_id)
            if target is not None:
                _append_capture_suggestion(
                    note,
                    candidate,
                    action="link",
                    entity_type=target.type,
                    relationship_type=relationship_type,
                    confidence=confidence,
                    evidence=evidence,
                    suggestions=suggestions,
                    suggestion_type="link_existing",
                    operation_type="link_existing",
                    payload={
                        "source_entity_id": note.id,
                        "target_entity_id": target.id,
                        "target_type": target.type,
                        "title": target.title,
                        "relationship_type": relationship_type,
                        "evidence": evidence,
                    },
                    reason=decision.get("reason"),
                )
        return

    # SQ-07: tasks must pass the structural suggest gate; otherwise they are
    # dropped as noise (logistics, stance fragments, restatements).
    if entity_type == "task" and not _task_suggest_ok(note, candidate, decision, confidence):
        return
    task_payload = {
        "type": entity_type,
        "title": title,
        "content": content,
        "due_at": _candidate_value(candidate, "due_at"),
        "assigned_to": _candidate_value(candidate, "assigned_to"),
        "source_entity_id": note.id,
        "evidence": evidence,
        "relationship_type": relationship_type,
        "near_match": {
            "entity_id": decision.get("top_match_id"),
            "title": decision.get("top_match_title"),
            "score": top_match_score,
        } if decision.get("top_match_id") else None,
    }
    if entity_type == "task" and note.type in THREAD_INGEST_SOURCE_TYPES:
        task_payload["target_entity_id"] = note.id
        task_payload["relationship_type"] = "derived_from"
    _append_capture_suggestion(
        note,
        candidate,
        action="new",
        entity_type=entity_type,
        relationship_type=relationship_type,
        confidence=confidence,
        evidence=evidence,
        suggestions=suggestions,
        suggestion_type=f"create_{entity_type}",
        operation_type="create_entity",
        payload=task_payload,
        reason=suggestion_reason,
    )


def _link_task_to_note_projects(
    note,
    task,
    confidence,
    evidence,
    applied_changes,
    suggestions=None,
    actor="agent:v4-capture",
    change_batch_id=None,
    on_behalf=None,
):
    """Create parent links from a newly accepted task to every project
    the source note is linked to.

    When a task is extracted from a meeting note and then accepted by the
    operator, it almost certainly belongs to one or more of the projects that
    note references. Without this step, tasks end up orphaned with only a
    derived_from link to the note, and projects show zero open tasks.

    When the source entity is itself a project or area, parent-link the task directly.
    """
    parent_target_ids = set()
    if note.type in {"project", "area"} and note.lifecycle == "active":
        parent_target_ids.add(note.id)

    project_link_types = {"related", "mentions", "parent"}
    note_project_links = EntityLink.query.filter(
        EntityLink.source_entity_id == note.id,
        EntityLink.relationship_type.in_(project_link_types),
    ).all()

    parent_target_ids.update(link.target_entity_id for link in note_project_links)

    if not parent_target_ids:
        return

    parents = Entity.query.filter(
        Entity.id.in_(parent_target_ids),
        Entity.type.in_({"project", "area"}),
        Entity.lifecycle == "active",
    ).all()

    for parent in parents:
        pin_decision = check_pin(task, "parent", actor, on_behalf=on_behalf)
        if not pin_decision["allow_write"]:
            suggestion = _create_suggestion(
                note,
                suggestion_type=f"update_{task.type}",
                operation_type="update_entity",
                payload={
                    "target_entity_id": task.id,
                    "target_type": task.type,
                    "title": task.title,
                    "fields": {},
                    "relationship_type": "derived_from",
                    "parent_target_id": parent.id,
                    "parent_target_type": parent.type,
                    "parent_target_title": parent.title,
                    "evidence": evidence,
                },
                confidence=confidence,
                reason=_pin_reason_with_context(evidence, pin_decision["reason"]),
            )
            if suggestion:
                suggestions.append(suggestion.to_dict())
            continue
        parent_link = _create_entity_link(
            task,
            parent,
            "parent",
            confidence,
            evidence,
            source="ai",
        )
        if parent_link is not None:
            _write_event(
                task,
                "relationship_added",
                new_value=parent_link.to_dict(),
                actor=actor,
                confidence=confidence,
                reason=evidence or f"inherited from note {note.id}",
                source_note_id=note.id,
                change_batch_id=change_batch_id,
            )
            _record_relationship_pin_event(
                task,
                "parent",
                actor=actor,
                reason="parent relationship pinned",
                confidence=confidence,
                source_note_id=note.id,
                change_batch_id=change_batch_id,
                on_behalf=on_behalf,
            )
            applied_changes.append({
                "type": "relationship_added",
                "target_entity_id": parent.id,
                "relationship_type": "parent",
                "confidence": confidence,
            })


def _touch_parent_projects(task):
    """Advance updated_at on all active parent projects of a task.

    Called whenever a task is modified so project surfaces reflect
    current activity instead of going stale.
    """
    parent_links = EntityLink.query.filter_by(
        source_entity_id=task.id,
        relationship_type="parent",
    ).all()
    for link in parent_links:
        parent = db.session.get(Entity, link.target_entity_id)
        if parent is not None and parent.lifecycle == "active":
            parent.updated_at = datetime.now(timezone.utc)


def _apply_entity_update(note, entity, candidate, decision, relationship_type, confidence, evidence, applied_changes, suggestions):
    fields = dict(decision.get("fields") or {})
    changed = {}
    previous = {}
    demoted_fields = {}

    for field_name in ("status", "due_at"):
        if field_name not in fields:
            continue
        pin_decision = check_pin(entity, field_name, "agent:v4-capture")
        if pin_decision["allow_write"]:
            continue
        demoted_fields[field_name] = fields.pop(field_name)
        suggestion = _create_suggestion(
            note,
            suggestion_type=f"update_{entity.type}",
            operation_type="update_entity",
            payload={
                "target_entity_id": entity.id,
                "target_type": entity.type,
                "title": entity.title,
                "fields": {field_name: demoted_fields[field_name]},
                "relationship_type": relationship_type,
                "assigned_to": _candidate_value(candidate, "assigned_to"),
                "evidence": evidence,
            },
            confidence=confidence,
            reason=_pin_reason_with_context(decision.get("reason"), pin_decision["reason"]),
        )
        if suggestion:
            suggestions.append(suggestion.to_dict())

    new_status = fields.get("status")
    if new_status and new_status in VALID_STATUS.get(entity.type, set()):
        previous["status"] = entity.status
        entity.status = new_status
        changed["status"] = new_status

    raw_due = fields.get("due_at")
    if raw_due:
        parsed = _parse_iso_date(raw_due)
        if parsed:
            previous["due_at"] = entity.due_at.isoformat() if entity.due_at else None
            entity.due_at = parsed
            changed["due_at"] = raw_due

    raw_follow_up = fields.get("follow_up_at")
    if raw_follow_up:
        parsed = _parse_iso_date(raw_follow_up)
        if parsed:
            previous["follow_up_at"] = entity.follow_up_at.isoformat() if entity.follow_up_at else None
            entity.follow_up_at = parsed
            changed["follow_up_at"] = raw_follow_up

    link_source, link_target = _candidate_link_endpoints(note, entity, relationship_type)
    link = _create_entity_link(link_source, link_target, relationship_type, confidence, evidence)

    if changed:
        applied_changes.append({
            "type": "entity_updated",
            "entity_id": entity.id,
            "entity_type": entity.type,
            "title": entity.title,
            "changes": changed,
        })
        _write_event(
            entity, "ai_updated", old_value=previous, new_value=changed, actor="agent:v4-capture",
            confidence=confidence, reason=decision.get("reason"), source_note_id=note.id,
        )
        _queue_embed_job(entity.id, "capture_auto_update")
    if link is not None:
        applied_changes.append({
            "type": "relationship_added",
            "target_entity_id": entity.id,
            "relationship_type": relationship_type,
            "confidence": confidence,
        })
        _write_event(note, "relationship_added", new_value=link.to_dict(), actor="agent:v4-capture", confidence=confidence, reason=evidence, source_note_id=note.id)
    _apply_assignee_and_record(
        note,
        entity,
        _candidate_value(candidate, "assigned_to"),
        confidence,
        evidence,
        applied_changes,
        source="ai",
        actor="agent:v4-capture",
        suggestions=suggestions,
    )


def _get_app_setting(key, default=None):
    setting = db.session.get(AppSetting, key)
    return setting.value if setting is not None else default


def _app_setting_row(key):
    setting = db.session.get(AppSetting, key)
    if setting is None:
        setting = AppSetting(key=key, value=None)
        db.session.add(setting)
    return setting


def _set_app_setting(key, value):
    setting = _app_setting_row(key)
    setting.value = value
    flag_modified(setting, "value")
    db.session.commit()
    return value


def _owner_person_id():
    owner_person_id = _clean_text(_get_app_setting("owner_person_id"))
    return owner_person_id


def _owner_aliases():
    aliases = _get_app_setting("owner_aliases", DEFAULT_OWNER_ALIASES)
    return {str(a).strip().lower() for a in aliases}


def _is_owner(name, person_id=None):
    owner_person_id = _owner_person_id()
    if owner_person_id is not None:
        return person_id == owner_person_id
    cleaned = _clean_text(name)
    if cleaned is None:
        return False
    return cleaned.lower() in _owner_aliases()


def _record_owner_identity_change(previous_owner, next_owner, actor="user"):
    if previous_owner is not None and previous_owner.id != (next_owner.id if next_owner is not None else None):
        _write_event(
            previous_owner,
            "updated",
            old_value={"is_owner": True},
            new_value={"is_owner": False},
            actor=actor,
            reason="owner identity updated",
        )
    if next_owner is not None and next_owner.id != (previous_owner.id if previous_owner is not None else None):
        _write_event(
            next_owner,
            "updated",
            old_value={"is_owner": False},
            new_value={"is_owner": True},
            actor=actor,
            reason="owner identity updated",
        )


def _delegation_cadence_days(person_id=None):
    overrides = _get_app_setting("cadence_overrides", {}) or {}
    if person_id and person_id in overrides:
        return overrides[person_id]
    return _get_app_setting("default_cadence_days", DEFAULT_DELEGATION_CADENCE_DAYS)


def _add_working_days(start, days):
    """Add `days` working days (Mon-Fri) to `start`, skipping weekends."""
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def _latest_activity_updates(entity_ids):
    """Map entity_id -> (created_at, content) of its most recent activity-update note."""
    if not entity_ids:
        return {}
    rows = (
        db.session.query(EntityLink.target_entity_id, Entity.created_at, Entity.content)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "activity_update",
            EntityLink.target_entity_id.in_(entity_ids),
        )
        .order_by(EntityLink.target_entity_id, Entity.created_at.desc())
        .all()
    )
    latest = {}
    for target_id, created_at, content in rows:
        if target_id not in latest:
            latest[target_id] = (created_at, content)
    return latest


def _ensure_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _days_since(reference, now):
    reference = _ensure_utc(reference)
    if reference is None:
        return None
    return max(0, (now - reference).days)


def _person_open_tasks(person):
    """Open tasks assigned to `person`."""
    return (
        _entity_query()
        .join(EntityLink, (EntityLink.source_entity_id == Entity.id) & (EntityLink.relationship_type == "assigned_to"))
        .filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
            EntityLink.target_entity_id == person.id,
        )
        .order_by(Entity.follow_up_at.asc().nullslast(), Entity.updated_at.desc())
        .limit(50)
        .all()
    )


def _project_open_tasks(project):
    """Open tasks parent-linked to `project`."""
    return (
        _entity_query()
        .join(EntityLink, (EntityLink.source_entity_id == Entity.id) & (EntityLink.relationship_type == "parent"))
        .filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
            EntityLink.target_entity_id == project.id,
        )
        .order_by(Entity.due_at.asc().nullslast(), Entity.follow_up_at.asc().nullslast(), Entity.updated_at.desc())
        .limit(50)
        .all()
    )


def _person_current_load(tasks, latest_update):
    """Open tasks assigned to a person, each with last-activity-update info."""
    if not tasks:
        return []

    results = []
    for task in tasks:
        last = latest_update.get(task.id)
        last_created, last_content = last if last else (None, None)
        results.append({
            "task": _entity_with_attention(task),
            "last_heard_at": _iso(last_created),
            "last_heard_preview": last_content[:160] if last_content else None,
        })
    return results


def _person_pulse(tasks, latest_update, now=None):
    """Transient 1:1 prep signal for a person's current work."""
    now = now or datetime.now(timezone.utc)
    summary = {
        "open_tasks": len(tasks),
        "stuck_tasks": 0,
        "overdue_follow_ups": 0,
        "quiet_tasks": 0,
    }
    focus_items = []

    for task in tasks:
        last_created, last_content = latest_update.get(task.id, (None, None))
        last_heard_preview = last_content[:160] if last_content else None
        is_stuck = task.status in {"blocked", "waiting"}
        follow_up_at = _ensure_utc(task.follow_up_at)
        overdue_days = max(1, (now.date() - follow_up_at.date()).days) if follow_up_at and follow_up_at < now else 0
        quiet_days = _days_since(last_created or task.created_at, now) or 0
        is_quiet = quiet_days >= PERSON_PULSE_QUIET_DAYS

        if is_stuck:
            summary["stuck_tasks"] += 1
        if overdue_days:
            summary["overdue_follow_ups"] += 1
        if is_quiet:
            summary["quiet_tasks"] += 1

        if is_stuck:
            focus = {
                "kind": "stuck",
                "label": "Blocked" if task.status == "blocked" else "Waiting",
            }
            rank = (0, 0)
        elif overdue_days:
            focus = {
                "kind": "overdue_follow_up",
                "label": f"Follow-up overdue by {overdue_days} day{'s' if overdue_days != 1 else ''}",
            }
            rank = (1, -overdue_days)
        elif is_quiet:
            focus = {
                "kind": "quiet",
                "label": f"No update in {quiet_days} day{'s' if quiet_days != 1 else ''}",
            }
            rank = (2, -quiet_days)
        else:
            continue

        focus_items.append((rank, {
            **focus,
            "entity": _entity_with_attention(task),
            "last_heard_at": _iso(last_created),
            "last_heard_preview": last_heard_preview,
        }))

    focus_items.sort(key=lambda item: item[0])
    return {
        "headline": _person_pulse_headline(summary),
        "summary": summary,
        "focus_items": [item for _, item in focus_items[:5]],
    }


def _person_pulse_headline(summary):
    parts = []
    if summary["stuck_tasks"]:
        parts.append(f"{summary['stuck_tasks']} stuck task{'s' if summary['stuck_tasks'] != 1 else ''}")
    if summary["overdue_follow_ups"]:
        parts.append(
            f"{summary['overdue_follow_ups']} overdue follow-up"
            f"{'s' if summary['overdue_follow_ups'] != 1 else ''}"
        )
    if summary["quiet_tasks"]:
        parts.append(f"{summary['quiet_tasks']} quiet task{'s' if summary['quiet_tasks'] != 1 else ''}")
    if not parts:
        return "No obvious follow-up risk right now."
    if len(parts) == 1:
        joined = parts[0]
    elif len(parts) == 2:
        joined = f"{parts[0]} and {parts[1]}"
    else:
        joined = f"{', '.join(parts[:-1])}, and {parts[-1]}"
    return f"Focus the next 1:1 on {joined}."


def _person_recent_notes(person):
    """Recent non-activity notes that mention `person`."""
    notes = (
        _entity_query()
        .join(EntityLink, (EntityLink.source_entity_id == Entity.id) & (EntityLink.relationship_type == "mentions"))
        .filter(
            Entity.type == "note",
            Entity.lifecycle == "active",
            Entity.source != "activity_update",
            EntityLink.target_entity_id == person.id,
        )
        .order_by(Entity.updated_at.desc(), Entity.created_at.desc())
        .limit(3)
        .all()
    )
    return [
        {
            "id": note.id,
            "type": note.type,
            "title": note.title,
            "updated_at": _iso(note.updated_at),
            "preview": (note.content or "")[:160] or None,
        }
        for note in notes
    ]


def _person_meeting_prep(person, tasks, latest_update, pulse, now=None):
    """Transient meeting-prep artifact for a person's detail page."""
    now = now or datetime.now(timezone.utc)
    agenda_items = []

    for item in pulse.get("focus_items", []):
        if item["kind"] == "stuck":
            title = f"Unblock {item['entity']['title']}"
        elif item["kind"] == "overdue_follow_up":
            title = f"Confirm next step for {item['entity']['title']}"
        elif item["kind"] == "quiet":
            title = f"Ask for status on {item['entity']['title']}"
        else:
            title = item["entity"]["title"]
        reason = item["label"]
        if item.get("last_heard_preview"):
            reason += f". Last heard: {item['last_heard_preview']}"
        agenda_items.append({
            "kind": item["kind"],
            "title": title,
            "reason": reason,
            "entity": item["entity"],
        })

    focused_ids = {item["entity"]["id"] for item in agenda_items}
    progress_candidates = []
    for task in tasks:
        if task.id in focused_ids:
            continue
        last_created, last_content = latest_update.get(task.id, (None, None))
        if last_created is None:
            continue
        if _days_since(last_created, now) is None or _days_since(last_created, now) > 7:
            continue
        progress_candidates.append({
            "kind": "recent_progress",
            "title": f"Acknowledge progress on {task.title}",
            "reason": (last_content or "")[:160] or "Recent update shared",
            "entity": _entity_with_attention(task),
            "_sort": _ensure_utc(last_created),
        })

    progress_candidates.sort(key=lambda item: item["_sort"], reverse=True)
    for item in progress_candidates[: max(0, 4 - len(agenda_items))]:
        item.pop("_sort", None)
        agenda_items.append(item)

    recent_notes = _person_recent_notes(person)
    return {
        "headline": _meeting_prep_headline(len(agenda_items), len(recent_notes)),
        "counts": {
            "agenda_items": len(agenda_items),
            "recent_notes": len(recent_notes),
        },
        "agenda_items": agenda_items[:4],
        "recent_notes": recent_notes,
    }


def _meeting_prep_headline(agenda_count, note_count):
    agenda_label = f"{agenda_count} agenda topic{'s' if agenda_count != 1 else ''}"
    note_label = f"{note_count} recent note{'s' if note_count != 1 else ''}"
    return f"Go in with {agenda_label} and {note_label}."


def _coordination_radar(now=None):
    now = now or datetime.now(timezone.utc)
    return {
        "people": _coordination_radar_people(now, limit=3, require_signal=True),
        "projects": _coordination_radar_projects(now, limit=3, require_signal=True),
    }


def _coordination_radar_people(now, *, limit=3, require_signal=True):
    owner_person_id = _owner_person_id()
    rows = (
        db.session.query(EntityLink.target_entity_id, Entity)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "assigned_to",
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
        )
        .order_by(
            EntityLink.target_entity_id,
            Entity.follow_up_at.asc().nullslast(),
            Entity.updated_at.desc(),
        )
        .all()
    )
    if not rows:
        return []

    tasks_by_person_id = {}
    task_ids = []
    for person_id, task in rows:
        tasks_by_person_id.setdefault(person_id, []).append(task)
        task_ids.append(task.id)

    people = (
        _entity_query()
        .filter(
            Entity.type == "person",
            Entity.lifecycle == "active",
            Entity.status == "active",
            Entity.id.in_(list(tasks_by_person_id)),
        )
        .all()
    )
    people_by_id = {person.id: person for person in people}
    latest_update = _latest_activity_updates(task_ids)

    radar_items = []
    for person_id, tasks in tasks_by_person_id.items():
        if owner_person_id is not None and person_id == owner_person_id:
            continue
        person = people_by_id.get(person_id)
        if person is None:
            continue
        if owner_person_id is None and _is_owner(person.title, person.id):
            continue
        pulse = _person_pulse(tasks[:50], latest_update, now=now)
        counts = pulse["summary"]
        if require_signal and not (counts["stuck_tasks"] or counts["overdue_follow_ups"] or counts["quiet_tasks"]):
            continue
        radar_items.append({
            "entity_id": person.id,
            "entity_type": "person",
            "title": person.title,
            "headline": pulse["headline"],
            "counts": counts,
            "_rank": (
                counts["stuck_tasks"],
                counts["overdue_follow_ups"],
                counts["quiet_tasks"],
                counts["open_tasks"],
            ),
        })

    radar_items.sort(key=lambda item: item["_rank"], reverse=True)
    for item in radar_items:
        item.pop("_rank", None)
    if limit is None:
        return radar_items
    return radar_items[:limit]


def _today_dependency_interventions(now):
    tasks = (
        _entity_query()
        .filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
        )
        .order_by(Entity.updated_at.desc())
        .limit(200)
        .all()
    )
    latest_update = _latest_activity_updates([task.id for task in tasks])
    watch = _task_dependency_watch(tasks, latest_update, limit=10)
    return watch["focus_items"]


def _coordination_radar_projects(now, *, limit=3, require_signal=True):
    rows = (
        db.session.query(EntityLink.target_entity_id, Entity)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "parent",
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
        )
        .order_by(
            EntityLink.target_entity_id,
            Entity.due_at.asc().nullslast(),
            Entity.follow_up_at.asc().nullslast(),
            Entity.updated_at.desc(),
        )
        .all()
    )
    if not rows:
        return []

    tasks_by_project_id = {}
    task_ids = []
    for project_id, task in rows:
        tasks_by_project_id.setdefault(project_id, []).append(task)
        task_ids.append(task.id)

    projects = (
        _entity_query()
        .filter(
            Entity.type == "project",
            Entity.lifecycle == "active",
            Entity.status == "active",
            Entity.id.in_(list(tasks_by_project_id)),
        )
        .all()
    )
    projects_by_id = {project.id: project for project in projects}
    latest_update = _latest_activity_updates(task_ids)

    radar_items = []
    for project_id, tasks in tasks_by_project_id.items():
        project = projects_by_id.get(project_id)
        if project is None:
            continue
        pulse = _project_pulse(tasks[:50], latest_update, now=now)
        counts = pulse["summary"]
        if require_signal and not (counts["stuck_tasks"] or counts["overdue_tasks"] or counts["quiet_tasks"]):
            continue
        radar_items.append({
            "entity_id": project.id,
            "entity_type": "project",
            "title": project.title,
            "headline": pulse["headline"],
            "counts": counts,
            "_rank": (
                counts["stuck_tasks"],
                counts["overdue_tasks"],
                counts["quiet_tasks"],
                counts["open_tasks"],
            ),
        })

    radar_items.sort(key=lambda item: item["_rank"], reverse=True)
    for item in radar_items:
        item.pop("_rank", None)
    if limit is None:
        return radar_items
    return radar_items[:limit]


def _aggregate_attention_reasons(attentions):
    """Merge attention.reasons from thread members, summing weights by key."""
    merged = {}
    for attention in attentions:
        for reason in attention.get("reasons") or []:
            key = reason["key"]
            if key in merged:
                merged[key]["weight"] += reason["weight"]
            else:
                merged[key] = dict(reason)
    return sorted(merged.values(), key=lambda reason: reason["weight"], reverse=True)


def _thread_attention_score(reasons):
    return max(0, min(100, sum(reason["weight"] for reason in reasons)))


def _entity_recent_notes(entity_id, limit=10):
    return (
        _entity_query()
        .join(EntityLink, EntityLink.source_entity_id == Entity.id)
        .filter(
            Entity.type == "note",
            Entity.lifecycle == "active",
            EntityLink.target_entity_id == entity_id,
            EntityLink.relationship_type.in_(["mentions", "related", "references"]),
        )
        .order_by(Entity.created_at.desc())
        .limit(limit)
        .all()
    )


def _thread_last_context(entity, tasks, latest_update, entity_notes, now):
    """One-sentence summary of the most recent activity."""
    candidates = []
    for task in tasks:
        last = latest_update.get(task.id)
        if last:
            created_at, content = last
            candidates.append((created_at, content))
    for note in entity_notes:
        candidates.append((note.created_at, note.content))
    if entity.updated_at:
        candidates.append((entity.updated_at, None))

    if not candidates:
        return f"last activity on {now.date().isoformat()}"

    most_recent = max(
        candidates,
        key=lambda item: _ensure_utc(item[0]) or datetime.min.replace(tzinfo=timezone.utc),
    )
    created_at, content = most_recent
    if content and str(content).strip():
        sentence = str(content).strip().split("\n")[0]
        if len(sentence) > 200:
            sentence = sentence[:197] + "..."
        return sentence

    reference = _ensure_utc(created_at) or now
    return f"last activity on {reference.strftime('%b %d')}"


def _thread_last_activity_at(entity, tasks, latest_update, entity_notes):
    candidates = []
    for task in tasks:
        last = latest_update.get(task.id)
        if last and last[0]:
            candidates.append(_ensure_utc(last[0]))
    for note in entity_notes:
        if note.created_at:
            candidates.append(_ensure_utc(note.created_at))
    if entity.updated_at:
        candidates.append(_ensure_utc(entity.updated_at))
    candidates = [value for value in candidates if value is not None]
    if not candidates:
        return None
    return max(candidates)


def _build_thread_key_items(tasks, *, inherited_priorities, staleness, blocks, now, limit=3):
    items = []
    for task in tasks:
        attention = attention_for_entity(
            task,
            inherited_priority=inherited_priorities.get(task.id),
            staleness_days=staleness.get(task.id),
            blocks_count=blocks.get(task.id, 0),
            now=now,
        )
        items.append({
            "id": task.id,
            "type": task.type,
            "name": task.title,
            "attention_score": attention["score"],
        })
    items.sort(key=lambda item: item["attention_score"], reverse=True)
    return items[:limit]


def _person_thread(person, tasks, latest_update, now, inherited_priorities, staleness, blocks):
    attentions = [
        attention_for_entity(
            task,
            inherited_priority=inherited_priorities.get(task.id),
            staleness_days=staleness.get(task.id),
            blocks_count=blocks.get(task.id, 0),
            now=now,
        )
        for task in tasks
    ]
    reasons = _aggregate_attention_reasons(attentions)
    entity_notes = _entity_recent_notes(person.id)
    last_activity_at = _thread_last_activity_at(person, tasks, latest_update, entity_notes)
    return {
        "id": person.id,
        "type": "person",
        "name": person.title,
        "attention_score": _thread_attention_score(reasons),
        "attention_reasons": reasons,
        "last_activity_at": _iso(last_activity_at),
        "last_context": _thread_last_context(person, tasks, latest_update, entity_notes, now),
        "key_items": _build_thread_key_items(
            tasks,
            inherited_priorities=inherited_priorities,
            staleness=staleness,
            blocks=blocks,
            now=now,
        ),
    }


def _project_thread(project, tasks, latest_update, now, inherited_priorities, staleness, blocks):
    attentions = [
        attention_for_entity(
            task,
            inherited_priority=inherited_priorities.get(task.id),
            staleness_days=staleness.get(task.id),
            blocks_count=blocks.get(task.id, 0),
            now=now,
        )
        for task in tasks
    ]
    reasons = _aggregate_attention_reasons(attentions)
    entity_notes = _entity_recent_notes(project.id)
    last_activity_at = _thread_last_activity_at(project, tasks, latest_update, entity_notes)
    return {
        "id": project.id,
        "type": "project",
        "name": project.title,
        "attention_score": _thread_attention_score(reasons),
        "attention_reasons": reasons,
        "last_activity_at": _iso(last_activity_at),
        "last_context": _thread_last_context(project, tasks, latest_update, entity_notes, now),
        "key_items": _build_thread_key_items(
            tasks,
            inherited_priorities=inherited_priorities,
            staleness=staleness,
            blocks=blocks,
            now=now,
        ),
    }


def _people_threads(now):
    owner_person_id = _owner_person_id()
    rows = (
        db.session.query(EntityLink.target_entity_id, Entity)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "assigned_to",
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
        )
        .order_by(
            EntityLink.target_entity_id,
            Entity.follow_up_at.asc().nullslast(),
            Entity.updated_at.desc(),
        )
        .all()
    )
    if not rows:
        return []

    tasks_by_person_id = {}
    task_ids = []
    for person_id, task in rows:
        tasks_by_person_id.setdefault(person_id, []).append(task)
        task_ids.append(task.id)

    people = (
        _entity_query()
        .filter(
            Entity.type == "person",
            Entity.lifecycle == "active",
            Entity.status == "active",
            Entity.id.in_(list(tasks_by_person_id)),
        )
        .all()
    )
    people_by_id = {person.id: person for person in people}
    latest_update = _latest_activity_updates(task_ids)
    all_tasks = [task for tasks in tasks_by_person_id.values() for task in tasks]
    inherited_priorities = _inherited_task_priorities(all_tasks)
    staleness = _staleness_days_for(all_tasks, now)
    blocks = _blocking_impact_counts(all_tasks)

    threads = []
    for person_id, tasks in tasks_by_person_id.items():
        if owner_person_id is not None and person_id == owner_person_id:
            continue
        person = people_by_id.get(person_id)
        if person is None:
            continue
        if owner_person_id is None and _is_owner(person.title, person.id):
            continue
        threads.append(
            _person_thread(
                person,
                tasks[:50],
                latest_update,
                now,
                inherited_priorities,
                staleness,
                blocks,
            )
        )
    return threads


def _project_threads(now):
    rows = (
        db.session.query(EntityLink.target_entity_id, Entity)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "parent",
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(OPEN_TASK_STATUSES),
        )
        .order_by(
            EntityLink.target_entity_id,
            Entity.due_at.asc().nullslast(),
            Entity.follow_up_at.asc().nullslast(),
            Entity.updated_at.desc(),
        )
        .all()
    )
    if not rows:
        return []

    tasks_by_project_id = {}
    task_ids = []
    for project_id, task in rows:
        tasks_by_project_id.setdefault(project_id, []).append(task)
        task_ids.append(task.id)

    projects = (
        _entity_query()
        .filter(
            Entity.type == "project",
            Entity.lifecycle == "active",
            Entity.status == "active",
            Entity.id.in_(list(tasks_by_project_id)),
        )
        .all()
    )
    projects_by_id = {project.id: project for project in projects}
    latest_update = _latest_activity_updates(task_ids)
    all_tasks = [task for tasks in tasks_by_project_id.values() for task in tasks]
    inherited_priorities = _inherited_task_priorities(all_tasks)
    staleness = _staleness_days_for(all_tasks, now)
    blocks = _blocking_impact_counts(all_tasks)

    threads = []
    for project_id, tasks in tasks_by_project_id.items():
        project = projects_by_id.get(project_id)
        if project is None:
            continue
        threads.append(
            _project_thread(
                project,
                tasks[:50],
                latest_update,
                now,
                inherited_priorities,
                staleness,
                blocks,
            )
        )
    return threads


def _notes_linked_to_parent_entities(note_ids):
    if not note_ids:
        return set()
    rows = (
        db.session.query(EntityLink.source_entity_id)
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.source_entity_id.in_(note_ids),
            EntityLink.relationship_type.in_(["mentions", "related", "parent", "references"]),
            Entity.type.in_(["person", "project"]),
        )
        .all()
    )
    return {row[0] for row in rows}


def _topic_thread_name(notes):
    for note in notes:
        title = (note.title or "").strip()
        if title:
            return title
    for note in notes:
        content = (note.content or "").strip()
        if content:
            line = content.split("\n")[0].strip()
            if line:
                return line[:80]
    return "Untitled topic"


def _topic_threads(now, *, limit=None):
    """Best-effort topic clusters from orphan notes with embeddings."""
    started = time_module.monotonic()

    def _over_budget():
        return (time_module.monotonic() - started) * 1000 > TOPIC_CLUSTER_TIME_BUDGET_MS

    try:
        from services.v4_reconciliation import _cosine

        candidate_notes = (
            _entity_query()
            .filter(
                Entity.type == "note",
                Entity.lifecycle == "active",
            )
            .order_by(Entity.updated_at.desc())
            .limit(150)
            .all()
        )
        if _over_budget():
            logger.warning(
                "topic clustering exceeded %sms budget; returning no topics",
                TOPIC_CLUSTER_TIME_BUDGET_MS,
            )
            return []

        note_ids = [note.id for note in candidate_notes]
        linked = _notes_linked_to_parent_entities(note_ids)
        orphan_notes = [note for note in candidate_notes if note.id not in linked]
        if len(orphan_notes) < 2:
            return []

        chunks = (
            db.session.query(EntityChunk)
            .filter(
                EntityChunk.entity_id.in_([note.id for note in orphan_notes]),
                EntityChunk.chunk_index == 0,
                EntityChunk.embedding.is_not(None),
            )
            .all()
        )
        embedding_by_note = {chunk.entity_id: chunk.embedding for chunk in chunks}
        notes_with_embeddings = [
            (note, embedding_by_note[note.id])
            for note in orphan_notes
            if note.id in embedding_by_note
        ]
        if len(notes_with_embeddings) < 2:
            return []

        clusters = []
        for index, (note, embedding) in enumerate(notes_with_embeddings):
            if _over_budget():
                logger.warning(
                    "topic clustering exceeded %sms budget; returning no topics",
                    TOPIC_CLUSTER_TIME_BUDGET_MS,
                )
                return []
            placed = False
            for cluster in clusters:
                anchor_index = cluster[0]
                anchor_embedding = notes_with_embeddings[anchor_index][1]
                if _cosine(embedding, anchor_embedding) >= TOPIC_CLUSTER_SIMILARITY:
                    cluster.append(index)
                    placed = True
                    break
            if not placed:
                clusters.append([index])

        threads = []
        for cluster_indices in clusters:
            if len(cluster_indices) < 2:
                continue
            cluster_notes = [notes_with_embeddings[i][0] for i in cluster_indices]
            attentions = [attention_for_entity(note, now=now) for note in cluster_notes]
            reasons = _aggregate_attention_reasons(attentions)
            latest_note = max(cluster_notes, key=lambda note: note.updated_at or note.created_at)
            threads.append({
                "id": f"topic:{hashlib.sha256(latest_note.id.encode()).hexdigest()[:12]}",
                "type": "topic",
                "name": _topic_thread_name(cluster_notes),
                "attention_score": _thread_attention_score(reasons),
                "attention_reasons": reasons,
                "last_activity_at": _iso(latest_note.updated_at or latest_note.created_at),
                "last_context": _thread_last_context(latest_note, [], {}, [latest_note], now),
                "key_items": [
                    {
                        "id": note.id,
                        "type": "note",
                        "name": note.title or _topic_thread_name([note]),
                        "attention_score": attention_for_entity(note, now=now)["score"],
                    }
                    for note in sorted(
                        cluster_notes,
                        key=lambda note: attention_for_entity(note, now=now)["score"],
                        reverse=True,
                    )[:3]
                ],
            })
            if limit is not None and len(threads) >= limit:
                break
        return threads
    except Exception as exc:
        logger.warning("topic clustering failed: %s", exc)
        return []


def _project_pulse(tasks, latest_update, now=None):
    """Transient project pulse derived from open project tasks."""
    now = now or datetime.now(timezone.utc)
    summary = {
        "open_tasks": len(tasks),
        "stuck_tasks": 0,
        "overdue_tasks": 0,
        "quiet_tasks": 0,
    }
    focus_items = []

    for task in tasks:
        last_created, last_content = latest_update.get(task.id, (None, None))
        last_heard_preview = last_content[:160] if last_content else None
        is_stuck = task.status in {"blocked", "waiting"}
        due_refs = [dt for dt in (_ensure_utc(task.due_at), _ensure_utc(task.follow_up_at)) if dt is not None]
        overdue_at = min(due_refs) if due_refs else None
        overdue_days = max(1, (now.date() - overdue_at.date()).days) if overdue_at and overdue_at < now else 0
        quiet_days = _days_since(last_created or task.created_at, now) or 0
        is_quiet = quiet_days >= PERSON_PULSE_QUIET_DAYS

        if is_stuck:
            summary["stuck_tasks"] += 1
        if overdue_days:
            summary["overdue_tasks"] += 1
        if is_quiet:
            summary["quiet_tasks"] += 1

        if is_stuck:
            focus = {"kind": "stuck", "label": "Blocked" if task.status == "blocked" else "Waiting"}
            rank = (0, 0)
        elif overdue_days:
            focus = {
                "kind": "overdue",
                "label": f"Overdue by {overdue_days} day{'s' if overdue_days != 1 else ''}",
            }
            rank = (1, -overdue_days)
        elif is_quiet:
            focus = {
                "kind": "quiet",
                "label": f"No update in {quiet_days} day{'s' if quiet_days != 1 else ''}",
            }
            rank = (2, -quiet_days)
        else:
            continue

        focus_items.append((rank, {
            **focus,
            "entity": _entity_with_attention(task),
            "last_heard_at": _iso(last_created),
            "last_heard_preview": last_heard_preview,
        }))

    focus_items.sort(key=lambda item: item[0])
    return {
        "headline": _project_pulse_headline(summary),
        "summary": summary,
        "focus_items": [item for _, item in focus_items[:5]],
    }


def _task_dependency_watch(tasks, latest_update, limit=5):
    task_ids = [task.id for task in tasks]
    if not task_ids:
        return {
            "headline": "No active blockers or dependency chains right now.",
            "summary": {"blocked_tasks": 0, "external_blockers": 0, "blocking_tasks": 0},
            "focus_items": [],
        }

    task_id_set = set(task_ids)
    blocked_rows = (
        db.session.query(EntityLink.target_entity_id, Entity)
        .join(Entity, Entity.id == EntityLink.source_entity_id)
        .filter(
            EntityLink.relationship_type == "blocks",
            EntityLink.target_entity_id.in_(task_ids),
            Entity.lifecycle == "active",
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(EntityLink.target_entity_id, Entity.updated_at.desc())
        .all()
    )
    blocking_rows = (
        db.session.query(EntityLink.source_entity_id, Entity)
        .join(Entity, Entity.id == EntityLink.target_entity_id)
        .filter(
            EntityLink.relationship_type == "blocks",
            EntityLink.source_entity_id.in_(task_ids),
            Entity.lifecycle == "active",
            ~Entity.status.in_(DONE_TASK_STATUSES),
        )
        .order_by(EntityLink.source_entity_id, Entity.updated_at.desc())
        .all()
    )

    tasks_by_id = {task.id: task for task in tasks}
    blocking_counts = _blocking_impact_counts(tasks)
    blocked_task_ids = set()
    external_blockers = 0
    focus_items = []

    for target_id, blocker in blocked_rows:
        task = tasks_by_id.get(target_id)
        if task is None:
            continue
        if task.status not in {"blocked", "waiting"}:
            continue
        blocked_task_ids.add(target_id)
        last_created, last_content = latest_update.get(target_id, (None, None))
        is_external = blocker.id not in task_id_set
        if is_external:
            external_blockers += 1
        focus_items.append((
            (0 if is_external else 1, 0),
            {
                "kind": "external_blocker" if is_external else "blocked_by",
                "label": f"Blocked by {blocker.title or 'Untitled task'}",
                "entity": _entity_with_attention(task),
                "blocker": _entity_with_attention(blocker),
                "last_heard_at": _iso(last_created),
                "last_heard_preview": last_content[:160] if last_content else None,
            },
        ))

    first_blocked_target = {}
    for source_id, target in blocking_rows:
        first_blocked_target.setdefault(source_id, target)

    for source_id, count in blocking_counts.items():
        task = tasks_by_id.get(source_id)
        if task is None or count <= 0:
            continue
        focus_items.append((
            (2, -count),
            {
                "kind": "blocking",
                "label": f"Blocking {count} open task{'s' if count != 1 else ''}",
                "entity": _entity_with_attention(task),
                "blocked_count": count,
                "blocked_preview": first_blocked_target.get(source_id).title if first_blocked_target.get(source_id) else None,
            },
        ))

    focus_items.sort(key=lambda item: item[0])
    summary = {
        "blocked_tasks": len(blocked_task_ids),
        "external_blockers": external_blockers,
        "blocking_tasks": len([count for count in blocking_counts.values() if count > 0]),
    }
    return {
        "headline": _project_dependency_watch_headline(summary),
        "summary": summary,
        "focus_items": [item for _, item in focus_items[:limit]],
    }


def _project_dependency_watch_headline(summary):
    parts = []
    if summary["blocked_tasks"]:
        parts.append(f"{summary['blocked_tasks']} blocked task{'s' if summary['blocked_tasks'] != 1 else ''}")
    if summary["external_blockers"]:
        parts.append(
            f"{summary['external_blockers']} external dependenc"
            f"{'ies' if summary['external_blockers'] != 1 else 'y'}"
        )
    if summary["blocking_tasks"]:
        parts.append(
            f"{summary['blocking_tasks']} task"
            f"{'s' if summary['blocking_tasks'] != 1 else ''} blocking others"
        )
    if not parts:
        return "No active blockers or dependency chains right now."
    if len(parts) == 1:
        joined = parts[0]
    elif len(parts) == 2:
        joined = f"{parts[0]} and {parts[1]}"
    else:
        joined = f"{', '.join(parts[:-1])}, and {parts[-1]}"
    return f"Watch {joined}."


def _project_pulse_headline(summary):
    parts = []
    if summary["stuck_tasks"]:
        parts.append(f"{summary['stuck_tasks']} stuck task{'s' if summary['stuck_tasks'] != 1 else ''}")
    if summary["overdue_tasks"]:
        parts.append(f"{summary['overdue_tasks']} overdue task{'s' if summary['overdue_tasks'] != 1 else ''}")
    if summary["quiet_tasks"]:
        parts.append(f"{summary['quiet_tasks']} quiet task{'s' if summary['quiet_tasks'] != 1 else ''}")
    if not parts:
        return "No obvious delivery risk right now."
    if len(parts) == 1:
        joined = parts[0]
    elif len(parts) == 2:
        joined = f"{parts[0]} and {parts[1]}"
    else:
        joined = f"{', '.join(parts[:-1])}, and {parts[-1]}"
    return f"Focus this project on {joined}."


def _delegations_quiet(now):
    """Tasks delegated to a non-owner person whose follow_up_at has passed
    with no activity update since. Batched (no N+1)."""
    from sqlalchemy.orm import aliased

    PersonEntity = aliased(Entity)
    owner_person_id = _owner_person_id()
    owner_aliases = _owner_aliases() if owner_person_id is None else set()

    tasks = (
        _entity_query()
        .join(EntityLink, (EntityLink.source_entity_id == Entity.id) & (EntityLink.relationship_type == "assigned_to"))
        .join(PersonEntity, PersonEntity.id == EntityLink.target_entity_id)
        .filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            ~Entity.status.in_(DONE_TASK_STATUSES),
            Entity.follow_up_at.isnot(None),
            Entity.follow_up_at < now,
            PersonEntity.type == "person",
        )
    )
    if owner_person_id is not None:
        tasks = tasks.filter(PersonEntity.id != owner_person_id)
    elif owner_aliases:
        tasks = tasks.filter(~func.lower(PersonEntity.title).in_(owner_aliases))
    tasks = tasks.order_by(Entity.follow_up_at.asc()).limit(50).all()
    if not tasks:
        return []

    task_ids = [task.id for task in tasks]
    latest_update = _latest_activity_updates(task_ids)

    results = []
    for task in tasks:
        last = latest_update.get(task.id)
        last_created, last_content = last if last else (None, None)
        if last_created is not None:
            reference = last_created
            if reference.tzinfo is None:
                reference = reference.replace(tzinfo=timezone.utc)
            if reference >= task.follow_up_at:
                continue
        else:
            reference = task.follow_up_at

        item = _entity_with_attention(task, context=["delegation_quiet"])
        item["days_silent"] = (now - reference).days
        item["last_update"] = last_content[:160] if last_content else None
        results.append(item)
    return results


def _parse_iso_date(value):
    """Parse an ISO 8601 date string into a timezone-aware datetime, or None."""
    if not value:
        return None
    try:
        from datetime import datetime, timezone
        s = str(value).strip()[:10]
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None




def _create_suggestion(note, suggestion_type, operation_type, payload, confidence=None, reason=None):
    fingerprint = _suggestion_fingerprint(suggestion_type, operation_type, payload)
    existing_pending = _existing_pending_suggestion(fingerprint)
    if existing_pending is not None:
        if existing_pending.source_entity_id == note.id:
            if confidence is not None and (existing_pending.confidence is None or confidence > existing_pending.confidence):
                existing_pending.confidence = confidence
            if reason:
                existing_pending.reason = reason
            return existing_pending
        return None

    if _recently_resolved_duplicate(fingerprint, confidence, suggestion_type, operation_type, payload):
        return None

    _clear_review_resolution(note)
    suggestion = AiSuggestion(
        source_entity_id=note.id,
        suggestion_type=suggestion_type,
        operation_type=operation_type,
        payload={**(payload or {}), "_fingerprint": fingerprint},
        confidence=confidence,
        reason=reason,
        status="pending",
    )
    db.session.add(suggestion)
    db.session.flush()
    return suggestion


def _creates_blocks_cycle(source_entity_id, target_entity_id):
    """True if adding source --blocks--> target would create a cycle, i.e. if
    target can already (transitively) reach source via 'blocks' links."""
    if source_entity_id == target_entity_id:
        return True
    visited = set()
    frontier = [target_entity_id]
    while frontier:
        current = frontier.pop()
        if current == source_entity_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        next_ids = [
            row[0] for row in db.session.query(EntityLink.target_entity_id)
            .filter(
                EntityLink.source_entity_id == current,
                EntityLink.relationship_type == "blocks",
            )
            .all()
        ]
        frontier.extend(next_ids)
    return False


# Matches markdown links produced by the inline @/[[ mention picker, e.g.
# "[Ship the feature](/tasks/3e6c...-...)". Capturing the plural type segment
# lets us resolve straight back to an entity without any LLM involvement.
EXPLICIT_MENTION_PATTERN = re.compile(
    r"\[[^\]\n]+\]\(/(?P<plural>[a-z]+)/(?P<id>[0-9a-fA-F-]{36})\)"
)


def _apply_explicit_mentions(note, content):
    """Create direct `mentions` links for entities picked via the inline
    @/[[ picker while typing `content`.

    These references are explicit user choices, so they bypass extraction
    and reconciliation entirely — confidence 1.0, no review needed.
    """
    if not content:
        return []
    applied = []
    seen_ids = set()
    for match in EXPLICIT_MENTION_PATTERN.finditer(content):
        entity_type = ENTITY_TYPE_BY_PLURAL.get(match.group("plural"))
        if entity_type is None:
            continue
        target_id = match.group("id")
        if target_id == note.id or target_id in seen_ids:
            continue
        target = db.session.get(Entity, target_id)
        if target is None or target.type != entity_type or target.lifecycle == "deleted":
            continue
        seen_ids.add(target_id)
        link = _create_entity_link(note, target, "mentions", 1.0, "explicit mention", source="user")
        if link is not None:
            _write_event(
                target,
                "relationship_added",
                new_value=link.to_dict(),
                actor="user",
                reason="explicit mention",
                source_note_id=note.id,
            )
            applied.append({
                "type": "relationship_added",
                "source_entity_id": note.id,
                "target_entity_id": target.id,
                "relationship_type": "mentions",
                "confidence": 1.0,
            })
    return applied


def _create_entity_link(source_entity, target_entity, relationship_type, confidence, evidence, source="ai"):
    existing = EntityLink.query.filter_by(
        source_entity_id=source_entity.id,
        target_entity_id=target_entity.id,
        relationship_type=relationship_type,
    ).first()
    if existing is not None:
        return None
    if relationship_type == "blocks" and _creates_blocks_cycle(source_entity.id, target_entity.id):
        return None
    link = EntityLink(
        source_entity_id=source_entity.id,
        target_entity_id=target_entity.id,
        relationship_type=relationship_type,
        source=source,
        confidence=confidence,
        evidence=evidence,
    )
    db.session.add(link)
    db.session.flush()

    # When a note is linked to any non-note entity, queue a summarize job so
    # the entity's summary reflects the new information, regardless of link direction.
    if getattr(source_entity, "type", None) == "note" and getattr(target_entity, "type", None) != "note":
        from services.v4_summarization import queue_summarize_if_needed
        queue_summarize_if_needed(target_entity.id, has_existing_summary=bool(target_entity.ai_summary))
    elif getattr(target_entity, "type", None) == "note" and getattr(source_entity, "type", None) != "note":
        from services.v4_summarization import queue_summarize_if_needed
        queue_summarize_if_needed(source_entity.id, has_existing_summary=bool(source_entity.ai_summary))

    # When a task is parent-linked to a project, advance the project's
    # updated_at so surfaces reflect current activity.
    if (relationship_type == "parent"
        and getattr(source_entity, "type", None) == "task"
        and getattr(target_entity, "type", None) == "project"):
        target_entity.updated_at = datetime.now(timezone.utc)

    return link


def _find_existing_entity(entity_type, title):
    if entity_type == "person":
        return _find_existing_person(title)
    return Entity.query.filter(
        Entity.type == entity_type,
        func.lower(Entity.title) == title.lower(),
        Entity.lifecycle != "deleted",
    ).first()


def _find_existing_person(title):
    """Find an active person by exact, unique first-name, or unique substring match.

    A bare first-name mention ("Priya") resolves to "Priya Dhandapani" only
    when the match is unambiguous. If multiple people share the same first
    name, no automatic link is made — the caller should create a new entity or
    surface the mention for review.
    """
    title_lower = (title or "").strip().lower()
    if not title_lower:
        return None

    persons = Entity.query.filter(
        Entity.type == "person",
        Entity.lifecycle == "active",
    ).all()

    exact_match = None
    first_name_matches = []
    substring_matches = []

    for person in persons:
        person_title_lower = (person.title or "").strip().lower()
        if not person_title_lower:
            continue
        if person_title_lower == title_lower:
            exact_match = person
            break
        words = person_title_lower.split()
        if words and words[0] == title_lower:
            first_name_matches.append(person)
        elif title_lower in person_title_lower:
            substring_matches.append(person)

    if exact_match is not None:
        return exact_match
    if len(first_name_matches) == 1:
        return first_name_matches[0]
    if not first_name_matches and len(substring_matches) == 1:
        return substring_matches[0]
    return None


def _person_carries_work(title, work_carrying_persons):
    """Return True if a person candidate matches a work-carrying name.

    Work-carrying names come from task/project candidates with an assigned_to
    value in the same note. Matching tolerates first-name and substring overlap
    so that "Priya" is considered work-carrying when a task is assigned to
    "Priya Dhandapani".
    """
    if not title or not work_carrying_persons:
        return False
    title_lower = title.strip().lower()
    for name in work_carrying_persons:
        name_lower = (name or "").strip().lower()
        if not name_lower:
            continue
        if title_lower == name_lower:
            return True
        name_words = name_lower.split()
        if name_words and name_words[0] == title_lower:
            return True
        if title_lower in name_lower or name_lower in title_lower:
            return True
    return False


def _default_relationship_type(entity_type):
    if entity_type == "person":
        return "mentions"
    return "related"


def _is_create_suggestion_operation(operation_type):
    return operation_type in {"create_entity", "create_new_entity"}


def _accepted_suggestion_link(source_note, entity, payload=None):
    payload = payload or {}
    target_entity_id = payload.get("target_entity_id")
    relationship_type = payload.get("relationship_type")
    if target_entity_id and relationship_type == "derived_from" and entity.type == "task":
        target = db.session.get(Entity, target_entity_id)
        if target is not None and target.lifecycle != "deleted" and target.id != entity.id:
            return entity, target, relationship_type
    if entity.type == "task":
        return entity, source_note, "derived_from"
    if entity.type == "person":
        return source_note, entity, "mentions"
    if entity.type == "resource":
        return source_note, entity, "references"
    return source_note, entity, "related"


def _candidate_link_endpoints(source_note, entity, relationship_type):
    if entity.type == "task" and relationship_type == "derived_from":
        if source_note.type == "note":
            return entity, source_note
        if source_note.type in THREAD_INGEST_SOURCE_TYPES:
            return entity, source_note
    return source_note, entity


def _candidate_value(candidate, key):
    if isinstance(candidate, dict):
        value = candidate.get(key)
    else:
        value = candidate
    return _clean_text(value)


def _candidate_confidence(candidate):
    if isinstance(candidate, dict):
        value = candidate.get("confidence")
    else:
        value = None
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _apply_capture_intent(note, extraction):
    ai_meta = dict(note.ai_meta or {})
    intent, confidence = _capture_intent(note.content or "", extraction or {})
    ai_meta["intent"] = intent
    ai_meta["intent_confidence"] = confidence
    note.ai_meta = ai_meta
    flag_modified(note, "ai_meta")


def _capture_intent(content, extraction):
    explicit_intent = extraction.get("intent")
    explicit_confidence = _candidate_confidence({"confidence": extraction.get("intent_confidence")})
    if explicit_intent in CAPTURE_INTENTS:
        return explicit_intent, explicit_confidence or _candidate_confidence(extraction)

    lowered = (content or "").strip().casefold()
    entities = extraction.get("entities") or []
    links = extraction.get("links") or []
    entity_types = {item.get("type") for item in entities}
    has_tasks = "task" in entity_types
    has_resources = "resource" in entity_types or any(link.get("relationship_type") == "references" for link in links)
    has_follow_up = any(item.get("follow_up_at") for item in entities)
    has_assignee = any(item.get("assigned_to") for item in entities)
    has_blocker = any(link.get("relationship_type") == "blocks" for link in links)

    if lowered in {"test", "testing", "asdf", "n/a", "na"}:
        return "junk", 0.78
    if has_blocker or any(phrase in lowered for phrase in ("blocked by", "blocked on", "waiting on", "stuck on", "dependency")):
        return "blocker", 0.82
    if has_assignee or (has_tasks and any(phrase in lowered for phrase in ("owner:", "assigned to", "delegate to", "have ", "ask "))):
        return "delegation", 0.8
    if has_follow_up or any(phrase in lowered for phrase in ("follow up", "follow-up", "circle back", "remind me", "check back")):
        return "follow_up", 0.8
    if has_resources or any(phrase in lowered for phrase in ("http://", "https://", "doc:", "see also", "reference", "read this", "link:")):
        return "reference", 0.76
    if has_tasks or any(phrase in lowered for phrase in ("todo", "to do", "next steps", "action items", "we should", "need to", "please", "ship ", "draft ", "review ", "send ", "schedule ")):
        return "task_signal", 0.74
    if any(phrase in lowered for phrase in ("update:", "fyi", "for visibility", "progress", "shipped", "completed", "done with", "status update")):
        return "update", 0.72
    if len(lowered) < 12 and not entities and not links:
        return "junk", 0.55
    return "note", 0.6


def _sort_inbox_notes(notes, pending_counts, mode):
    return sorted(
        notes,
        key=lambda note: _inbox_sort_key(note, pending_counts.get(note.id, 0), mode),
    )


def _inbox_sort_key(note, pending_suggestion_count, mode):
    ai_meta = note.ai_meta or {}
    intent = ai_meta.get("intent") if ai_meta.get("intent") in CAPTURE_INTENTS else "note"
    intent_rank = INBOX_INTENT_PRIORITY.get(intent, INBOX_INTENT_PRIORITY["note"])
    updated_at = note.updated_at or note.created_at or datetime.min.replace(tzinfo=timezone.utc)
    created_at = note.created_at or updated_at
    timestamp_rank = -updated_at.timestamp()
    created_rank = -created_at.timestamp()

    if mode == "needs_review":
        if note.ai_status == "failed":
            review_rank = 0
        elif pending_suggestion_count > 0:
            review_rank = 1
        elif note.ai_status == "pending":
            review_rank = 2
        else:
            review_rank = 3
        return (review_rank, intent_rank, -pending_suggestion_count, timestamp_rank, created_rank)

    return (intent_rank, created_rank, timestamp_rank)


def _capture_suggestion_reason(decision, confidence, uncertain=False, evidence=None):
    from services.v4_reconciliation import (
        UNCERTAIN_SUGGESTION_REASON,
        is_uncertain_decision,
    )

    if uncertain or is_uncertain_decision(decision, confidence=confidence):
        return evidence or UNCERTAIN_SUGGESTION_REASON
    return decision.get("reason")


def _append_capture_suggestion(note, candidate, action, entity_type, relationship_type, confidence, evidence, suggestions, suggestion_type, operation_type, payload, reason):
    if not _should_emit_capture_suggestion(note, candidate, action, entity_type, relationship_type, confidence):
        return
    suggestion = _create_suggestion(
        note,
        suggestion_type=suggestion_type,
        operation_type=operation_type,
        payload=payload,
        confidence=confidence,
        reason=reason,
    )
    if suggestion is not None:
        suggestions.append(suggestion.to_dict())


def _should_emit_capture_suggestion(note, candidate, action, entity_type, relationship_type, confidence):
    if note.type != "note":
        return confidence >= LOW_CONFIDENCE_THRESHOLD

    intent = ((note.ai_meta or {}).get("intent") or "note")
    if entity_type == "decision":
        # SQ-09: decisions are high-signal by design; confidence is the
        # tiebreaker that keeps only very low-confidence ones out of review.
        return confidence >= LOW_CONFIDENCE_THRESHOLD
    # SQ-09: junk-intent captures are structurally dropped unless a candidate
    # is high-confidence enough to be worth a quick review slot.
    if intent == "junk" and confidence < INTENT_SUGGESTION_CONFIDENCE_FLOOR:
        return False
    # SQ-09: reference-intent captures should not spawn low-confidence task
    # work. The structural signal is the intent classification; confidence is
    # the tiebreaker.
    if (
        intent == "reference"
        and entity_type == "task"
        and action in {"new", "update"}
        and confidence < INTENT_SUGGESTION_CONFIDENCE_FLOOR
    ):
        return False
    # SQ-09: tentative phrasing is a structural drop signal; all tentative
    # task candidates are suppressed as noise regardless of confidence.
    if (
        entity_type == "task"
        and action == "new"
        and _task_candidate_looks_tentative(candidate)
    ):
        return False
    return True


def _task_candidate_looks_tentative(candidate):
    """Return True for obviously tentative task phrasing that should stay out of review.

    We still allow concrete low-confidence tasks like "Follow up with Henry" or
    "Review the rollout doc" to surface for review, but we suppress hedged
    wording that usually represents musing rather than an actionable task.
    """
    title = (_candidate_value(candidate, "title") or "").casefold()
    if not title:
        return False

    tentative_prefixes = (
        "maybe ",
        "possibly ",
        "perhaps ",
        "might ",
        "could ",
        "consider ",
        "think about ",
        "look into ",
        "we should maybe ",
        "let's maybe ",
    )
    return title.startswith(tentative_prefixes)


def _status_keyword_is_affirmed(source_text, term):
    """Return True when *term* appears in *source_text* without direct negation."""
    lowered = source_text.lower()
    start = 0
    while start < len(lowered):
        pos = lowered.find(term, start)
        if pos == -1:
            return False
        segment = lowered[max(0, pos - 20):pos + len(term)]
        if not _status_term_is_negated(segment, term):
            return True
        start = pos + len(term)
    return False


def _status_term_is_negated(segment, term):
    """True when *segment* around *term* is directly negated."""
    escaped = re.escape(term)
    negated_patterns = (
        rf"\bnot\s+yet\s+{escaped}\b",
        rf"\bnot\s+{escaped}\b",
        rf"\b(?:isn\'t|aren't|wasn't|weren't|hasn't|haven't|hadn't)\s+(?:\w+\s+){{0,2}}{escaped}\b",
        rf"\b(?:don't|doesn't|didn't|won't|wouldn't|can't|cannot)\s+(?:\w+\s+){{0,2}}{escaped}\b",
    )
    return any(re.search(pattern, segment) for pattern in negated_patterns)


def _status_change_is_explicit(source_text, new_status):
    """SQ-09 structural guard for status auto-apply.

    A status transition is only auto-applied when the source text contains
    explicit phrasing that names the new status. Confidence is consulted only
    after this precondition is met; without it, the change stays a reviewable
    suggestion. Negated phrasing ("not done", "isn't blocked") does not count.
    """
    if not source_text or not new_status:
        return False
    keywords = {
        "done": {"done", "shipped", "completed", "finished", "closed", "close", "closing", "wrapped up"},
        "completed": {"completed", "done", "shipped", "finished", "closed", "close", "closing"},
        "cancelled": {"cancelled", "canceled", "killed", "won't do", "not doing", "scrapped"},
        "blocked": {"blocked", "stuck", "blocker", "blocking", "block"},
        "waiting": {"waiting", "wait", "waiting on", "blocked on"},
    }
    return any(
        _status_keyword_is_affirmed(source_text, term)
        for term in keywords.get(new_status, set())
    )


def _append_decision_suggestions(note, thread_id, suggestions):
    from api import v4_entities as _v4e
    """Extract explicit decisions and append reviewable create_decision suggestions."""
    decision_candidates = _v4e._extract_decision_candidates(note, thread_id=thread_id)
    for candidate in decision_candidates:
        _append_capture_suggestion(
            note,
            candidate,
            action="new",
            entity_type="decision",
            relationship_type=None,
            confidence=candidate.get("confidence", 0.9),
            evidence=candidate.get("statement"),
            suggestions=suggestions,
            suggestion_type="create_decision",
            operation_type="create_decision",
            payload={
                "thread_id": candidate.get("thread_id"),
                "statement": candidate.get("statement"),
                "context": candidate.get("context"),
                "decided_at": candidate.get("decided_at"),
                "decided_by": candidate.get("decided_by"),
                "source_note_id": note.id,
            },
            reason=f"Explicit commitment detected: {candidate.get('statement')}",
        )


_FOLLOW_UP_OWNER_RE = re.compile(
    r"\bfollow[\s-]?up with ([A-Za-z][a-zA-Z'-]+)\b",
    re.IGNORECASE,
)


def _collect_work_carrying_persons(all_candidates):
    """Names that carry work in this capture (assignees, delegation, follow-up targets)."""
    names = set()
    for cand in all_candidates:
        ctype = _candidate_value(cand, "type")
        assignee = _candidate_value(cand, "assigned_to")
        if assignee:
            names.add(assignee)
        if (
            ctype == "person"
            and cand.get("_source") == "link"
            and _candidate_value(cand, "relationship_type") == "assigned_to"
        ):
            title = _candidate_value(cand, "title")
            if title:
                names.add(title)
        if ctype == "task":
            title = _candidate_value(cand, "title") or ""
            match = _FOLLOW_UP_OWNER_RE.search(title)
            if match:
                names.add(match.group(1))
    return names


def _suggestion_task_structural_score(note, row):
    """Structural score for a pending create_task suggestion row."""
    payload = row.get("payload") or {}
    candidate = {
        "title": payload.get("title"),
        "assigned_to": payload.get("assigned_to"),
        "due_at": payload.get("due_at"),
        "follow_up_at": payload.get("follow_up_at"),
    }
    near = payload.get("near_match") or {}
    decision = {
        "top_match_score": near.get("score") or 0.0,
        "top_match_id": near.get("entity_id"),
    }
    return _task_structural_score(note, candidate, decision)


def _cap_and_group_task_suggestions(note, suggestions):
    """Cap create_task suggestions per note and tag survivors with group_id.

    Long meeting notes can produce many task candidates. We keep the best
    TASK_SUGGESTION_CAP_PER_NOTE candidates (structural score, then confidence)
    and mark them as a group so the review sheet can render them with an
    accept-all control.
    """
    task_rows = [(i, row) for i, row in enumerate(suggestions) if row.get("suggestion_type") == "create_task"]
    if not task_rows:
        return

    kept = task_rows
    if len(task_rows) > TASK_SUGGESTION_CAP_PER_NOTE:
        task_rows.sort(
            key=lambda item: (
                _suggestion_task_structural_score(note, item[1]),
                item[1].get("confidence") or 0.0,
            ),
            reverse=True,
        )
        kept = task_rows[:TASK_SUGGESTION_CAP_PER_NOTE]
    kept_ids = {row["id"] for _, row in kept}

    note_id_str = str(note.id)
    for suggestion_id in kept_ids:
        suggestion = db.session.get(AiSuggestion, suggestion_id)
        if suggestion is None or suggestion.status != "pending":
            continue
        payload = dict(suggestion.payload or {})
        payload["group_id"] = note_id_str
        suggestion.payload = payload
        flag_modified(suggestion, "payload")

    # Drop overflow tasks from the DB and response. Use "expired" (not
    # "dismissed") so SQ-10 semantic dismissal memory is not polluted.
    dropped = [(i, row) for i, row in task_rows if row["id"] not in kept_ids]
    for _i, row in dropped:
        suggestion = db.session.get(AiSuggestion, row["id"])
        if suggestion is not None and suggestion.status == "pending":
            suggestion.status = "expired"
            suggestion.resolved_at = datetime.utcnow()
            drop_payload = dict(suggestion.payload or {})
            drop_payload["expire_reason"] = "task_cap_overflow"
            suggestion.payload = drop_payload
            flag_modified(suggestion, "payload")

    # Update the in-memory dicts and remove dropped rows.
    kept_set = {i for i, _ in kept}
    for i, row in task_rows:
        if i in kept_set:
            payload = row.get("payload") or {}
            payload["group_id"] = note_id_str
            row["payload"] = payload

    suggestions[:] = [row for i, row in enumerate(suggestions) if i in kept_set or row.get("suggestion_type") != "create_task"]


def _expire_stale_suggestion_if_needed(suggestion):
    source_note = db.session.get(Entity, suggestion.source_entity_id)
    payload = suggestion.payload or {}
    relationship_type = payload.get("relationship_type")

    if source_note is None or source_note.lifecycle != "active":
        return _expire_suggestion(suggestion, None, "source note is no longer active")

    if suggestion.operation_type == "link_existing":
        target = db.session.get(Entity, payload.get("target_entity_id"))
        if target is None or target.lifecycle == "deleted":
            return _expire_suggestion(suggestion, source_note, "target entity no longer exists")
        if _relationship_exists_between(source_note, target, relationship_type or _default_relationship_type(target.type)):
            return _expire_suggestion(suggestion, source_note, "relationship already exists")
        return None

    if suggestion.operation_type == "update_entity":
        target = db.session.get(Entity, payload.get("target_entity_id"))
        if target is None or target.lifecycle == "deleted":
            return _expire_suggestion(suggestion, source_note, "target entity no longer exists")
        fields = payload.get("fields") or {}
        link_exists = _relationship_exists_between(
            source_note,
            target,
            relationship_type or _default_relationship_type(target.type),
        )
        if not _suggested_fields_would_change(target, fields) and link_exists:
            return _expire_suggestion(suggestion, source_note, "suggestion no longer changes the target")
        return None

    if _is_create_suggestion_operation(suggestion.operation_type):
        entity_type = payload.get("type")
        title = _clean_text(payload.get("title"))
        if not entity_type or not title:
            return _expire_suggestion(suggestion, source_note, "suggestion payload is incomplete")
        existing = _find_existing_entity(entity_type, title)
        if existing is None or existing.lifecycle == "deleted":
            return None
        rel_type = relationship_type or _default_relationship_type(entity_type)
        if _relationship_exists_between(source_note, existing, rel_type):
            return _expire_suggestion(suggestion, source_note, "matching entity and relationship already exist")
    return None


def _expire_suggestion(suggestion, source_note, reason):
    suggestion.status = "expired"
    suggestion.resolved_at = datetime.utcnow()
    if source_note is not None:
        _write_event(
            source_note,
            "suggestion_expired",
            new_value={"suggestion_id": suggestion.id},
            actor="agent:v4-reconcile",
            confidence=suggestion.confidence,
            reason=reason,
        )
    return suggestion.to_dict()


def _suggested_fields_would_change(target_entity, fields):
    if not isinstance(fields, dict):
        return False
    if "status" in fields and fields["status"] != target_entity.status:
        return True
    if "due_at" in fields:
        due_at, _ = _parse_datetime_or_error(fields["due_at"])
        if due_at != target_entity.due_at:
            return True
    if "follow_up_at" in fields:
        follow_up_at, _ = _parse_datetime_or_error(fields["follow_up_at"])
        if follow_up_at != target_entity.follow_up_at:
            return True
    return False


def _relationship_exists_between(source_note, entity, relationship_type):
    link_source, link_target = _candidate_link_endpoints(source_note, entity, relationship_type)
    return EntityLink.query.filter_by(
        source_entity_id=link_source.id,
        target_entity_id=link_target.id,
        relationship_type=relationship_type,
    ).first() is not None


def _suggestion_fingerprint(suggestion_type, operation_type, payload):
    normalized = {
        "suggestion_type": suggestion_type,
        "operation_type": operation_type,
        "payload": _normalized_suggestion_payload(operation_type, payload or {}),
    }
    raw = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _normalized_suggestion_payload(operation_type, payload):
    if _is_create_suggestion_operation(operation_type):
        return {
            "type": _clean_text(payload.get("type")),
            "title": _clean_text(payload.get("title")),
            "content": _clean_text(payload.get("content")),
            "due_at": _clean_text(payload.get("due_at")),
            "follow_up_at": _clean_text(payload.get("follow_up_at")),
            "assigned_to": _clean_text(payload.get("assigned_to")),
            "relationship_type": _clean_text(payload.get("relationship_type")),
            "target_entity_id": _clean_text(payload.get("target_entity_id")),
        }
    if operation_type == "create_decision":
        return {
            "thread_id": _clean_text(payload.get("thread_id")),
            "statement": _clean_text(payload.get("statement")),
            "decided_at": _clean_text(payload.get("decided_at")),
            "decided_by": _clean_text(payload.get("decided_by")),
        }
    if operation_type == "update_unresolved":
        # Distinct unresolved updates must not collapse into one fingerprint;
        # the content excerpt is the identity of the captured update.
        return {
            "content": _clean_text(payload.get("content")),
            "status": _clean_text(payload.get("status")),
            "follow_up_at": _clean_text(payload.get("follow_up_at")),
        }
    if operation_type == "update_entity":
        fields = payload.get("fields") or {}
        return {
            "target_entity_id": _clean_text(payload.get("target_entity_id")),
            "relationship_type": _clean_text(payload.get("relationship_type")),
            "assigned_to": _clean_text(payload.get("assigned_to")),
            "fields": {
                "status": _clean_text(fields.get("status")),
                "due_at": _clean_text(fields.get("due_at")),
                "follow_up_at": _clean_text(fields.get("follow_up_at")),
            },
        }
    return {
        "target_entity_id": _clean_text(payload.get("target_entity_id")),
        "relationship_type": _clean_text(payload.get("relationship_type")),
    }


def _existing_pending_suggestion(fingerprint):
    return AiSuggestion.query.filter(
        AiSuggestion.status == "pending",
        AiSuggestion.payload["_fingerprint"].as_string() == fingerprint,
    ).first()


def _semantic_embedding_text(suggestion_type, operation_type, payload):
    """Normalize a suggestion into the text we embed for semantic duplicate checks.

    Uses the title (or statement/content for non-entity suggestions). For
    update suggestions, appends the target entity id so that reworded updates
    to *different* targets are not confused with each other.
    """
    payload = payload or {}
    text = (
        _clean_text(payload.get("title"))
        or _clean_text(payload.get("statement"))
        or _clean_text(payload.get("content"))
        or ""
    )
    if operation_type == "update_entity":
        target_id = _clean_text(payload.get("target_entity_id"))
        if target_id:
            text = f"{text} {target_id}".strip()
    return text


def _recently_resolved_duplicate(fingerprint, confidence, suggestion_type, operation_type, payload):
    # SQ-09: duplicate suppression is structurally gated by the fingerprint
    # (same normalized payload). Confidence is a tiebreaker: a slightly higher
    # confidence version is allowed to resurface, otherwise the duplicate is
    # suppressed so the review queue isn't spammed with re-suggestions.
    cutoff = datetime.now(timezone.utc) - timedelta(days=SUGGESTION_DUPLICATE_MEMORY_DAYS)
    existing = AiSuggestion.query.filter(
        AiSuggestion.status.in_(("dismissed", "expired")),
        AiSuggestion.updated_at >= cutoff,
        AiSuggestion.payload["_fingerprint"].as_string() == fingerprint,
    ).order_by(AiSuggestion.updated_at.desc()).first()
    if existing is not None:
        previous_confidence = existing.confidence or 0.0
        next_confidence = confidence or 0.0
        return next_confidence <= previous_confidence + 0.05

    # SQ-10: reworded duplicates of recently dismissed suggestions should also
    # be suppressed. The exact-fingerprint fast path above keeps this cheap.
    return _recently_resolved_semantic_duplicate(suggestion_type, operation_type, payload)


def _recently_resolved_semantic_duplicate(suggestion_type, operation_type, payload):
    """Suppress reworded duplicates via embedding similarity.

    Compares the candidate's normalized text to dismissed/expired suggestions
    from the last SUGGESTION_SEMANTIC_MEMORY_DAYS days with the same
    suggestion_type. Embeddings are computed lazily and cached in the dismissed
    suggestion's payload.
    """
    candidate_text = _semantic_embedding_text(suggestion_type, operation_type, payload)
    if not candidate_text:
        return False

    from services.v4_reconciliation import _cosine, _embed_texts

    semantic_cutoff = datetime.now(timezone.utc) - timedelta(days=SUGGESTION_SEMANTIC_MEMORY_DAYS)
    existing = AiSuggestion.query.filter(
        AiSuggestion.status.in_(("dismissed", "expired")),
        AiSuggestion.updated_at >= semantic_cutoff,
        AiSuggestion.suggestion_type == suggestion_type,
    ).order_by(AiSuggestion.updated_at.desc()).all()

    if not existing:
        return False

    candidate_vectors = _embed_texts([candidate_text])
    if not candidate_vectors or not candidate_vectors[0]:
        return False
    candidate_vec = candidate_vectors[0]

    # Backfill embeddings for dismissed suggestions that don't have one yet.
    missing = []
    for suggestion in existing:
        existing_payload = suggestion.payload or {}
        if "_semantic_embedding" not in existing_payload:
            text = _semantic_embedding_text(suggestion.suggestion_type, suggestion.operation_type, existing_payload)
            if text:
                missing.append((suggestion, text))

    if missing:
        vectors = _embed_texts([text for _, text in missing])
        for i, (suggestion, _) in enumerate(missing):
            if i >= len(vectors) or not vectors[i]:
                continue
            new_payload = dict(suggestion.payload or {})
            new_payload["_semantic_embedding"] = vectors[i]
            suggestion.payload = new_payload
            flag_modified(suggestion, "payload")

    for suggestion in existing:
        existing_payload = suggestion.payload or {}
        if existing_payload.get("expire_reason") == "task_cap_overflow":
            continue
        embedding = existing_payload.get("_semantic_embedding")
        if not embedding:
            continue
        if _cosine(candidate_vec, embedding) >= SUGGESTION_SEMANTIC_SIMILARITY_THRESHOLD:
            return True

    return False


# SQ-07: structural task-extraction gate. A task candidate must have both
# (a) a concrete deliverable/next-action and (b) an owner the user chases.
# We approximate this with four checklist signals; confidence only breaks ties.
_TASK_DELIVERABLE_VERBS = {
    "ship", "draft", "send", "schedule", "define", "review", "build", "write",
    "document", "follow", "follow up", "followup", "confirm", "complete",
    "finish", "deliver", "prepare", "update", "fix", "resolve", "close",
    "clear", "get", "obtain", "share", "publish", "deploy", "release",
    "test", "verify", "check", "ask", "tell", "remind", "call", "meet",
    "discuss", "align", "drive", "lead", "own", "take", "handle", "manage",
    "coordinate", "facilitate", "organize", "create", "make", "produce",
    "submit", "present", "report", "investigate", "research", "analyze",
    "decide", "approve", "sign", "negotiate", "finalize", "review", "revise",
    "edit", "proofread", "circulate", "distribute", "design", "plan",
    "implement", "develop", "code", "migrate", "integrate", "configure",
    "setup", "set", "refactor", "rewrite", "rework", "consolidate",
    "streamline", "simplify", "automate", "enable", "disable", "restore",
    "backfill", "reconcile", "validate", "benchmark", "measure", "track",
}
# Imperatives that look like deliverables but are actually logistics/stance.
# "schedule" is deliberately excluded from this list: scheduling a specific,
# named call or deliverable is a real action item (e.g. "Schedule the customer
# migration call"), whereas generic meeting logistics are excluded by the prompt.
_TASK_LOGISTICS_VERBS = {
    "attend", "hold", "book", "reserve", "block", "endorse",
    "agree", "defer", "revisit", "prioritize", "favour", "favor", "support",
}


def _title_has_deliverable_shape(title):
    """True if the title starts with an action verb followed by an object."""
    if not title:
        return False
    words = title.lower().strip("-–:;• ").split()
    if not words:
        return False
    # Tentative prefix cancels deliverable shape.
    if words[0] in {"maybe", "possibly", "perhaps", "might", "could", "consider"}:
        return False
    first = words[0].rstrip(",")
    if first in _TASK_LOGISTICS_VERBS:
        return False
    if first in _TASK_DELIVERABLE_VERBS:
        return len(words) >= 2
    # Recognize "follow up" / "follow-up" as a compound verb.
    if first in {"follow", "follow-up"} and len(words) >= 2 and words[1] in {"up", "with", "on"}:
        return len(words) >= 3
    return False


def _task_has_owner(candidate):
    """True if the candidate has an explicit assignee."""
    return bool(_clean_text(_candidate_value(candidate, "assigned_to")))


def _task_has_date(candidate):
    """True if the candidate carries a due or follow-up date."""
    return bool(
        _candidate_value(candidate, "due_at") or _candidate_value(candidate, "follow_up_at")
    )


def _task_target_resolvable(note, candidate, decision):
    """True if the task can be attached to an existing project/area or note project link."""
    # Reconciliation found a near-match existing task/project/area.
    if (decision.get("top_match_score") or 0.0) >= NEAR_DUPLICATE_SCORE:
        return True
    # Candidate itself carries a project/area relationship.
    related = (_candidate_value(candidate, "parent") or _candidate_value(candidate, "project"))
    if related:
        return True
    # Source note already links to a project the task could inherit.
    if note is not None:
        if note.type in THREAD_INGEST_SOURCE_TYPES:
            return True
        note_project_links = EntityLink.query.filter(
            EntityLink.source_entity_id == note.id,
            EntityLink.relationship_type.in_(["parent", "related"]),
        ).join(Entity, Entity.id == EntityLink.target_entity_id).filter(
            Entity.type == "project"
        ).first()
        if note_project_links is not None:
            return True
    return False


def _task_structural_score(note, candidate, decision):
    """Return 0-4 structural quality score for a task candidate.

    SQ-07 checklist:
      1. has_owner: assigned_to is present.
      2. has_deliverable_title: verb + object shape (not logistics/stance).
      3. has_date: due_at or follow_up_at present.
      4. target_resolvable: existing near-match, explicit parent project, or
         source note already links to a project.
    """
    score = 0
    if _task_has_owner(candidate):
        score += 1
    if _title_has_deliverable_shape(_candidate_value(candidate, "title")):
        score += 1
    if _task_has_date(candidate):
        score += 1
    if _task_target_resolvable(note, candidate, decision):
        score += 1
    return score


def _task_suggest_ok(note, candidate, decision, confidence):
    """SQ-07: structural score gate for suggesting a task.

    A candidate must have at least half the structural signals to be worth
    a review slot; confidence only breaks ties when capping. Score 4
    candidates are now proposed (auto-create is retired).
    """
    score = _task_structural_score(note, candidate, decision)
    if score < 2:
        return False
    # SQ-09: confidence is the tiebreaker that keeps very low-confidence
    # noise out of the review queue.
    return confidence >= LOW_CONFIDENCE_THRESHOLD


def _reconciliation_confidence(candidate, decision):
    candidate_confidence = _candidate_confidence(candidate)
    decision_confidence = _candidate_confidence(decision)
    if decision_confidence <= 0:
        return candidate_confidence
    if candidate_confidence <= 0:
        return decision_confidence
    return min(candidate_confidence, decision_confidence)


def _find_duplicate_capture_note(content):
    return Entity.query.filter(
        Entity.type == "note",
        Entity.lifecycle != "deleted",
        Entity.content == content,
    ).order_by(Entity.updated_at.desc(), Entity.created_at.desc()).first()


def _apply_assignee_and_record(
    note,
    entity,
    assigned_to,
    confidence,
    evidence,
    applied_changes,
    source,
    actor,
    change_batch_id=None,
    suggestions=None,
    on_behalf=None,
):
    person, link, person_created = _apply_assignee(
        note,
        entity,
        assigned_to,
        confidence,
        evidence,
        source=source,
        actor=actor,
        change_batch_id=change_batch_id,
        suggestions=suggestions,
        on_behalf=on_behalf,
    )
    if person_created:
        _write_event(
            person,
            "created",
            new_value=person.to_dict(),
            actor=actor,
            confidence=confidence,
            reason=evidence,
            source_note_id=note.id,
            change_batch_id=change_batch_id,
        )
        applied_changes.append({
            "type": "entity_created",
            "entity_id": person.id,
            "entity_type": person.type,
            "title": person.title,
            "confidence": confidence,
        })
    if link is not None:
        applied_changes.append({
            "type": "relationship_added",
            "target_entity_id": person.id,
            "relationship_type": "assigned_to",
            "confidence": confidence,
        })


def _apply_assignee(
    note,
    entity,
    assigned_to,
    confidence,
    evidence,
    source,
    actor,
    change_batch_id=None,
    suggestions=None,
    on_behalf=None,
):
    assignee_name = _clean_text(assigned_to)
    if assignee_name is None or entity.type not in {"task", "project"}:
        return None, None, False

    pin_decision = check_pin(entity, "owner", actor, on_behalf=on_behalf)
    if not pin_decision["allow_write"]:
        suggestion = _create_suggestion(
            note,
            suggestion_type=f"update_{entity.type}",
            operation_type="update_entity",
            payload={
                "target_entity_id": entity.id,
                "target_type": entity.type,
                "title": entity.title,
                "fields": {},
                "relationship_type": "derived_from",
                "assigned_to": assignee_name,
                "evidence": evidence,
            },
            confidence=confidence,
            reason=_pin_reason_with_context(evidence, pin_decision["reason"]),
        )
        if suggestion:
            suggestions.append(suggestion.to_dict())
        return None, None, False

    person = _find_existing_entity("person", assignee_name)
    person_created = False
    if person is None:
        person_source = "ai_capture" if source == "ai" else "ai_suggestion"
        person = Entity(
            type="person",
            title=assignee_name,
            content=None,
            status=DEFAULT_STATUS["person"],
            lifecycle="active",
            source=person_source,
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        db.session.add(person)
        db.session.flush()
        _queue_embed_job(person.id, "assignee_auto_create")
        person_created = True

    link = _create_entity_link(
        entity,
        person,
        "assigned_to",
        confidence,
        evidence,
        source=source,
    )
    if link is not None:
        _write_event(
            entity,
            "relationship_added",
            new_value=link.to_dict(),
            actor=actor,
            confidence=confidence,
            reason=evidence,
            change_batch_id=change_batch_id,
        )
        _record_relationship_pin_event(
            entity,
            "assigned_to",
            actor=actor,
            reason="owner relationship pinned",
            confidence=confidence,
            source_note_id=note.id if note is not None else None,
            change_batch_id=change_batch_id,
            on_behalf=on_behalf,
        )
        if entity.type == "task" and entity.follow_up_at is None and not _is_owner(assignee_name, person.id):
            cadence_days = _delegation_cadence_days(person.id)
            entity.follow_up_at = _add_working_days(datetime.now(timezone.utc), cadence_days)
            _write_event(
                entity,
                "ai_updated",
                old_value={"follow_up_at": None},
                new_value={"follow_up_at": entity.follow_up_at.isoformat()},
                actor=actor,
                confidence=confidence,
                reason="delegation cadence",
                source_note_id=note.id if note is not None else None,
                change_batch_id=change_batch_id,
            )
    return person, link, person_created


def _queue_embed_job(entity_id, reason):
    db.session.add(Job(
        job_type="embed",
        entity_id=entity_id,
        payload={"entity_id": entity_id, "reason": reason},
    ))


def _clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _archive_incoming_activity_updates(entity):
    activity_notes = (
        Entity.query.join(
            EntityLink,
            (EntityLink.source_entity_id == Entity.id) & (EntityLink.target_entity_id == entity.id),
        )
        .filter(
            Entity.type == "note",
            Entity.source == "activity_update",
            EntityLink.relationship_type == "activity_update",
            Entity.lifecycle == "active",
        )
        .all()
    )
    for note in activity_notes:
        note.lifecycle = "archived"
        _write_event(
            note,
            "archived",
            old_value={"lifecycle": "active"},
            new_value={"lifecycle": "archived"},
        )


def _delete_incoming_activity_updates(entity):
    activity_note_ids = (
        Entity.query.join(
            EntityLink,
            (EntityLink.source_entity_id == Entity.id) & (EntityLink.target_entity_id == entity.id),
        )
        .filter(
            Entity.type == "note",
            Entity.source == "activity_update",
            EntityLink.relationship_type == "activity_update",
        )
        .with_entities(Entity.id)
        .all()
    )
    for (note_id,) in activity_note_ids:
        db.session.delete(db.session.get(Entity, note_id))

__all__ = ['datetime', 'time', 'timezone', 'timedelta', 'hashlib', 'json', 'logging', 're', 'time_module', 'Response', 'current_app', 'jsonify', 'request', 'stream_with_context', 'func', 'or_', 'text', 'flag_modified', 'selectinload', 'db', 'AiSuggestion', 'AppSetting', 'Decision', 'Entity', 'EntityChunk', 'EntityEvent', 'EntityLink', 'EntityTag', 'Job', 'Tag', '_iso', 'runtime_health', 'attention_for_entity', 'today_attention_count', 'today_attention_items', 'narrate_event', 'title_or_placeholder', 'logger', 'TOPIC_CLUSTER_SIMILARITY', 'TOPIC_CLUSTER_TIME_BUDGET_MS', 'STATUS_BY_TYPE', 'ENTITY_TYPES', 'PRIORITY_LEVELS', 'PRIORITY_ORDER', 'DEFAULT_STATUS', 'VALID_STATUS', 'VALID_LIFECYCLE', 'WRITABLE_FIELDS', 'RELATIONSHIP_PROPERTY_KEYS', 'RELATIONSHIP_TYPES', 'RELATIONSHIP_COMPATIBILITY', 'DEFAULT_OWNER_ALIASES', 'DEFAULT_DELEGATION_CADENCE_DAYS', 'AUTO_APPLY_CONFIDENCE', 'LOW_CONFIDENCE_THRESHOLD', 'RISKY_ENTITY_CREATION_TYPES', 'THREAD_INGEST_SOURCE_TYPES', 'SUGGEST_ONLY_CREATION_TYPES', 'TASK_SUGGESTION_CAP_PER_NOTE', 'NEAR_DUPLICATE_SCORE', 'CAPTURE_INTENTS', 'INBOX_INTENT_PRIORITY', 'INTENT_SUGGESTION_CONFIDENCE_FLOOR', 'INTENT_ROUTE_CONFIDENCE', 'INTENT_ROUTE_MAX_CONTENT_CHARS', 'UPDATE_TARGET_SIMILARITY', 'SUGGESTION_DUPLICATE_MEMORY_DAYS', 'SUGGESTION_SEMANTIC_MEMORY_DAYS', 'SUGGESTION_SEMANTIC_SIMILARITY_THRESHOLD', 'COMPACT_LINK_COUNT_RULES', 'CAPTURE_STREAM_EVENTS', '_format_capture_sse_event', '_create_capture_note', '_entity_brief', '_event_reason_for_applied_change', '_matched_entity_for_applied_change', '_enrich_applied_change', '_enrich_suggestion_item', '_capture_result_payload', '_count_extraction_candidates', '_count_capture_summarize_jobs', '_timeline_thread_entity_ids', '_timeline_thread_map', 'ENTITY_TYPE_PLURAL', 'ENTITY_TYPE_BY_PLURAL', 'MENTION_TYPES_PER_GROUP', 'DONE_TASK_STATUSES', 'OPEN_TASK_STATUSES', 'FOLLOW_UP_ENTITY_TYPES', 'STALE_PROJECT_DAYS', 'ARCHIVAL_SUGGESTION_DAYS', 'PERSON_PULSE_QUIET_DAYS', '_build_today_payload', '_decisions_count_for_entity', '_needs_review_query', '_needs_review_count', '_pending_suggestions_count', '_entity_with_attention', '_inherited_task_priorities', '_staleness_days_for', '_child_task_ids_by_project', '_project_staleness_days', '_latest_event_at', '_blocking_impact_counts', '_agent_event_item', '_agent_suggestion_item', '_agent_failed_note_item', '_audit_entity', '_clear_review_resolution', '_mark_review_resolved', '_merge_entities', 'TYPE_CONVERSIONS', 'CONVERSION_STATUS_MAP', 'CAPTURE_CHANGE_EVENT_TYPES', 'DEFAULT_ACTIVITY_UPDATES_PAGE_SIZE', 'MAX_ACTIVITY_UPDATES_PAGE_SIZE', 'DETAIL_ACTIVITY_UPDATES_LIMIT', 'ACTIVITY_UPDATE_DEDUP_HOURS', 'NEAR_DUPLICATE_ACTIVITY_UPDATE_THRESHOLD', '_normalize_activity_update_content', '_activity_update_content_tokens', '_activity_update_content_similarity', '_recent_activity_update_notes', '_find_near_duplicate_activity_update', '_create_activity_update_note', '_refresh_delegation_cadence', '_apply_activity_update_policy', 'VALID_DISMISS_REASONS', '_entity_query', '_load_entity', '_relationship_detail_sections', '_task_detail_sections', '_activity_updates_order', '_activity_updates_query', '_serialize_activity_update', '_activity_updates_section', '_fetch_activity_updates', '_project_detail_sections', '_area_detail_sections', '_note_detail_sections', '_person_detail_sections', '_resource_detail_sections', '_section', '_link_items', '_related_entity_for_link', '_entity_map_for_links', '_attach_project_task_counts', '_attach_project_context', '_attach_task_context', '_enrich_search_results_with_task_context', '_attach_compact_link_counts', '_replace_tags', '_add_tag', '_write_event', '_validate_status', '_is_relationship_compatible', '_validate_lifecycle', '_validate_properties', '_find_relationship_property_key', '_parse_datetime', '_parse_datetime_or_error', '_error', '_title_from_content', '_activity_update_title', '_capture_thread_id_from_data', '_capture_thread_entity_dict', '_run_basic_capture_extraction', '_extract_decision_candidates', '_decision_thread_id_for_note', '_valid_decided_by', '_apply_capture_extraction_metadata', '_capture_intent_route', '_process_capture_extraction', '_route_capture_update_intent', '_resolve_update_target', '_embedding_update_target', '_reconcile_capture_candidates', '_apply_reconciliation_decision', '_link_task_to_note_projects', '_touch_parent_projects', '_apply_entity_update', '_get_app_setting', '_app_setting_row', '_set_app_setting', '_owner_person_id', '_owner_aliases', '_is_owner', '_record_owner_identity_change', '_delegation_cadence_days', '_add_working_days', '_latest_activity_updates', '_ensure_utc', '_days_since', '_person_open_tasks', '_project_open_tasks', '_person_current_load', '_person_pulse', '_person_pulse_headline', '_person_recent_notes', '_person_meeting_prep', '_meeting_prep_headline', '_coordination_radar', '_coordination_radar_people', '_today_dependency_interventions', '_coordination_radar_projects', '_aggregate_attention_reasons', '_thread_attention_score', '_entity_recent_notes', '_thread_last_context', '_thread_last_activity_at', '_build_thread_key_items', '_person_thread', '_project_thread', '_people_threads', '_project_threads', '_notes_linked_to_parent_entities', '_topic_thread_name', '_topic_threads', '_project_pulse', '_task_dependency_watch', '_project_dependency_watch_headline', '_project_pulse_headline', '_delegations_quiet', '_parse_iso_date', '_create_suggestion', '_creates_blocks_cycle', 'EXPLICIT_MENTION_PATTERN', '_apply_explicit_mentions', '_create_entity_link', '_find_existing_entity', '_find_existing_person', '_person_carries_work', '_default_relationship_type', '_is_create_suggestion_operation', '_accepted_suggestion_link', '_candidate_link_endpoints', '_candidate_value', '_candidate_confidence', '_apply_capture_intent', '_capture_intent', '_sort_inbox_notes', '_inbox_sort_key', '_capture_suggestion_reason', '_append_capture_suggestion', '_should_emit_capture_suggestion', '_task_candidate_looks_tentative', '_status_keyword_is_affirmed', '_status_term_is_negated', '_status_change_is_explicit', '_append_decision_suggestions', '_FOLLOW_UP_OWNER_RE', '_collect_work_carrying_persons', '_suggestion_task_structural_score', '_cap_and_group_task_suggestions', '_expire_stale_suggestion_if_needed', '_expire_suggestion', '_suggested_fields_would_change', '_relationship_exists_between', '_suggestion_fingerprint', '_normalized_suggestion_payload', '_existing_pending_suggestion', '_semantic_embedding_text', '_recently_resolved_duplicate', '_recently_resolved_semantic_duplicate', '_TASK_DELIVERABLE_VERBS', '_TASK_LOGISTICS_VERBS', '_title_has_deliverable_shape', '_task_has_owner', '_task_has_date', '_task_target_resolvable', '_task_structural_score', '_task_suggest_ok', '_reconciliation_confidence', '_find_duplicate_capture_note', '_apply_assignee_and_record', '_apply_assignee', '_queue_embed_job', '_clean_text', '_archive_incoming_activity_updates', '_delete_incoming_activity_updates']
from services.v4_trust import check_pin, record_pin, relationship_pin_field
