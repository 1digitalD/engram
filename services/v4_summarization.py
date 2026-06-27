"""Entity summarization service.

Reads all notes linked to an entity in chronological order and synthesizes
a current-state summary. Results are persisted on the entity so they can be
served instantly until invalidated by a new linked note.

Trigger paths:
  - Async: a "summarize" job is queued whenever a note is linked to an entity
    that already has a summary (auto-refresh) or via the on-demand API endpoint.
  - On-demand: POST /entities/:id/summarize calls summarize_entity() directly.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from utils import get_openai_client
from services.llm_models import resolve_chat_model
from services.job_worker import register_handler

logger = logging.getLogger(__name__)

SUMMARIZATION_MODEL = resolve_chat_model("OPENAI_SUMMARIZATION_MODEL")

SYSTEM_PROMPT = """\
You are a knowledge assistant synthesizing the current state of a workspace entity
from a chronological log of notes that reference it.

Write a concise, present-tense summary (3–6 sentences) that captures:
- What this entity is and its current status
- Key decisions or outcomes recorded across the notes
- Open questions, blockers, or next actions still outstanding
- Who is involved and what they are responsible for

Do not enumerate every note. Synthesize into a coherent current-state picture.
Omit notes that add no new information. Be specific — names, dates, and decisions
matter more than vague qualifiers.
"""


def summarize_entity(entity_id: str) -> str | None:
    """Generate and persist a summary for the given entity. Returns the summary text."""
    from extensions import db
    from models import Entity, EntityLink, EntityEvent

    entity = db.session.get(Entity, entity_id)
    if entity is None or entity.lifecycle == "deleted":
        return None

    notes = _linked_notes(entity_id)
    if not notes:
        return None

    if not os.getenv("OPENAI_API_KEY"):
        return None

    try:
        from flask import current_app
        if current_app.config.get("TESTING") and os.getenv("ENGRAM_ALLOW_TEST_AI") != "1":
            return None
    except RuntimeError:
        pass

    summary = _call_model(entity, notes)
    if not summary:
        return None

    now = datetime.now(timezone.utc)
    entity.ai_summary = summary
    entity.ai_summarized_at = now
    db.session.add(EntityEvent(
        entity_id=entity_id,
        event_type="ai_summarized",
        actor="agent:v4-summarize",
        new_value={"summary": summary, "note_count": len(notes)},
    ))
    db.session.commit()
    logger.info("Summarized entity %s from %d notes", entity_id, len(notes))
    return summary


def is_summary_stale(entity) -> bool:
    """True if any linked note was created after the last summarization."""
    if entity.ai_summarized_at is None:
        return False  # no summary yet — not stale, just absent
    from extensions import db
    from models import Entity, EntityLink
    newest = (
        db.session.query(Entity.created_at)
        .join(EntityLink, EntityLink.source_entity_id == Entity.id)
        .filter(
            EntityLink.target_entity_id == entity.id,
            Entity.type == "note",
            Entity.lifecycle == "active",
        )
        .order_by(Entity.created_at.desc())
        .scalar()
    )
    if newest is None:
        return False
    summarized = entity.ai_summarized_at
    if summarized.tzinfo is None:
        summarized = summarized.replace(tzinfo=timezone.utc)
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    return newest > summarized


def queue_summarize_if_needed(entity_id: str, has_existing_summary: bool) -> None:
    """Queue a background summarize job. Skips if one is already pending."""
    from extensions import db
    from models import Job
    already_queued = db.session.query(Job).filter(
        Job.entity_id == entity_id,
        Job.job_type == "summarize",
        Job.status.in_(["pending", "running"]),
    ).first()
    if already_queued:
        return
    db.session.add(Job(
        job_type="summarize",
        entity_id=entity_id,
        payload={"entity_id": entity_id},
    ))


# ── Job handler ───────────────────────────────────────────────────────────────

@register_handler("summarize")
def handle_summarize_job(payload):
    entity_id = (payload or {}).get("entity_id")
    if not entity_id:
        raise ValueError("summarize job payload missing entity_id")
    summarize_entity(entity_id)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _linked_notes(entity_id: str) -> list[dict]:
    """Return all active notes linked to this entity, oldest first.

    Notes may point to an entity (for example activity updates) or an entity may
    point to a note (for example task derived_from note).
    """
    from extensions import db
    from models import Entity, EntityLink

    incoming_rows = (
        db.session.query(Entity, EntityLink)
        .join(EntityLink, EntityLink.source_entity_id == Entity.id)
        .filter(
            EntityLink.target_entity_id == entity_id,
            Entity.type == "note",
            Entity.lifecycle == "active",
        )
        .order_by(Entity.created_at.asc())
        .all()
    )
    outgoing_rows = (
        db.session.query(Entity, EntityLink)
        .join(EntityLink, EntityLink.target_entity_id == Entity.id)
        .filter(
            EntityLink.source_entity_id == entity_id,
            Entity.type == "note",
            Entity.lifecycle == "active",
        )
        .order_by(Entity.created_at.asc())
        .all()
    )

    combined = []
    seen = set()
    for e, link in incoming_rows + outgoing_rows:
        key = (e.id, link.id)
        if key in seen:
            continue
        seen.add(key)
        combined.append((e, link))

    combined.sort(key=lambda row: row[0].created_at or datetime.min.replace(tzinfo=timezone.utc))
    return [
        {
            "title": e.title,
            "content": e.content or "",
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "relationship_type": link.relationship_type,
        }
        for e, link in combined
    ]


def _call_model(entity, notes: list[dict]) -> str | None:
    from models import Entity
    entity_block = (
        f"Entity type: {entity.type}\n"
        f"Title: {entity.title}\n"
        f"Status: {entity.status}\n"
    )
    if entity.due_at:
        entity_block += f"Due: {entity.due_at.date()}\n"
    if entity.content:
        entity_block += f"Description: {entity.content}\n"

    notes_block = "\n\n".join(
        f"[{n['created_at'][:10] if n['created_at'] else 'unknown date'}] "
        f"{n['title'] or '(untitled)'}\n{n['content']}"
        for n in notes
    )

    user_content = f"ENTITY:\n{entity_block}\n\nNOTES (chronological):\n{notes_block}"

    try:
        response = get_openai_client().chat.completions.create(
            model=SUMMARIZATION_MODEL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content[:20000]},
            ],
        )
        return (response.choices[0].message.content or "").strip() or None
    except Exception as e:
        logger.error("summarization model call failed for entity %s: %s", entity.id, e)
        return None

