"""Progressive note summarization via Claude (Anthropic) with input chunking."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime
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
    text = (note.raw_text or "").strip().replace("\n", " ")
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
