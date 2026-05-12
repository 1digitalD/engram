"""Progressive note summarization via Claude (Anthropic) with input chunking."""

from __future__ import annotations

import json
import os
import re
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

SYSTEM_PROMPT = (
    "You are a progressive summarization assistant. Given a set of notes, "
    "produce a concise summary with key themes and actionable items."
)

# Rough token estimate when the API does not return usage (should not happen in production).
_CHARS_PER_TOKEN = 4

# Max estimated tokens of note text per API call (user message body dedicated to notes).
_MAX_NOTE_TOKENS_PER_CALL = 1500

_DEFAULT_MODEL = os.environ.get(
    "ANTHROPIC_SUMMARY_MODEL", "claude-3-5-sonnet-20241022"
)

_JSON_USER_SUFFIX = (
    "Respond with a single JSON object only (no markdown fences) "
    'with keys: "summary_text" (string), "key_themes" (array of strings), '
    '"action_items" (array of strings, each item a short actionable string).'
)

RETROSPECTIVE_SYSTEM_PROMPT = (
    "You are writing a project retrospective for a personal knowledge system. "
    "Ground every point in the note excerpts you receive; do not invent work "
    "that is not supported by the notes. Each JSON field value should be "
    "well-formatted markdown (use short paragraphs and bullet lists where appropriate)."
)

_RETROSPECTIVE_JSON_SUFFIX = (
    "Respond with a single JSON object only (no markdown fences) with keys: "
    '"accomplished" (string), "key_decisions" (string), "lessons_learned" (string), '
    '"outstanding_items" (string). Each value must be markdown text for that section.'
)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _note_created_at(note: Any) -> datetime:
    return note.created_at or datetime.utcnow()


def _sort_notes_newest_first(notes: list) -> list:
    return sorted(notes, key=_note_created_at, reverse=True)


def _group_notes_by_date_sorted(notes: list) -> list[tuple[Any, list]]:
    """Group by calendar date; groups ordered newest-first; notes within group newest-first."""
    by_date: dict[Any, list] = defaultdict(list)
    for n in _sort_notes_newest_first(notes):
        d = _note_created_at(n).date()
        by_date[d].append(n)
    dates_sorted = sorted(by_date.keys(), reverse=True)
    return [(d, by_date[d]) for d in dates_sorted]


def _format_note_line(note: Any, day) -> str:
    ts = _note_created_at(note).isoformat()
    text = (getattr(note, 'raw_text', None) or getattr(note, 'content', '') or '').strip().replace("\n", " ")
    if len(text) > 2000:
        text = text[:1997] + "..."
    return f"- [{day.isoformat()} {ts}] ({note.id}): {text}"


def _build_note_chunks(notes: list) -> list[str]:
    """Split note text into chunks within _MAX_NOTE_TOKENS_PER_CALL (estimated)."""
    lines: list[str] = []
    for day, day_notes in _group_notes_by_date_sorted(notes):
        ordered = sorted(day_notes, key=_note_created_at, reverse=True)
        for note in ordered:
            lines.append(_format_note_line(note, day))

    chunks: list[str] = []
    buf: list[str] = []
    tok = 0
    for line in lines:
        lt = _estimate_tokens(line)
        if buf and tok + lt > _MAX_NOTE_TOKENS_PER_CALL:
            chunks.append("\n".join(buf))
            buf = []
            tok = 0
        buf.append(line)
        tok += lt
    if buf:
        chunks.append("\n".join(buf))
    return chunks if chunks else [""]


def _strip_json_fences(raw: str) -> str:
    s = raw.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s


def _parse_llm_json(text: str) -> dict[str, Any]:
    raw = _strip_json_fences(text)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("LLM JSON must be an object")
    return {
        "summary_text": str(data.get("summary_text", "")).strip(),
        "key_themes": list(data.get("key_themes") or []),
        "action_items": list(data.get("action_items") or []),
    }


