"""V4 ask service: grounded Q&A over the workspace."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from copy import deepcopy

from flask import current_app

from services.v4_brief import BRIEF_MODEL
from services.v4_search import search_entities
from utils import get_openai_client

logger = logging.getLogger(__name__)

ASK_TOP_K = 5
CACHE_TTL_SECONDS = 24 * 60 * 60
HIGH_RELEVANCE = 0.7

_ASK_CACHE: dict[str, dict] = {}

IDK_ANSWER = "I don't have anything in the workspace that answers this."

SYSTEM_PROMPT = """You are a careful research assistant for a personal knowledge workspace. \
Answer the user's question using ONLY the provided workspace context. \
If the context does not contain enough information, say \"I don't have anything in the workspace that answers this.\" \
Do NOT invent facts. Cite sources inline using the exact format: 📝 'snippet' — entity_id.

Return JSON only:
{
  "answer": "your concise answer with inline citations",
  "cited_entity_ids": ["id1", "id2"]
}"""


def _clear_cache() -> None:
    """Clear the in-process ask cache. Exposed for tests."""
    _ASK_CACHE.clear()


def _context_hash(citations: list[dict]) -> str:
    payload = [(c["entity_id"], c["snippet"]) for c in citations]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _cache_key(question: str, citations: list[dict]) -> str:
    return hashlib.sha256(
        f"{question}|{_context_hash(citations)}".encode("utf-8")
    ).hexdigest()


def _get_cached(key: str) -> dict | None:
    entry = _ASK_CACHE.get(key)
    if not entry:
        return None
    if time.time() > entry["expires_at"]:
        _ASK_CACHE.pop(key, None)
        return None
    return deepcopy(entry["response"])


def _set_cached(key: str, response: dict) -> None:
    _ASK_CACHE[key] = {
        "response": deepcopy(response),
        "expires_at": time.time() + CACHE_TTL_SECONDS,
    }


def _normalize_question(question: str) -> str:
    return (question or "").strip()


def _query_terms(question: str) -> list[str]:
    return [t.lower() for t in question.split() if t.isalnum() and len(t) > 2]


def _keyword_relevance(result: dict, terms: list[str]) -> float:
    """Heuristic relevance for keyword matches based on term coverage."""
    if not terms:
        return 0.5
    entity = result.get("entity") or {}
    title = (entity.get("title") or "").lower()
    snippet = (result.get("match", {}).get("snippet") or "").lower()
    content = (entity.get("content") or "").lower()
    text = f"{title} {snippet} {content}"
    unique_terms = list(dict.fromkeys(terms))
    matched = [t for t in unique_terms if t in text]
    coverage = len(matched) / len(unique_terms)
    normalized_query = " ".join(unique_terms)
    phrase_bonus = 0.0
    if normalized_query in title:
        phrase_bonus = 0.4
    elif normalized_query in content or normalized_query in snippet:
        phrase_bonus = 0.2
    relevance = coverage * 0.6 + phrase_bonus
    return round(min(1.0, max(0.0, relevance)), 3)


def _build_citations(results: list[dict], question: str) -> list[dict]:
    """Turn search results into normalized citations with relevance scores."""
    terms = _query_terms(question)
    citations = []
    for result in results:
        match = result.get("match") or {}
        entity = result.get("entity") or {}
        entity_id = entity.get("id")
        snippet = match.get("snippet") or entity.get("title") or ""
        source = match.get("source")
        semantic_score = match.get("semantic_score")

        if semantic_score is not None and source in ("semantic", "hybrid"):
            relevance = round(min(1.0, max(0.0, float(semantic_score))), 3)
        else:
            relevance = _keyword_relevance(result, terms)

        if not snippet or not entity_id:
            continue
        citations.append(
            {
                "entity_id": entity_id,
                "snippet": snippet[:280],
                "relevance": relevance,
            }
        )

    citations.sort(key=lambda c: c["relevance"], reverse=True)
    return citations


def _compute_confidence(citations: list[dict]) -> str:
    if not citations:
        return "low"
    high_count = sum(1 for c in citations if c["relevance"] >= HIGH_RELEVANCE)
    if high_count >= 2:
        return "high"
    return "medium"


def _inline_citation(citation: dict) -> str:
    snippet = citation["snippet"].replace("'", "\\'")
    return f"📝 '{snippet}' — {citation['entity_id']}"


def _suggested_actions(
    citations: list[dict], *, idk: bool = False, question: str = ""
) -> list[dict]:
    if idk:
        return [
            {
                "type": "capture",
                "label": "Capture starting point",
                "payload": {"content": question},
            }
        ]

    actions = []
    seen = set()
    for citation in citations[:3]:
        entity_id = citation["entity_id"]
        if entity_id in seen:
            continue
        seen.add(entity_id)
        actions.append(
            {
                "type": "open",
                "label": "Open source",
                "payload": {"entity_id": entity_id},
            }
        )
    return actions


def _fallback_answer(question: str, citations: list[dict]) -> str:
    lines = [f"Based on what I found in the workspace for “{question}”:"]
    for citation in citations:
        lines.append(f"- {_inline_citation(citation)}")
    return "\n".join(lines)


def _idk_response(question: str, citations: list[dict]) -> dict:
    caveats = []
    if not citations:
        caveats.append("No matching entities were found in the workspace.")
    else:
        caveats.append(
            "The matching sources are not strong enough to ground a reliable answer."
        )
        caveats.append(
            f"Only {len(citations)} source(s) matched, and none reached the high-relevance threshold."
        )

    return {
        "answer": IDK_ANSWER,
        "citations": [],
        "confidence": "low",
        "caveats": caveats,
        "suggested_actions": _suggested_actions([], idk=True, question=question),
    }


def _generate_answer(question: str, citations: list[dict]) -> str | None:
    """Generate a grounded answer with the configured BRIEF_MODEL.

    Returns None when generation is unavailable so the caller can fall back.
    """
    try:
        if current_app.config.get("TESTING") and os.getenv("ENGRAM_ALLOW_TEST_AI") != "1":
            return None
    except RuntimeError:
        # Outside of an app context; treat as unavailable.
        return None

    if not os.getenv("OPENAI_API_KEY"):
        return None

    context = "\n\n".join(
        f"[{i + 1}] entity_id: {c['entity_id']}\nsnippet: {c['snippet']}"
        for i, c in enumerate(citations)
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Question: {question}\n\nContext:\n{context}",
        },
    ]

    try:
        response = get_openai_client().chat.completions.create(
            model=BRIEF_MODEL,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=messages,
        )
        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)
    except Exception as exc:
        logger.error("ask answer generation failed: %s", exc)
        return None

    answer = (parsed.get("answer") or "").strip()
    if not answer:
        return None

    allowed_ids = {c["entity_id"] for c in citations}
    cited_ids = [
        eid for eid in (parsed.get("cited_entity_ids") or []) if eid in allowed_ids
    ]

    # Ensure citations appear inline if the model omitted them.
    if "📝" not in answer and cited_ids:
        cited_citations = [c for c in citations if c["entity_id"] in cited_ids]
        answer = answer + "\n\n" + "\n".join(
            _inline_citation(c) for c in cited_citations
        )

    return answer


def ask_question(question: str, top_k: int = ASK_TOP_K) -> dict:
    """Answer a question using hybrid retrieval over the workspace.

    Returns a dict with answer, citations, confidence, caveats, and suggested_actions.
    """
    question = _normalize_question(question)
    if not question:
        raise ValueError("question is required")

    results = search_entities(question, mode="hybrid", limit=top_k)
    citations = _build_citations(results, question)

    cache_key = _cache_key(question, citations)
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    confidence = _compute_confidence(citations)
    if confidence == "low":
        response = _idk_response(question, citations)
    else:
        answer = _generate_answer(question, citations) or _fallback_answer(
            question, citations
        )
        response = {
            "answer": answer,
            "citations": citations,
            "confidence": confidence,
            "caveats": [],
            "suggested_actions": _suggested_actions(citations, question=question),
        }

    _set_cached(cache_key, response)
    return response
