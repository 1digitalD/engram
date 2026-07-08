"""Receipt-grounded follow-up nudge drafting for waiting-on commitments."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone

from extensions import db
from models import Entity, EntityLink, _iso
from services.llm_models import resolve_chat_model
from utils import get_openai_client

logger = logging.getLogger(__name__)

NUDGE_DRAFT_MODEL = resolve_chat_model("OPENAI_NUDGE_DRAFT_MODEL")

SYSTEM_PROMPT = """You draft polite follow-up messages for delegated work in a personal workspace.
Use ONLY the provided commitment context and receipts. Reference the original ask and when it was made.
Never invent facts, meetings, dates, or quotes that are not supported by the receipts.

Tone: helpful and direct, not passive-aggressive. Keep the draft short (2-4 sentences) and ready to paste.

Return JSON only:
{
  "draft": "the message text ready to copy-paste"
}"""


def gather_commitment_context(commitment_id: str) -> dict:
    """Load commitment facts and receipt refs for nudge drafting."""
    task = db.session.get(Entity, commitment_id)
    if task is None or task.lifecycle == "deleted" or task.type != "task":
        raise LookupError("commitment not found")

    owner = _linked_entity(task.id, "assigned_to", target_types={"person"})
    space = _linked_entity(task.id, "parent", target_types={"project", "area"})
    source_note = _source_note_for_task(task)
    latest_update = _latest_activity_update(task.id)

    original_ask = (task.title or "").strip() or "Untitled commitment"
    committed_at = _committed_at(task, source_note)
    receipts = _build_receipts(
        task=task,
        owner=owner,
        space=space,
        source_note=source_note,
        latest_update=latest_update,
        committed_at=committed_at,
        original_ask=original_ask,
    )

    return {
        "commitment_id": task.id,
        "title": task.title,
        "status": task.status,
        "original_ask": original_ask,
        "committed_at": committed_at,
        "due_at": _iso(task.due_at),
        "follow_up_at": _iso(task.follow_up_at),
        "owner": _entity_ref(owner),
        "space": _entity_ref(space),
        "source_note": _note_receipt(source_note, original_ask),
        "last_update": latest_update,
        "receipts": receipts,
    }


def build_user_prompt(context: dict) -> str:
    """Serialize commitment context for the nudge LLM prompt."""
    lines = [
        f"Original ask: {context['original_ask']}",
        f"Committed date: {context.get('committed_at') or 'unknown'}",
    ]
    if (context.get("owner") or {}).get("title"):
        lines.append(f"Owner: {context['owner']['title']}")
    if (context.get("space") or {}).get("title"):
        lines.append(f"Space: {context['space']['title']}")
    if context.get("due_at"):
        lines.append(f"Due: {context['due_at']}")
    if context.get("follow_up_at"):
        lines.append(f"Follow-up due: {context['follow_up_at']}")
    if (context.get("last_update") or {}).get("content"):
        lines.append(f"Last update: {context['last_update']['content']}")
    if (context.get("source_note") or {}).get("quote"):
        lines.append(f"Source quote: {context['source_note']['quote']}")

    lines.append("Receipts:")
    for receipt in context.get("receipts") or []:
        label = receipt.get("label") or receipt.get("field") or receipt.get("kind")
        value = receipt.get("value") or receipt.get("quote") or ""
        lines.append(f"- {label}: {value}")

    return "\n".join(lines)


def draft_nudge(commitment_id: str) -> dict:
    """Draft a follow-up nudge from commitment receipts. Never auto-sends."""
    context = gather_commitment_context(commitment_id)
    draft_text = _generate_draft_text(context)
    return {
        "commitment_id": context["commitment_id"],
        "draft": draft_text,
        "original_ask": context["original_ask"],
        "committed_at": context.get("committed_at"),
        "receipts": context.get("receipts") or [],
        "auto_sent": False,
    }


def _generate_draft_text(context: dict) -> str:
    if _llm_enabled():
        try:
            response = get_openai_client().chat.completions.create(
                model=NUDGE_DRAFT_MODEL,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(context)},
                ],
            )
            payload = json.loads(response.choices[0].message.content or "{}")
            draft = (payload.get("draft") or "").strip()
            if draft:
                return draft
        except Exception:
            logger.exception("nudge draft LLM failed for %s", context.get("commitment_id"))
    return _heuristic_draft(context)


def _heuristic_draft(context: dict) -> str:
    owner = (context.get("owner") or {}).get("title") or "there"
    ask = context.get("original_ask") or "this item"
    committed = _format_date_label(context.get("committed_at"))
    parts = [f"Hi {owner},"]
    if committed:
        parts.append(f"Following up on {ask} from {committed}.")
    else:
        parts.append(f"Following up on {ask}.")
    quote = (context.get("source_note") or {}).get("quote")
    if quote:
        parts.append(f'You committed: "{quote}"')
    parts.append("Any update on where this stands?")
    return " ".join(parts)


def _llm_enabled() -> bool:
    if not os.getenv("OPENAI_API_KEY"):
        return False
    try:
        from flask import current_app

        if current_app.config.get("TESTING") and os.getenv("ENGRAM_ALLOW_TEST_AI") != "1":
            return False
    except RuntimeError:
        return True
    return True


def _linked_entity(task_id: str, relationship_type: str, *, target_types: set[str]):
    row = (
        db.session.query(Entity)
        .join(EntityLink, EntityLink.target_entity_id == Entity.id)
        .filter(
            EntityLink.source_entity_id == task_id,
            EntityLink.relationship_type == relationship_type,
            Entity.type.in_(target_types),
            Entity.lifecycle == "active",
        )
        .first()
    )
    return row


def _source_note_for_task(task: Entity):
    return (
        db.session.query(Entity)
        .join(EntityLink, EntityLink.target_entity_id == Entity.id)
        .filter(
            EntityLink.source_entity_id == task.id,
            EntityLink.relationship_type == "derived_from",
            Entity.type == "note",
            Entity.lifecycle == "active",
        )
        .order_by(Entity.created_at.asc())
        .first()
    )


def _latest_activity_update(task_id: str):
    row = (
        db.session.query(Entity.created_at, Entity.content)
        .join(EntityLink, EntityLink.source_entity_id == Entity.id)
        .filter(
            EntityLink.target_entity_id == task_id,
            EntityLink.relationship_type == "activity_update",
            Entity.type == "note",
            Entity.lifecycle == "active",
        )
        .order_by(Entity.created_at.desc())
        .first()
    )
    if not row:
        return None
    created_at, content = row
    return {
        "at": _iso(created_at),
        "content": (content or "").strip()[:280] or None,
    }


def _committed_at(task: Entity, source_note: Entity | None) -> str | None:
    candidates = [
        _iso(task.created_at),
        _iso(task.follow_up_at),
        _iso(source_note.created_at) if source_note else None,
    ]
    for value in candidates:
        if value:
            return value[:10]
    return None


def _build_receipts(
    *,
    task: Entity,
    owner: Entity | None,
    space: Entity | None,
    source_note: Entity | None,
    latest_update: dict | None,
    committed_at: str | None,
    original_ask: str,
) -> list[dict]:
    receipts = [
        {
            "kind": "task",
            "entity_id": task.id,
            "field": "title",
            "label": "original ask",
            "value": original_ask,
        }
    ]
    if committed_at:
        receipts.append(
            {
                "kind": "task",
                "entity_id": task.id,
                "field": "committed_at",
                "label": "committed date",
                "value": committed_at,
            }
        )
    if task.due_at:
        receipts.append(
            {
                "kind": "task",
                "entity_id": task.id,
                "field": "due_at",
                "label": "due date",
                "value": _iso(task.due_at),
            }
        )
    if owner:
        receipts.append(
            {
                "kind": "person",
                "entity_id": owner.id,
                "field": "title",
                "label": "owner",
                "value": owner.title,
            }
        )
    if space:
        receipts.append(
            {
                "kind": space.type,
                "entity_id": space.id,
                "field": "title",
                "label": "space",
                "value": space.title,
            }
        )
    note_receipt = _note_receipt(source_note, original_ask)
    if note_receipt:
        receipts.append(note_receipt)
    if latest_update and latest_update.get("content"):
        receipts.append(
            {
                "kind": "note",
                "entity_id": task.id,
                "field": "last_update",
                "label": "last update",
                "value": latest_update["content"],
            }
        )
    return receipts


def _note_receipt(note: Entity | None, needle: str) -> dict | None:
    if note is None:
        return None
    quote = _quote_from_note(note.content or "", needle)
    return {
        "kind": "note",
        "entity_id": note.id,
        "field": "content",
        "label": "source note",
        "quote": quote,
        "value": quote,
    }


def _quote_from_note(content: str, needle: str) -> str | None:
    text = (content or "").strip()
    if not text:
        return None
    if needle:
        match = re.search(re.escape(needle), text, flags=re.IGNORECASE)
        if match:
            start = max(0, match.start() - 40)
            end = min(len(text), match.end() + 80)
            return text[start:end].strip()
    return text[:200].strip() or None


def _entity_ref(entity: Entity | None) -> dict | None:
    if entity is None:
        return None
    return {"id": entity.id, "title": entity.title, "type": entity.type}


def _format_date_label(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return f"{parsed.day} {parsed.strftime('%b %Y')}"
    except ValueError:
        return value[:10]