def _parse_retrospective_json(text: str) -> dict[str, str]:
    raw = _strip_json_fences(text)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("LLM JSON must be an object")
    keys = (
        "accomplished",
        "key_decisions",
        "lessons_learned",
        "outstanding_items",
    )
    return {k: str(data.get(k, "")).strip() for k in keys}


class Summarizer:
    """
    Calls Claude with chunked note bodies (max ~1500 estimated note tokens per call).
    Groups notes by date, newest days first.
    """

    def __init__(self, client: Any | None = None, model: str | None = None):
        self._client = client
        self._model = model or _DEFAULT_MODEL

    def _anthropic_client(self):
        if self._client is not None:
            return self._client
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        import anthropic

        return anthropic.Anthropic(api_key=key)

    def _invoke(
        self,
        user_body: str,
        *,
        entity_name: str,
        granularity: str,
    ) -> tuple[dict[str, Any], int, int]:
        client = self._anthropic_client()
        user = (
            f"Context: entity={entity_name!r}, granularity={granularity}.\n\n"
            f"Notes:\n{user_body}\n\n{_JSON_USER_SUFFIX}"
        )
        msg = client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
        )
        text_parts = []
        for block in msg.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        combined = "".join(text_parts)
        parsed = _parse_llm_json(combined)
        usage = getattr(msg, "usage", None)
        if usage is not None:
            inp = int(getattr(usage, "input_tokens", 0) or 0)
            out = int(getattr(usage, "output_tokens", 0) or 0)
        else:
            inp = _estimate_tokens(SYSTEM_PROMPT + user)
            out = _estimate_tokens(combined)
        return parsed, inp, out

    def _merge_partials(
        self,
        partials: list[dict[str, Any]],
        *,
        entity_name: str,
        granularity: str,
    ) -> tuple[dict[str, Any], int, int]:
        if len(partials) == 1:
            return partials[0], 0, 0
        payload = json.dumps(partials, ensure_ascii=False)
        if _estimate_tokens(payload) > _MAX_NOTE_TOKENS_PER_CALL:
            mid = max(1, len(partials) // 2)
            left, li, lo = self._merge_partials(
                partials[:mid], entity_name=entity_name, granularity=granularity
            )
            right, ri, ro = self._merge_partials(
                partials[mid:], entity_name=entity_name, granularity=granularity
            )
            merged, mi, mo = self._merge_partials(
                [left, right], entity_name=entity_name, granularity=granularity
            )
            return merged, li + ri + mi, lo + ro + mo

        user = (
            f"Merge these partial summaries for entity={entity_name!r}, "
            f"granularity={granularity}. Combine themes and action items; dedupe.\n"
            f"Partials (JSON array):\n{payload}\n\n{_JSON_USER_SUFFIX}"
        )
        client = self._anthropic_client()
        msg = client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
        )
        text_parts = []
        for block in msg.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        combined = "".join(text_parts)
        parsed = _parse_llm_json(combined)
        usage = getattr(msg, "usage", None)
        if usage is not None:
            inp = int(getattr(usage, "input_tokens", 0) or 0)
            out = int(getattr(usage, "output_tokens", 0) or 0)
        else:
            inp = _estimate_tokens(SYSTEM_PROMPT + user)
            out = _estimate_tokens(combined)
        return parsed, inp, out

    def _invoke_retrospective_chunk(
        self,
        chunk: str,
        *,
        project_name: str,
        note_count: int,
    ) -> tuple[dict[str, str], int, int]:
        client = self._anthropic_client()
        user = (
            f"You completed the project {project_name!r}.\n"
            f"The project has {note_count} linked notes in total. "
            "The list below is one batch of those notes (excerpts with ids and timestamps); "
            "other batches may follow in separate API calls when synthesizing.\n\n"
            f"Project notes (this batch):\n{chunk}\n\n"
            "Write a concise retrospective covering:\n"
            "- What was accomplished\n"
            "- Key decisions made\n"
            "- Lessons learned\n"
            "- Outstanding items to carry forward\n\n"
            f"{_RETROSPECTIVE_JSON_SUFFIX}"
        )
        msg = client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=RETROSPECTIVE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
        )
        text_parts = []
        for block in msg.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        combined = "".join(text_parts)
        parsed = _parse_retrospective_json(combined)
        usage = getattr(msg, "usage", None)
        if usage is not None:
            inp = int(getattr(usage, "input_tokens", 0) or 0)
            out = int(getattr(usage, "output_tokens", 0) or 0)
        else:
            inp = _estimate_tokens(RETROSPECTIVE_SYSTEM_PROMPT + user)
            out = _estimate_tokens(combined)
        return parsed, inp, out

    def _merge_retrospective_partials(
        self,
        partials: list[dict[str, str]],
        *,
        project_name: str,
    ) -> tuple[dict[str, str], int, int]:
        if len(partials) == 1:
            return partials[0], 0, 0
        payload = json.dumps(partials, ensure_ascii=False)
        if _estimate_tokens(payload) > _MAX_NOTE_TOKENS_PER_CALL:
            mid = max(1, len(partials) // 2)
            left, li, lo = self._merge_retrospective_partials(
                partials[:mid], project_name=project_name
            )
            right, ri, ro = self._merge_retrospective_partials(
                partials[mid:], project_name=project_name
            )
            merged, mi, mo = self._merge_retrospective_partials(
                [left, right], project_name=project_name
            )
            return merged, li + ri + mi, lo + ro + mo

        user = (
            f"Merge these partial retrospectives for project={project_name!r}. "
            "Produce one coherent retrospective; deduplicate bullets; keep specifics "
            "that appear in more than one partial; resolve contradictions conservatively "
            "(prefer explicit dates/facts from the notes).\n"
            f"Partials (JSON array):\n{payload}\n\n{_RETROSPECTIVE_JSON_SUFFIX}"
        )
        client = self._anthropic_client()
        msg = client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=RETROSPECTIVE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
        )
        text_parts = []
        for block in msg.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        combined = "".join(text_parts)
        parsed = _parse_retrospective_json(combined)
        usage = getattr(msg, "usage", None)
        if usage is not None:
            inp = int(getattr(usage, "input_tokens", 0) or 0)
            out = int(getattr(usage, "output_tokens", 0) or 0)
        else:
            inp = _estimate_tokens(RETROSPECTIVE_SYSTEM_PROMPT + user)
            out = _estimate_tokens(combined)
        return parsed, inp, out

    def summarize_notes(self, notes: list, granularity: str, entity_name: str) -> dict:
        """
        Returns dict with:
        summary_text, key_themes, action_items, token_count, model_used
        """
        if not notes:
            return {
                "summary_text": "",
                "key_themes": [],
                "action_items": [],
                "token_count": 0,
                "model_used": self._model,
            }

        chunks = _build_note_chunks(notes)
        total_in = 0
        total_out = 0
        partials: list[dict[str, Any]] = []

        for chunk in chunks:
            if not chunk.strip():
                continue
            parsed, inp, out = self._invoke(
                chunk, entity_name=entity_name, granularity=granularity
            )
            partials.append(parsed)
            total_in += inp
            total_out += out

        if not partials:
            partials = [
                {
                    "summary_text": "",
                    "key_themes": [],
                    "action_items": [],
                }
            ]

        if len(partials) == 1:
            merged = partials[0]
        else:
            merged, mi, mo = self._merge_partials(
                partials, entity_name=entity_name, granularity=granularity
            )
            total_in += mi
            total_out += mo

        return {
            "summary_text": merged.get("summary_text", ""),
            "key_themes": merged.get("key_themes") or [],
            "action_items": merged.get("action_items") or [],
            "token_count": total_in + total_out,
            "model_used": self._model,
        }

    def summarize_project_retrospective(self, notes: list, project_name: str) -> dict[str, Any]:
        """
        Claude-backed retrospective using chunked project note excerpts.

        Returns dict keys:
        accomplished, key_decisions, lessons_learned, outstanding_items,
        token_count, model_used
        """
        if not notes:
            return {
                "accomplished": "",
                "key_decisions": "",
                "lessons_learned": "",
                "outstanding_items": "",
                "token_count": 0,
                "model_used": self._model,
            }

        chunks = _build_note_chunks(notes)
        note_count = len(notes)
        total_in = 0
        total_out = 0
        partials: list[dict[str, str]] = []

        for chunk in chunks:
            if not chunk.strip():
                continue
            parsed, inp, out = self._invoke_retrospective_chunk(
                chunk, project_name=project_name, note_count=note_count
            )
            partials.append(parsed)
            total_in += inp
            total_out += out

        if len(partials) == 1:
            merged = partials[0]
        else:
            merged, mi, mo = self._merge_retrospective_partials(
                partials, project_name=project_name
            )
            total_in += mi
            total_out += mo

        return {
            "accomplished": merged.get("accomplished", ""),
            "key_decisions": merged.get("key_decisions", ""),
            "lessons_learned": merged.get("lessons_learned", ""),
            "outstanding_items": merged.get("outstanding_items", ""),
            "token_count": total_in + total_out,
            "model_used": self._model,
        }

    def execute_scheduled_summarization(
        self, granularity: str, area_id: str | None = None
    ) -> int:
        """
        For each relevant area, load notes from the last 7 days and persist a Summary.

        When ``area_id`` is set, only that area is processed. Returns the number of
        summaries written.
        """
        from extensions import db
        from models import Entity, EntityLink, Summary, SummaryGranularity

        try:
            gran = SummaryGranularity[str(granularity.strip().upper())]
        except (KeyError, AttributeError):
            raise ValueError(f"invalid granularity: {granularity!r}") from None

        since = datetime.utcnow() - timedelta(days=7)
        created = 0

        if area_id is not None:
            area = db.session.get(Entity, area_id)
            if not area:
                raise ValueError(f"area not found: {area_id}")
            areas = [area]
        else:
            areas = Entity.query.filter_by(type="area").order_by(Entity.title).all()

        for area in areas:
            linked_note_ids = (
                db.session.query(EntityLink.src_id)
                .filter(EntityLink.dst_id == area.id, EntityLink.link_type == "area")
                .subquery()
            )
            notes = (
                Entity.query
                .filter(Entity.type == "note", Entity.created_at >= since, Entity.id.in_(linked_note_ids))
                .order_by(Entity.created_at.asc())
                .all()
            )
            if not notes:
                continue

            result = self.summarize_notes(
                notes, granularity=gran.value, entity_name=area.title
            )
            times = [n.created_at or datetime.utcnow() for n in notes]
            summary = Summary(
                note_id=notes[0].id,
                area_id=area.id,
                summary_text=result.get("summary_text") or "",
                generated_at=datetime.utcnow(),
                summary_type="scheduled",
                granularity=gran,
                date_from=min(times),
                date_to=max(times),
                key_themes=result.get("key_themes"),
                action_items=result.get("action_items"),
            )
            db.session.add(summary)
            created += 1

        db.session.commit()
        return created

    def run_async(
        self,
        granularity: str,
        area_id: str | None = None,
        *,
        app: Any | None = None,
        sync: bool = False,
    ) -> None:
        """Run ``execute_scheduled_summarization`` in-process or on a daemon thread."""
        from flask import current_app

        application = app or current_app._get_current_object()

        def task() -> None:
            with application.app_context():
                self.execute_scheduled_summarization(granularity, area_id)

        if sync:
            task()
        else:
            threading.Thread(target=task, daemon=True).start()
