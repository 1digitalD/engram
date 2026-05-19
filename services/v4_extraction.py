"""v4 capture extraction boundary.

The extractor returns candidates only. Reconciliation decides which candidates
are safe to apply and which must become reviewable suggestions.
"""
from __future__ import annotations

import json
import os

from utils import get_openai_client

EXTRACTION_MODEL = os.getenv("OPENAI_EXTRACTION_MODEL", "gpt-4o-mini")
ALLOWED_ENTITY_TYPES = {"task", "project", "area", "person", "resource"}
ALLOWED_RELATIONSHIP_TYPES = {"parent", "related", "derived_from", "mentions", "assigned_to", "references", "blocks"}

SYSTEM_PROMPT = """You extract structured candidates from a personal workspace note.
Return JSON only. Do not rewrite or classify the source note as another entity.
Only return candidates for possible metadata, links, or reviewable entity creation.
Risky changes must remain candidates for review, never instructions to mutate data.
Schema:
{
  "summary": "short optional summary",
  "confidence": 0.0,
  "tags": [{"name": "tag", "confidence": 0.0}],
  "links": [{
    "target_type": "project|area|person|resource|task",
    "title": "existing or possible entity title",
    "relationship_type": "parent|related|derived_from|mentions|assigned_to|references|blocks",
    "confidence": 0.0,
    "evidence": "short quote or rationale"
  }],
  "entities": [{
    "type": "task|project|area|person|resource",
    "title": "candidate title",
    "content": "optional detail",
    "confidence": 0.0,
    "evidence": "short quote or rationale"
  }]
}
"""


def extract_capture_candidates(content, mode="auto"):
    """Return extraction candidates for a captured note.

    The function deliberately returns candidates only. Capture reconciliation
    decides what is safe to apply and what must become a review suggestion.
    """
    if mode == "off" or not content or not content.strip():
        return {}

    try:
        from flask import current_app
        if current_app.config.get("TESTING") and os.getenv("ENGRAM_ALLOW_TEST_AI") != "1":
            return {}
    except RuntimeError:
        pass

    if not os.getenv("OPENAI_API_KEY"):
        return {}

    response = get_openai_client().chat.completions.create(
        model=os.getenv("OPENAI_EXTRACTION_MODEL", EXTRACTION_MODEL),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content[:12000]},
        ],
    )
    raw = response.choices[0].message.content or "{}"
    return _normalize_payload(json.loads(raw))


def _normalize_payload(payload):
    if not isinstance(payload, dict):
        return {}

    return {
        "summary": _text(payload.get("summary")),
        "confidence": _confidence(payload.get("confidence")),
        "tags": _normalize_items(payload.get("tags"), _normalize_tag),
        "links": _normalize_items(payload.get("links"), _normalize_link),
        "entities": _normalize_items(payload.get("entities"), _normalize_entity),
    }


def _normalize_items(value, normalizer):
    items = []
    for item in _list(value):
        normalized = normalizer(item)
        if normalized:
            items.append(normalized)
    return items


def _normalize_tag(item):
    if isinstance(item, str):
        name = item
        confidence = 0.6
    elif isinstance(item, dict):
        name = item.get("name") or item.get("title")
        confidence = item.get("confidence")
    else:
        return None
    name = _text(name)
    if not name:
        return None
    return {"name": name[:80], "confidence": _confidence(confidence)}


def _normalize_link(item):
    if not isinstance(item, dict):
        return None
    target_type = _text(item.get("target_type") or item.get("type"))
    title = _text(item.get("title") or item.get("name"))
    if target_type not in ALLOWED_ENTITY_TYPES or not title:
        return None
    relationship_type = _text(item.get("relationship_type")) or "related"
    if relationship_type not in ALLOWED_RELATIONSHIP_TYPES:
        relationship_type = "related"
    return {
        "target_type": target_type,
        "title": title[:160],
        "relationship_type": relationship_type,
        "confidence": _confidence(item.get("confidence")),
        "evidence": _text(item.get("evidence") or item.get("reason")),
    }


def _normalize_entity(item):
    if not isinstance(item, dict):
        return None
    entity_type = _text(item.get("type"))
    title = _text(item.get("title") or item.get("name"))
    if entity_type not in ALLOWED_ENTITY_TYPES or not title:
        return None
    return {
        "type": entity_type,
        "title": title[:160],
        "content": _text(item.get("content") or item.get("description")),
        "confidence": _confidence(item.get("confidence")),
        "evidence": _text(item.get("evidence") or item.get("reason")),
    }


def _list(value):
    return value if isinstance(value, list) else []


def _text(value):
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _confidence(value):
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(confidence, 1.0))
