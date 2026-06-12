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
BRIEF_CACHE_KEY = "daily_brief"
BRIEF_MAX_AGE_HOURS = 6
BRIEF_MAX_ITEMS = 7

SYSTEM_PROMPT = """You are the chief of staff for a personal knowledge workspace. \
Today's date: {today}.

You receive a JSON snapshot of the workspace: active projects (with recent \
activity), open tasks (with status, due/follow-up dates, blockers), and the \
most recent activity updates. Decide what the user should pay attention to \
TODAY, without them having to look for it.

Ranking judgment — weigh, in rough order:
1. Hard commitments at risk: overdue or due-today items, promised follow-ups.
2. Blocked/waiting items where the blocker can be acted on or chased today.
3. Momentum: projects with recent activity that need a decision or next step.
4. Quiet risks: important projects going stale, delegations with no news.
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


def get_brief(force=False):
    """Return the cached brief, regenerating when stale or forced."""
    from extensions import db
    from models import AppSetting

    setting = db.session.get(AppSetting, BRIEF_CACHE_KEY)
    cached = setting.value if setting else None
    if cached and not force:
        try:
            generated_at = datetime.fromisoformat(cached.get("generated_at"))
            if datetime.now(timezone.utc) - generated_at < timedelta(hours=BRIEF_MAX_AGE_HOURS):
                return cached, True
        except (TypeError, ValueError):
            pass

    brief = generate_brief()
    if brief is None:
        # No model available or generation failed: serve stale cache if any.
        return (cached, True) if cached else (None, False)

    if setting is None:
        setting = AppSetting(key=BRIEF_CACHE_KEY, value=brief)
        db.session.add(setting)
    else:
        setting.value = brief
    db.session.commit()
    return brief, False
