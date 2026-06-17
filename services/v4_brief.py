"""Ranked daily brief: an LLM judgment pass over the workspace.

/today is date arithmetic — items without dates never surface and dated
items get equal billing. The brief reads the current state (projects,
open loops, recent updates) and *decides* what leads, with a why-now
reason per item. Cached in app_settings; regenerated when stale.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from utils import get_openai_client

logger = logging.getLogger(__name__)

BRIEF_MODEL = os.getenv("OPENAI_BRIEF_MODEL", "gpt-4o")
BRIEF_MAX_AGE_HOURS = 6
BRIEF_MAX_ITEMS = 7
_BRIEF_CACHE = {"brief": None, "generated_at": None}

SYSTEM_PROMPT = """You are the chief of staff for a personal knowledge workspace. \
Today's date: {today}.

You receive a JSON snapshot of the workspace: active projects, open tasks, \
recent activity updates, compact Today runtime buckets, and coordination \
radar summaries. Decide what the user should pay attention to TODAY, without \
them having to look for it.

Ranking judgment — weigh, in rough order:
1. Hard commitments at risk: overdue or due-today items, promised follow-ups.
2. Blocked/waiting items where the blocker can be acted on or chased today.
3. Momentum: projects with recent activity that need a decision or next step.
4. Quiet risks: important projects going stale, delegations with no news.
5. Coordination risk: people or projects called out by the coordination radar.
Do NOT pad the list — fewer, sharper items beat a full list. Skip routine
items that are simply "in progress" with nothing to decide or do today.

