"""AI-generated Maps of Content (MOC) from a set of source notes."""

from __future__ import annotations

import json
import os
from typing import Any

from extensions import db
from models import BucketType, Link, Note, NoteType
from services.summarizer import _DEFAULT_MODEL, _estimate_tokens, _strip_json_fences

MOC_SYSTEM_PROMPT = (
    "You are building a Map of Content (MOC) for a personal knowledge base. "
    "Group related source notes into clear themes. Ground everything in the "
    "note excerpts; do not invent notes or IDs. "
    "Every section body must link to the relevant source notes using markdown "
    'links exactly like `[short label](/notes/<note_uuid>)` where `<note_uuid>` '
    "is one of the provided note ids."
)

_MOC_JSON_SUFFIX = (
    "Respond with a single JSON object only (no markdown fences) with keys: "
    '"title" (short plain-text title for the MOC, no # prefix), '
    '"overview" (markdown paragraph introducing the map), '
    '"sections" (array of objects, each with "heading" (string) and "body" '
    "(markdown). Use ##-level themes inside body only as nested bullets if "
    'needed; top-level themes go in "heading".)'
)


def _note_title_line(note: Note) -> str:
    text = (note.raw_text or "").strip()
    line = text.split("\n", 1)[0].strip()
    return line[:200] if line else "(untitled)"


def _note_excerpt(note: Note, max_chars: int = 600) -> str:
    text = (note.raw_text or "").strip()
    if len(text) > max_chars:
        return text[: max_chars - 3] + "..."
    return text


def _build_notes_prompt(notes: list[Note]) -> str:
    lines: list[str] = []
    for n in notes:
        lines.append(
            f"- id: {n.id}\n"
            f"  title_line: {_note_title_line(n)!r}\n"
            f"  excerpt: {_note_excerpt(n)!r}"
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


def _maybe_queue_embedding(note_id: str, raw_text: str) -> None:
    try:
        from flask import has_request_context

        if has_request_context():
            from api.notes import _queue_embedding

            _queue_embedding(note_id, raw_text)
    except Exception:
        pass


def _infer_bucket_area(notes: list[Note]) -> tuple[BucketType, str | None]:
    bucket = notes[0].bucket or BucketType.INBOX
    area_ids = {n.area_id for n in notes}
    area_id = notes[0].area_id if len(area_ids) == 1 else None
    return bucket, area_id


def generate_map_of_content(note_ids: list[str]) -> Note:
    """
    Call Claude to structure a MOC, persist a new ``Note`` with ``note_type=MOC``,
    and add ``child_of`` links from the MOC to each source note (MOC → source).
    """
    if not note_ids:
        raise ValueError("note_ids must be non-empty")

    seen: set[str] = set()
    ordered: list[str] = []
    for raw in note_ids:
        sid = str(raw).strip()
        if sid and sid not in seen:
            seen.add(sid)
            ordered.append(sid)

    notes: list[Note] = []
    for nid in ordered:
        n = db.session.get(Note, nid)
        if not n:
            raise ValueError(f"note not found: {nid}")
        notes.append(n)

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    import anthropic

    client = anthropic.Anthropic(api_key=key)
    model = os.environ.get("ANTHROPIC_SUMMARY_MODEL", _DEFAULT_MODEL)

    user = (
        "Create a Map of Content for these source notes:\n\n"
        f"{_build_notes_prompt(notes)}\n\n{_MOC_JSON_SUFFIX}"
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

    bucket, area_id = _infer_bucket_area(notes)
    body = _assemble_moc_body(parsed["title"], parsed["overview"], parsed["sections"])

    moc = Note(
        raw_text=body,
        bucket=bucket,
        note_type=NoteType.MOC,
        area_id=area_id,
        ai_meta={
            "moc_source_note_ids": ordered,
            "model_used": model,
            "token_estimate": _estimate_tokens(MOC_SYSTEM_PROMPT + user + combined),
        },
    )
    db.session.add(moc)
    db.session.flush()

    for src in ordered:
        exists = Link.query.filter_by(
            src_id=moc.id,
            dst_id=src,
            link_type="child_of",
        ).first()
        if not exists:
            db.session.add(
                Link(
                    src_id=moc.id,
                    dst_id=src,
                    link_type="child_of",
                    weight=1.0,
                    source="llm",
                )
            )

    db.session.commit()
    _maybe_queue_embedding(moc.id, moc.raw_text)
    return moc
