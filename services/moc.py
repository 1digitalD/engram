"""AI-generated Maps of Content (MOC) from a set of source entities.

v2 rewrite: uses Entity, EntityLink, create_entity, create_link.
Replaces Note references with Entity queries. Replaces raw_text with content.
"""

from __future__ import annotations

import json
import os
from typing import Any

from extensions import db
from models import Entity, EntityLink
from services.link_service import create_link
from services.summarizer import _DEFAULT_MODEL, _estimate_tokens, _strip_json_fences

MOC_SYSTEM_PROMPT = (
    "You are building a Map of Content (MOC) for a personal knowledge base. "
    "Group related source notes into clear themes. Ground everything in the "
    "note excerpts; do not invent notes or IDs. "
    "Every section body must link to the relevant source notes using markdown "
    'links exactly like `[short label](/notes/<entity_uuid>)` where `<entity_uuid>` '
    "is one of the provided entity ids."
)

_MOC_JSON_SUFFIX = (
    "Respond with a single JSON object only (no markdown fences) with keys: "
    '"title" (short plain-text title for the MOC, no # prefix), '
    '"overview" (markdown paragraph introducing the map), '
    '"sections" (array of objects, each with "heading" (string) and "body" '
    "(markdown). Use ##-level themes inside body only as nested bullets if "
    'needed; top-level themes go in "heading".)'
)


def _entity_title_line(entity: Entity) -> str:
    text = (entity.content or "").strip()
    line = text.split("\n", 1)[0].strip()
    return line[:200] if line else "(untitled)"


def _entity_excerpt(entity: Entity, max_chars: int = 600) -> str:
    text = (entity.content or "").strip()
    if len(text) > max_chars:
        return text[: max_chars - 3] + "..."
    return text


def _build_entities_prompt(entities: list[Entity]) -> str:
    lines: list[str] = []
    for e in entities:
        lines.append(
            f"- id: {e.id}\n"
            f"  title_line: {_entity_title_line(e)!r}\n"
            f"  excerpt: {_entity_excerpt(e)!r}"
        )
    return "\n".join(lines)


def _parse_moc_json(text: str) -> dict[str, Any]:
    raw = _strip_json_fences(text)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("LLM JSON must be an object")
    title = str(data.get("title", "")).strip() or "Map of content"
    overview = str(data.get("overview", "")).strip() or "_Overview pending._"
    sections_raw = data.get("sections") or []
    sections: list[dict[str, str]] = []
    if isinstance(sections_raw, list):
        for item in sections_raw:
            if not isinstance(item, dict):
                continue
            h = str(item.get("heading", "")).strip()
            b = str(item.get("body", "")).strip()
            if h or b:
                sections.append({"heading": h or "Notes", "body": b or "_—_"})
    if not sections:
        sections.append({"heading": "Sources", "body": "_No sections returned._"})
    return {"title": title, "overview": overview, "sections": sections}


def _assemble_moc_body(title: str, overview: str, sections: list[dict[str, str]]) -> str:
    parts = [f"# {title}", "", overview.strip(), ""]
    for sec in sections:
        h = sec["heading"].strip()
        b = sec["body"].strip()
        parts.append(f"## {h}")
        parts.append("")
        parts.append(b)
        parts.append("")
    parts.append("#moc")
    return "\n".join(parts).strip() + "\n"


def _infer_bucket_area(entities: list[Entity]) -> tuple[str, str | None]:
    bucket = (entities[0].properties or {}).get("bucket", "INBOX")
    area_ids = {(e.properties or {}).get("area_id") for e in entities}
    area_ids.discard(None)
    area_id = list(area_ids)[0] if len(area_ids) == 1 else None
    return bucket, area_id


def generate_map_of_content(entity_ids: list[str]) -> Entity:
    """
    Call Claude to structure a MOC, persist a new ``Entity`` (type='note'),
    and add ``child_of`` links from the MOC to each source entity (MOC → source).
    """
    if not entity_ids:
        raise ValueError("entity_ids must be non-empty")

    seen: set[str] = set()
    ordered: list[str] = []
    for raw in entity_ids:
        sid = str(raw).strip()
        if sid and sid not in seen:
            seen.add(sid)
            ordered.append(sid)

    entities: list[Entity] = []
    for eid in ordered:
        e = db.session.get(Entity, eid)
        if not e:
            raise ValueError(f"entity not found: {eid}")
        entities.append(e)

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    import anthropic

    client = anthropic.Anthropic(api_key=key)
    model = os.environ.get("ANTHROPIC_SUMMARY_MODEL", _DEFAULT_MODEL)

    user = (
        "Create a Map of Content for these source notes:\n\n"
        f"{_build_entities_prompt(entities)}\n\n{_MOC_JSON_SUFFIX}"
    )

    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        system=MOC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
    )
    text_parts: list[str] = []
    for block in msg.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)
    combined = "".join(text_parts)
    parsed = _parse_moc_json(combined)

    bucket, area_id = _infer_bucket_area(entities)
    body = _assemble_moc_body(parsed["title"], parsed["overview"], parsed["sections"])

    moc = Entity(
        type="note",
        title=parsed["title"],
        content=body,
        properties={"bucket": bucket, "area_id": area_id} if area_id else {"bucket": bucket},
        source="moc",
        lifecycle="active",
        ai_meta={
            "moc_source_note_ids": ordered,
            "model_used": model,
            "token_estimate": _estimate_tokens(MOC_SYSTEM_PROMPT + user + combined),
        },
        ai_status="pending",
    )
    db.session.add(moc)
    db.session.flush()

    for src_id in ordered:
        existing = EntityLink.query.filter_by(
            src_id=moc.id,
            dst_id=src_id,
            link_type="child_of",
        ).first()
        if not existing:
            create_link(
                src_id=moc.id,
                dst_id=src_id,
                link_type="child_of",
                source="llm",
                actor="system",
            )

    return moc