Return JSON only:
{{
  "narrative": "1-2 sentences: the shape of the day in plain language",
  "items": [{{
    "entity_id": "id from the snapshot",
    "title": "the entity's title verbatim",
    "why_now": "one concrete sentence: why this needs attention today",
    "urgency": 1-5
  }}]
}}
At most {max_items} items, ordered most-important first. entity_id MUST be \
copied exactly from the snapshot; never invent ids."""


def _snapshot():
    """Compact workspace snapshot for the ranking prompt."""
    from models import Entity, EntityLink
    from api.v4_entities import _build_today_payload, _coordination_radar

    now = datetime.now(timezone.utc)

    def _e(entity, **extra):
        item = {
            "id": entity.id,
            "type": entity.type,
            "title": entity.title,
            "status": entity.status,
            "due_at": entity.due_at.isoformat()[:10] if entity.due_at else None,
            "follow_up_at": entity.follow_up_at.isoformat()[:10] if entity.follow_up_at else None,
            "updated_at": entity.updated_at.isoformat()[:10] if entity.updated_at else None,
        }
        priority = (entity.properties or {}).get("priority")
        if priority:
            item["priority"] = priority
        if entity.ai_summary:
            item["summary"] = entity.ai_summary[:200]
        item.update(extra)
        return item

    today = _build_today_payload(now)
    coordination_radar = _coordination_radar(now)

    projects = (
        Entity.query
        .filter(Entity.type == "project", Entity.lifecycle == "active", Entity.status == "active")
        .order_by(Entity.updated_at.desc())
        .limit(30)
        .all()
    )
    open_tasks = (
        Entity.query
        .filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(["open", "in_progress", "waiting", "blocked"]),
        )
        .order_by(Entity.updated_at.desc())
        .limit(60)
        .all()
    )
    recent_updates = (
        Entity.query
        .filter(
            Entity.type == "note",
            Entity.source == "activity_update",
            Entity.lifecycle == "active",
            Entity.updated_at >= now - timedelta(days=5),
        )
        .order_by(Entity.updated_at.desc())
        .limit(20)
        .all()
    )

    # Map each recent update to its target entity for context.
    update_links = {}
    if recent_updates:
        rows = EntityLink.query.filter(
            EntityLink.source_entity_id.in_([n.id for n in recent_updates]),
            EntityLink.relationship_type == "activity_update",
        ).all()
        update_links = {link.source_entity_id: link.target_entity_id for link in rows}

    return {
        "generated_at": now.isoformat(),
        "projects": [_e(p) for p in projects],
        "open_tasks": [_e(t) for t in open_tasks],
        "recent_updates": [
            {
                "target_entity_id": update_links.get(n.id),
                "content": (n.content or "")[:300],
                "at": n.updated_at.isoformat()[:10] if n.updated_at else None,
            }
            for n in recent_updates
        ],
        "today": {
            "overdue": [
                {"id": entity["id"], "title": entity["title"], "status": entity["status"]}
                for entity in today.get("overdue", [])[:5]
            ],
            "due_today": [
                {"id": entity["id"], "title": entity["title"], "status": entity["status"]}
                for entity in today.get("due_today", [])[:5]
            ],
            "delegations_quiet": [
                {
                    "id": entity["id"],
                    "title": entity["title"],
                    "status": entity["status"],
                    "days_silent": entity.get("days_silent"),
                }
                for entity in today.get("delegations_quiet", [])[:5]
            ],
            "dependency_interventions": [
                {
                    "kind": item.get("kind"),
                    "label": item.get("label"),
                    "entity": {
                        "id": item["entity"]["id"],
                        "title": item["entity"]["title"],
                        "status": item["entity"]["status"],
                    },
                }
                for item in today.get("dependency_interventions", [])[:5]
            ],
            "unscheduled_attention_tasks": [
                {"id": entity["id"], "title": entity["title"], "status": entity["status"]}
                for entity in today.get("unscheduled_attention_tasks", [])[:5]
            ],
            "stale_projects": [
                {
                    "id": entity["id"],
                    "title": entity["title"],
                    "status": entity["status"],
                    "stale_days": entity.get("stale_days"),
                }
                for entity in (today.get("stale_projects", []) + today.get("suggested_archival", []))[:5]
            ],
        },
        "coordination_radar": coordination_radar,
    }


def _heuristic_brief(now=None):
    """Runtime-only fallback brief when model generation is unavailable."""
    from api.v4_entities import _build_today_payload, _coordination_radar

    now = now or datetime.now(timezone.utc)
    today = _build_today_payload(now)
    radar = _coordination_radar(now)
    items = []
    seen = set()

    def add_entity(entity, why_now, urgency):
        entity_id = entity.get("id") or entity.get("entity_id")
        entity_type = entity.get("type") or entity.get("entity_type")
        title = entity.get("title")
        status = entity.get("status")
        if not entity_id or entity_id in seen or not title:
            return
        seen.add(entity_id)
        items.append({
            "entity_id": entity_id,
            "entity_type": entity_type,
            "title": title,
            "status": status,
            "why_now": why_now[:300],
            "urgency": max(1, min(int(urgency), 5)),
        })

    for entity in (today.get("overdue") or [])[:2]:
        add_entity(entity, "Overdue and still open, so it needs a decision or push today.", 5)
    for entity in (today.get("due_today") or [])[:2]:
        add_entity(entity, "Due today, so it is on the critical path for the day.", 4)
    for item in (today.get("dependency_interventions") or [])[:2]:
        label = item.get("label") or "Blocked work needs intervention today."
        urgency = 5 if item.get("kind") == "blocked_by" else 4
        add_entity(item.get("entity") or {}, label, urgency)
    for entity in (today.get("delegations_quiet") or [])[:2]:
        days_silent = entity.get("days_silent")
        if isinstance(days_silent, int) and days_silent > 0:
            why_now = f"No update for {days_silent} days since follow-up came due."
        else:
            why_now = "Delegated work has gone quiet and needs a nudge."
        add_entity(entity, why_now, 4)
    for entity in (today.get("blocked_tasks") or [])[:1]:
        add_entity(entity, "Blocked work needs an unblock path or a clear next move.", 4)
    for entity in (today.get("unscheduled_attention_tasks") or [])[:2]:
        add_entity(entity, "Undated but high-impact or stale work is drifting without a plan.", 3)
    for entity in (today.get("stale_projects") or [])[:1]:
        stale_days = entity.get("stale_days")
        why_now = (
            f"No meaningful activity for {stale_days} days; check whether this project still has momentum."
            if isinstance(stale_days, int) and stale_days > 0
            else "No meaningful activity recently; confirm whether this project still matters."
        )
        add_entity(entity, why_now, 2)
    for entity in (today.get("suggested_archival") or [])[:1]:
        stale_days = entity.get("stale_days")
        why_now = (
            f"No meaningful activity for {stale_days} days; consider archiving it."
            if isinstance(stale_days, int) and stale_days > 0
            else "No meaningful activity recently; consider archiving it."
        )
        add_entity(entity, why_now, 2)
    for item in (radar.get("people") or [])[:1]:
        add_entity(
            {
                "id": item.get("entity_id"),
                "entity_id": item.get("entity_id"),
                "type": item.get("entity_type"),
                "entity_type": item.get("entity_type"),
                "title": item.get("title"),
                "status": "active",
            },
            item.get("headline") or "A teammate needs coordination attention.",
            3,
        )
    for item in (radar.get("projects") or [])[:1]:
        add_entity(
            {
                "id": item.get("entity_id"),
                "entity_id": item.get("entity_id"),
                "type": item.get("entity_type"),
                "entity_type": item.get("entity_type"),
                "title": item.get("title"),
                "status": "active",
            },
            item.get("headline") or "A project needs coordination attention.",
            3,
        )

    if not items:
        snapshot = _snapshot()
        if not snapshot["projects"] and not snapshot["open_tasks"] and not snapshot["recent_updates"]:
            return None

    headline_parts = []
    if today.get("overdue"):
        headline_parts.append(f"{len(today['overdue'])} overdue")
    if today.get("dependency_interventions"):
        headline_parts.append(f"{len(today['dependency_interventions'])} blockers to resolve")
    if today.get("delegations_quiet"):
        headline_parts.append(f"{len(today['delegations_quiet'])} quiet delegations")
    if not headline_parts and items:
        headline_parts.append("A few runtime signals need attention")
    elif not headline_parts:
        headline_parts.append("Clear runway right now")

    return {
        "narrative": ". ".join(headline_parts) + ".",
        "items": items[:BRIEF_MAX_ITEMS],
        "generated_at": now.isoformat(),
        "model": "heuristic",
    }


def generate_brief():
    """Run the ranking pass. Returns the brief dict or None when unavailable."""
    try:
        from flask import current_app
        if current_app.config.get("TESTING") and os.getenv("ENGRAM_ALLOW_TEST_AI") != "1":
            return None
    except RuntimeError:
        pass
    if not os.getenv("OPENAI_API_KEY"):
        return None

    snapshot = _snapshot()
    today = datetime.now(timezone.utc).date().isoformat()

    try:
        response = get_openai_client().chat.completions.create(
            model=BRIEF_MODEL,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.format(today=today, max_items=BRIEF_MAX_ITEMS)},
                {"role": "user", "content": json.dumps(snapshot)[:24000]},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)
    except Exception as exc:
        logger.error("brief generation failed: %s", exc)
        return None

    return _validate_brief(parsed)


def _validate_brief(parsed):
    """Drop hallucinated ids; clamp shape."""
    from models import Entity

    if not isinstance(parsed, dict):
        return None
    items = []
    for item in (parsed.get("items") or [])[:BRIEF_MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        entity_id = item.get("entity_id")
        entity = Entity.query.filter(
            Entity.id == entity_id, Entity.lifecycle == "active"
        ).first() if entity_id else None
        if entity is None:
            continue
        try:
            urgency = max(1, min(int(item.get("urgency") or 3), 5))
        except (TypeError, ValueError):
            urgency = 3
        items.append({
            "entity_id": entity.id,
            "entity_type": entity.type,
            "title": entity.title,
            "status": entity.status,
            "why_now": str(item.get("why_now") or "")[:300],
            "urgency": urgency,
        })

    narrative = str(parsed.get("narrative") or "")[:500]
    return {
        "narrative": narrative,
        "items": items,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": BRIEF_MODEL,
    }


def _brief_cache_fresh(now=None):
    now = now or datetime.now(timezone.utc)
    generated_at = _BRIEF_CACHE.get("generated_at")
    if not generated_at or _BRIEF_CACHE.get("brief") is None:
        return False
    try:
        created = datetime.fromisoformat(generated_at)
    except (TypeError, ValueError):
        return False
    return now - created < timedelta(hours=BRIEF_MAX_AGE_HOURS)


def get_brief(force=False):
    """Return the runtime brief, using an in-process cache when fresh."""
    now = datetime.now(timezone.utc)
    cached = _BRIEF_CACHE.get("brief")
    if cached and not force and _brief_cache_fresh(now):
        return cached, True

    brief = generate_brief()
    if brief is None:
        brief = _heuristic_brief(now)
    if brief is None:
        return (cached, True) if cached and _brief_cache_fresh(now) else (None, False)

    _BRIEF_CACHE["brief"] = brief
    _BRIEF_CACHE["generated_at"] = brief.get("generated_at") or now.isoformat()
    return brief, False
