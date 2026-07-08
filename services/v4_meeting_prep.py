"""Meeting prep payloads: discuss markers, mutual commitments, ask routing."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from extensions import db
from models import Entity, EntityLink, _iso
from services.v4_markers import prep_payload_for_person
from services.v4_workboard import OPEN_TASK_STATUSES, operator_identity

PREP_QUESTION_RE = re.compile(
    r"^\s*prep(?:are)?\s+me\s+for\s+(.+?)\s*[.?!]?\s*$",
    re.IGNORECASE,
)


def parse_prep_question(question: str) -> str | None:
    """Return the target person name when `question` is a prep-me-for request."""
    match = PREP_QUESTION_RE.match((question or "").strip())
    if not match:
        return None
    name = match.group(1).strip()
    return name or None


def find_person_by_name(name: str) -> Entity | None:
    """Resolve an active person entity by title (case-insensitive)."""
    cleaned = (name or "").strip().rstrip(".?!")
    if not cleaned:
        return None
    exact = (
        Entity.query.filter(
            Entity.type == "person",
            Entity.lifecycle == "active",
            Entity.title.ilike(cleaned),
        )
        .order_by(Entity.updated_at.desc())
        .first()
    )
    if exact is not None:
        return exact
    return (
        Entity.query.filter(
            Entity.type == "person",
            Entity.lifecycle == "active",
            Entity.title.ilike(f"%{cleaned}%"),
        )
        .order_by(Entity.updated_at.desc())
        .first()
    )


def _commitment_item(task: Entity) -> dict:
    return {
        "id": task.id,
        "type": task.type,
        "title": task.title,
        "status": task.status,
        "due_at": _iso(task.due_at),
        "follow_up_at": _iso(task.follow_up_at),
    }


def _tasks_assigned_to(person_id: str) -> list[Entity]:
    return (
        Entity.query.join(
            EntityLink,
            (EntityLink.source_entity_id == Entity.id)
            & (EntityLink.relationship_type == "assigned_to"),
        )
        .filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(tuple(OPEN_TASK_STATUSES)),
            EntityLink.target_entity_id == person_id,
        )
        .order_by(Entity.follow_up_at.asc().nullslast(), Entity.due_at.asc().nullslast())
        .all()
    )


def _operator_tasks_mentioning_person(operator_id: str, person_id: str) -> list[Entity]:
    assigned = EntityLink.__table__.alias("assigned")
    mentions = EntityLink.__table__.alias("mentions")
    return (
        Entity.query.join(
            assigned,
            (assigned.c.source_entity_id == Entity.id)
            & (assigned.c.relationship_type == "assigned_to")
            & (assigned.c.target_entity_id == operator_id),
        )
        .join(
            mentions,
            (mentions.c.source_entity_id == Entity.id)
            & (mentions.c.relationship_type == "mentions")
            & (mentions.c.target_entity_id == person_id),
        )
        .filter(
            Entity.type == "task",
            Entity.lifecycle == "active",
            Entity.status.in_(tuple(OPEN_TASK_STATUSES)),
        )
        .order_by(Entity.due_at.asc().nullslast(), Entity.updated_at.desc())
        .all()
    )


def mutual_commitments_for_person(person_id: str) -> dict:
    """Open commitments between the operator and `person_id`."""
    operator_person_id, operator_configured = operator_identity()
    they_owe = [_commitment_item(task) for task in _tasks_assigned_to(person_id)]
    you_owe = []
    if operator_configured and operator_person_id:
        you_owe = [
            _commitment_item(task)
            for task in _operator_tasks_mentioning_person(operator_person_id, person_id)
        ]
    return {"they_owe": they_owe, "you_owe": you_owe}


def build_meeting_prep_payload(
    person: Entity,
    *,
    base_meeting_prep: dict | None = None,
    now: datetime | None = None,
) -> dict:
    """Assemble the full meeting-prep payload for a person."""
    now = now or datetime.now(timezone.utc)
    discuss_markers = prep_payload_for_person(person.id)
    mutual_commitments = mutual_commitments_for_person(person.id)
    payload = {
        "person": {
            "id": person.id,
            "type": person.type,
            "title": person.title,
        },
        "discuss_markers": discuss_markers,
        "mutual_commitments": mutual_commitments,
        "generated_at": _iso(now),
    }
    if base_meeting_prep is not None:
        payload.update(base_meeting_prep)
    else:
        payload.setdefault("headline", _default_headline(person.title, discuss_markers, mutual_commitments))
    return payload


def _default_headline(person_title: str, discuss_markers: list, mutual_commitments: dict) -> str:
    they_count = len(mutual_commitments.get("they_owe") or [])
    you_count = len(mutual_commitments.get("you_owe") or [])
    marker_count = len(discuss_markers)
    parts = [f"Meeting prep for {person_title}"]
    if they_count or you_count:
        parts.append(f"{you_count} you owe, {they_count} they owe")
    if marker_count:
        parts.append(
            f"{marker_count} discuss marker{'s' if marker_count != 1 else ''}"
        )
    return ": ".join(parts[:1]) + (" — " + "; ".join(parts[1:]) if len(parts) > 1 else ".")


def citations_from_prep(prep: dict) -> list[dict]:
    """Receipt-style citations for ask responses."""
    citations = []
    seen = set()
    for bucket in ("they_owe", "you_owe"):
        for item in prep.get("mutual_commitments", {}).get(bucket) or []:
            entity_id = item.get("id")
            if not entity_id or entity_id in seen:
                continue
            seen.add(entity_id)
            citations.append(
                {
                    "entity_id": entity_id,
                    "snippet": item.get("title") or "",
                    "relevance": 1.0,
                }
            )
    for marker in prep.get("discuss_markers") or []:
        entity = marker.get("entity") or {}
        entity_id = entity.get("id") or marker.get("entity_id")
        if not entity_id or entity_id in seen:
            continue
        seen.add(entity_id)
        snippet = marker.get("note") or entity.get("title") or "Discuss marker"
        citations.append(
            {
                "entity_id": entity_id,
                "snippet": snippet[:280],
                "relevance": 1.0,
            }
        )
    for note in prep.get("recent_notes") or []:
        entity_id = note.get("id")
        if not entity_id or entity_id in seen:
            continue
        seen.add(entity_id)
        citations.append(
            {
                "entity_id": entity_id,
                "snippet": (note.get("preview") or note.get("title") or "")[:280],
                "relevance": 0.9,
            }
        )
    return citations


def answer_prep_question(person_name: str) -> dict:
    """Build an ask-shaped response for 'prep me for X'."""
    person = find_person_by_name(person_name)
    if person is None:
        return {
            "answer": f"I couldn't find a person named '{person_name}' in the workspace.",
            "confidence": "low",
            "caveats": ["No matching person entity."],
            "citations": [],
            "suggested_actions": [
                {
                    "type": "capture",
                    "label": "Capture starting point",
                    "payload": {"content": f"Prep me for {person_name}"},
                }
            ],
        }

    prep = build_meeting_prep_payload(person)
    return {
        "answer": prep.get("headline") or f"Meeting prep for {person.title}.",
        "confidence": "high",
        "caveats": [],
        "citations": citations_from_prep(prep),
        "suggested_actions": [
            {
                "type": "open",
                "label": f"Open {person.title}",
                "payload": {"entity_id": person.id},
            }
        ],
        "prep": prep,
    }
