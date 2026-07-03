"""Decision extraction for explicit commitments.

Decisions are first-class records of explicit commitments. They are NEVER
auto-created from capture — every extraction produces a reviewable suggestion.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timezone

from services.llm_models import resolve_chat_model
from utils import get_openai_client

logger = logging.getLogger(__name__)

DECISION_EXTRACTION_MODEL = resolve_chat_model("OPENAI_DECISION_MODEL")

SYSTEM_PROMPT = """You are a conservative extraction engine for explicit decisions and commitments.

Your ONLY job is to identify explicit, unambiguous commitments in the note.
Extract a decision ONLY when ALL of the following are true:
1. The text states a definite commitment (not a wish, idea, or possibility).
2. A specific person or named agent is attributed with the commitment.
3. A specific date, deadline, or concrete deliverable is named.

REJECT tentative or speculative language such as: maybe, possibly, perhaps,
might, could, consider, think about, look into, we should, I should, let's,
want to, hope to, plan to, exploring, investigating, discussing.

Examples of EXPLICIT commitments to extract:
- "Dan committed to ship the report by Friday."
- "The agent decided to use Python for the new stack."
- "Mary will deliver the wireframes by 2026-07-15."

Examples to REJECT:
- "We should maybe ship by Friday." (tentative)
- "I think Python is the right choice." (opinion, not commitment)
- "Let's consider wireframes next week." (speculative)

For each extracted decision, return:
- statement: the exact commitment statement, concise (≤200 chars)
- context: the surrounding sentence or clause that justifies the extraction
- decided_at: ISO 8601 datetime if a date is mentioned, otherwise null
- decided_by: "user" if a human (the note author or named person) made the commitment, or "agent:<name>" if an AI agent did

Return JSON only. No prose, no markdown fences.

Schema:
{
  "decisions": [
    {
      "statement": "concise commitment statement",
      "context": "surrounding text / justification",
      "decided_at": "YYYY-MM-DDTHH:MM:SSZ" or null,
      "decided_by": "user" or "agent:<name>"
    }
  ]
}

If no explicit commitments are found, return {"decisions": []}."""


# Tentative markers used for a fast pre-filter. The LLM prompt is the primary
# guardrail; this regex is defense-in-depth to avoid emitting suggestions for
# obviously hedged sentences.
TENTATIVE_MARKERS = re.compile(
    r"\b(maybe|possibly|perhaps|might|could|consider|thinking about|looking into|"
    r"we should|i should|let's|want to|hope to|plan to|exploring|investigating|"
    r"discussing|tentative|not sure|uncertain|if possible|would like)\b",
    re.IGNORECASE,
)


# ── Structural guardrail (SQ-04) ─────────────────────────────────────────
# The prompt requires a named actor and a concrete date/deliverable, but the
# model sometimes ignores that (e.g. "We can close this task now." was
# extracted as a decision). This is a post-hoc, regex-based structural check
# applied in _normalize_decisions as a belt-and-braces guard: it rejects
# candidates that read like routine status/closure chatter rather than an
# attributed commitment.
CLOSURE_LANGUAGE_PATTERN = re.compile(
    r"\b(clos(?:e|ed|ing)|done|finish(?:ed|ing)?|wrap\w*(?:\s+\w+){0,2}\s+up|"
    r"mark(?:ed)?\s+as\s+done)\b",
    re.IGNORECASE,
)

DATE_OR_DELIVERABLE_SIGNAL_PATTERN = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"today|tomorrow|tonight|eod|eow|end of day|end of week|next week|this week)\b",
    re.IGNORECASE,
)

# Words that commonly start a sentence regardless of who the actor is (generic
# pronouns/articles). A capitalized word in this position is not, by itself,
# evidence of a named actor. Capitalized words elsewhere in the statement (or
# a non-generic capitalized first word, e.g. an actual name) do count.
_SENTENCE_INITIAL_STOPWORDS = {
    "we", "the", "this", "that", "these", "those", "it", "i", "let", "lets",
    "he", "she", "they", "there", "here", "if", "when", "while", "after",
    "before", "once", "so", "then", "a", "an", "you", "your", "our", "us",
    "should", "will", "can", "may", "might", "could", "would", "and", "but",
}


def _has_named_actor_signal(statement):
    """True if the statement names a specific person/agent (or "I ...")."""
    if not statement:
        return False
    if re.search(r"\bI\b", statement):
        return True
    for index, word in enumerate(statement.split()):
        clean = re.sub(r"[^A-Za-z]", "", word)
        if not clean or not clean[0].isupper():
            continue
        if index == 0 and clean.lower() in _SENTENCE_INITIAL_STOPWORDS:
            continue
        return True
    return False


def _has_date_or_deliverable_signal(statement, context, decided_at):
    if decided_at:
        return True
    haystack = " ".join(part for part in (statement, context) if part)
    return bool(DATE_OR_DELIVERABLE_SIGNAL_PATTERN.search(haystack))


def _passes_structural_guardrail(statement, context, decided_at):
    has_actor = _has_named_actor_signal(statement)
    has_date_or_deliverable = _has_date_or_deliverable_signal(statement, context, decided_at)

    # Closure/routine-progress language with no attribution and no concrete
    # date/deliverable reads as status chatter, not a decision.
    if CLOSURE_LANGUAGE_PATTERN.search(statement) and not has_actor and not has_date_or_deliverable:
        return False

    # Otherwise still require at least one structural signal: a named actor
    # (or "I ..." attribution), or a concrete date/deliverable.
    if not has_actor and not has_date_or_deliverable:
        return False

    return True


def extract_decisions_from_note(content, today_iso=None):
    """Return decision candidates for a note.

    Returns a list of dicts with keys: statement, context, decided_at,
    decided_by. This function only emits candidates; capture reconciliation
    turns them into reviewable suggestions.
    """
    if not content or not content.strip():
        return []

    try:
        from flask import current_app
        if current_app.config.get("TESTING") and os.getenv("ENGRAM_ALLOW_TEST_AI") != "1":
            return []
    except RuntimeError:
        pass

    if not os.getenv("OPENAI_API_KEY"):
        return []

    today = today_iso or date.today().isoformat()
    user_prompt = f"Today is {today}.\n\nNote:\n{content[:6000]}"

    try:
        response = get_openai_client().chat.completions.create(
            model=DECISION_EXTRACTION_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)
    except Exception as exc:
        logger.warning("decision extraction failed: %s", exc)
        return []

    return _normalize_decisions(parsed.get("decisions") or [])


def _normalize_decisions(items):
    decisions = []
    for item in _list(items):
        if not isinstance(item, dict):
            continue
        statement = _clean_text(item.get("statement"))
        if not statement:
            continue
        # Defense-in-depth: reject candidates whose statement contains
        # tentative markers. This helps keep false positives low even if the
        # model is over-eager.
        if TENTATIVE_MARKERS.search(statement):
            continue
        context = _clean_text(item.get("context"))
        decided_by = _clean_text(item.get("decided_by")) or "user"
        if not _valid_decided_by(decided_by):
            decided_by = "user"
        decided_at = _parse_datetime(item.get("decided_at"))
        if not _passes_structural_guardrail(statement, context, decided_at):
            continue
        decisions.append({
            "statement": statement[:500],
            "context": context,
            "decided_at": decided_at,
            "decided_by": decided_by,
        })
    return decisions


def _valid_decided_by(value):
    if value == "user":
        return True
    if isinstance(value, str) and value.startswith("agent:") and len(value) > 6:
        return True
    return False


def _parse_datetime(value):
    if not value:
        return None
    s = str(value).strip()
    if s.lower() in {"null", "none", "n/a"}:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        pass
    # Try date-only
    try:
        dt = datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        return None


def _list(value):
    return value if isinstance(value, list) else []


def _clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None
