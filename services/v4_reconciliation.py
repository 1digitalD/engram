"""Semantic deduplication and reconciliation for extracted entity candidates.

Pipeline:
  1. Batch-embed all candidate titles in a single API call.
  2. Load each entity type's chunk set once; score all candidates of that type.
  3. Pass all candidates + their matches to an LLM in one batched call.
  4. Return a decision per candidate: new / update / link.
"""
from __future__ import annotations

import json
import logging
import math
import os
from datetime import date

from utils import get_openai_client
from services.llm_models import resolve_chat_model

logger = logging.getLogger(__name__)

RECONCILIATION_MODEL = resolve_chat_model("OPENAI_RECONCILIATION_MODEL")
SIMILARITY_THRESHOLD = 0.60
TOP_K = 3
CATALOG_CHAR_CAP = 8000  # ≈ 2000 tokens; projects/areas only

SYSTEM_PROMPT = """\
You are a deduplication and reconciliation engine for a personal knowledge workspace.
Today's date: {today}

{catalog_block}

You receive a JSON array of extracted entity candidates from a note. Each candidate \
includes the top existing entities that might be the same real-world thing, ranked by \
semantic similarity (0–1).

For each candidate decide the correct action:

  "new"             — No good existing match. A new entity should be created.
  "update"          — A clear match exists. Update the existing entity with new information.
  "link"            — A clear match exists but no fields need changing. Just link to it.
  "progress_update" — The candidate is a status/progress remark about an existing
                       entity (e.g. a standup line like "shipped the HITL piece" or
                       "still waiting on infra"), not new information that changes
                       the entity's fields, and not a new entity. Use this instead
                       of "update" or "new" when the note is just reporting on the
                       state of something that already exists in the catalog.

MATCHING RULES:
- Score < 0.65 → very unlikely match; prefer "new" UNLESS the WORKSPACE CATALOG above
  contains an entry with the same or very similar title — then prefer "link" or "update".
- Same person = same name (minor spelling differences OK).
- Same task = same action item, possibly rephrased; same actor + same action = match.
- Same project / area = same initiative or domain; paraphrases count as matches
  (e.g. "Deals agent family support" = "GTM agent family support").
- Same resource = same document, tool, URL, or artifact.
- Always check the WORKSPACE CATALOG before deciding "new" for a project or area.
- Creating a duplicate is a WORSE error than linking imperfectly. When an existing match
  OF THE SAME TYPE is plausible (similarity ≥ 0.7, or — for projects and areas — a catalog
  title covering the same initiative), prefer "update", "link", or "progress_update" over "new".
- A candidate of type "project" that is really a deliverable, milestone, or sub-goal of an
  existing project (a deck, doc, one-pager, plan, review, meeting) is NOT a new
  project — match it to the existing project ("update"/"link"/"progress_update").
- The previous two rules do NOT demote "task" candidates: a task describing a new action
  is "new" even when it obviously belongs to an existing project (the system attaches it
  to the project separately). Only choose "link"/"update" for a task when an existing TASK
  in its match list is the same action item.

FOR "update" — include:
  "target_id"         : id of the matching entity
  "fields"            : object with any subset of:
                          "status"       — only if the note explicitly changes it
                                           (e.g. "done", "blocked", "on_hold")
                          "due_at"       — ISO 8601 date if a deadline is stated or implied
                          "follow_up_at" — ISO 8601 date if a follow-up date is stated
                        Resolve relative dates ("next week", "Thursday") using today's date.
  "relationship_type" : how the source note relates to this entity (same vocab as below)

FOR "link" — include:
  "target_id"         : id of the matching entity
  "relationship_type" : parent | related | derived_from | mentions | assigned_to |
                        references | blocks

FOR "new" — include:
  "relationship_type" : how the source note relates to the entity to be created

FOR "progress_update" — include:
  "target_id"  : id of the existing entity this update is about
  "update_text": a concise (one sentence) summary of the status/progress, \
                  written from the entity's point of view (e.g. "Shipped the \
                  HITL piece", "Still waiting on infra")
  "fields"     : optional object with any subset of:
                    "status"   — if the update text clearly implies a status \
                                  transition for the target (e.g. "shipped" \
                                  / "delivered" / "done" → "done", "still \
                                  waiting on X" → "waiting", "blocked on X" \
                                  → "blocked"). Use the target entity type's \
                                  status vocabulary.
                    "priority" — one of "low" | "medium" | "high" | "urgent" \
                                  ONLY if the update text expresses urgency \
                                  escalation language about the target \
                                  (e.g. "this is now urgent", "becoming \
                                  critical", "needs to jump the queue", \
                                  "top priority now", "escalating this"). \
                                  Do not infer priority from routine status \
                                  updates — only from explicit escalation \
                                  language.
                  Omit "fields" entirely if neither is implied; omit \
                  individual keys that don't apply.
  "blocked_by_id" : if "fields.status" is "blocked" or "waiting" AND the \
                  update text names a specific blocking thing or person that \
                  matches an entity in the WORKSPACE CATALOG or this note's \
                  other candidates (e.g. "blocked on the API contract doc", \
                  "waiting on Akash"), the id of that blocking entity. \
                  Omit if no specific blocker entity can be identified.

Return a JSON object with a "decisions" array — one entry per candidate, \
in the same order as the input:

{{
  "decisions": [
    {{
      "action": "new" | "update" | "link" | "progress_update",
      "target_id": null,
      "fields": {{}},
      "update_text": null,
      "blocked_by_id": null,
      "relationship_type": "related",
      "confidence": 0.0,
      "reason": "brief explanation"
    }}
  ]
}}
"""


def reconcile_candidates(candidates):
    """Return one decision dict per candidate (same order as input).

    Each candidate must have at least: type, title, confidence.
    Missing decisions (e.g. on model error) default to action="new".
    """
    if not candidates:
        return []

    enriched = _enrich_candidates(candidates)
    decisions = _call_model(enriched)

    # Pad / fill defaults so caller always gets len(candidates) decisions
    default = {"action": "new", "target_id": None, "fields": {}, "relationship_type": None, "confidence": 0.0, "reason": ""}
    while len(decisions) < len(candidates):
        decisions.append(dict(default))
    decisions = decisions[:len(candidates)]

    # Attach the strongest similarity match to each decision so the apply
    # layer can refuse to auto-create when a plausible near-duplicate exists,
    # even if the model voted "new" with high confidence.
    for item, decision in zip(enriched, decisions):
        if not isinstance(decision, dict):
            continue
        matches = item.get("matches") or []
        top = matches[0] if matches else None
        decision["top_match_score"] = top["score"] if top else 0.0
        decision["top_match_id"] = top["id"] if top else None
        decision["top_match_title"] = top["title"] if top else None

    return decisions


# ── Batch enrichment ──────────────────────────────────────────────────────────

def _build_match_document(candidate):
    """Compose a rich match document from a candidate for embedding.

    Combines entity type + title + content + evidence so the query vector
    captures paraphrase and context, not just the title token.
    """
    parts = []
    entity_type = (candidate.get("type") or "").strip()
    if entity_type:
        parts.append(entity_type)
    title = (candidate.get("title") or "").strip()
    if title:
        parts.append(title)
    content = (candidate.get("content") or "").strip()
    if content:
        parts.append(content)
    evidence = (candidate.get("evidence") or "").strip()
    if evidence:
        parts.append(evidence)
    return " ".join(parts)


def _enrich_candidates(candidates):
    """Return enriched list [{candidate, matches}] using batched embeddings.

    Single _embed_texts call for all N candidates using composed match docs.
    Chunk set for each entity type loaded once and reused across candidates.
    """
    # --- Step 1: exact matches (no embedding needed) ---
    exact_by_index = {}
    for i, c in enumerate(candidates):
        title = c.get("title", "")
        entity_type = c.get("type", "")
        if title and entity_type:
            exact_by_index[i] = _exact_match(title, entity_type)

    # --- Step 2: batch embed composed match documents in one API call ---
    match_docs = [_build_match_document(c) for c in candidates]
    vectors = _embed_texts(match_docs) if any(match_docs) else []

    # --- Step 3: load chunk sets once per entity type ---
    types_needed = {c.get("type", "") for c in candidates if c.get("type")}
    chunks_by_type = {
        entity_type: _load_chunks_for_type(entity_type)
        for entity_type in types_needed
    }

    # --- Step 4: score each candidate against its type's chunk set ---
    enriched = []
    for i, candidate in enumerate(candidates):
        title = candidate.get("title", "")
        entity_type = candidate.get("type", "")
        exact = exact_by_index.get(i, [])

        if not title or not entity_type or i >= len(vectors) or not vectors[i]:
            enriched.append({"candidate": candidate, "matches": exact})
            continue

        vector = vectors[i]
        best = {m["id"]: m for m in exact}  # seed with exact match

        for chunk_entity_id, chunk_text, chunk_embedding, entity_data in chunks_by_type.get(entity_type, []):
            if not chunk_embedding:
                continue
            score = _cosine(vector, chunk_embedding)
            if score < SIMILARITY_THRESHOLD:
                continue
            current = best.get(chunk_entity_id)
            if current is None or score > current["score"]:
                best[chunk_entity_id] = {**entity_data, "score": score}

        ranked = sorted(best.values(), key=lambda x: x["score"], reverse=True)
        enriched.append({"candidate": candidate, "matches": ranked[:TOP_K]})

    return enriched


def _load_chunks_for_type(entity_type):
    """Load all chunks for active entities of entity_type.

    Returns list of (entity_id, chunk_text, embedding, entity_data_dict).
    Called once per type per reconcile_candidates invocation.
    """
    from models import Entity, EntityChunk

    entity_ids = {
        e.id: e
        for e in Entity.query.filter(
            Entity.type == entity_type,
            Entity.lifecycle != "deleted",
        ).all()
    }
    if not entity_ids:
        return []

    rows = []
    for chunk in EntityChunk.query.filter(EntityChunk.entity_id.in_(entity_ids)).all():
        e = entity_ids.get(chunk.entity_id)
        if e is None:
            continue
        entity_data = {
            "id": e.id,
            "title": e.title,
            "type": e.type,
            "status": e.status,
            "due_at": e.due_at.isoformat() if e.due_at else None,
            "follow_up_at": e.follow_up_at.isoformat() if e.follow_up_at else None,
            "content_preview": (e.content or "")[:300],
        }
        rows.append((chunk.entity_id, chunk.chunk_text, chunk.embedding, entity_data))
    return rows


def _embed_texts(titles):
    """Batch-embed a list of titles. Returns list of vectors (same order).

    Returns empty list if OPENAI_API_KEY is absent or on error.
    Thin wrapper so tests can patch services.v4_reconciliation._embed_texts.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return []
    if not titles:
        return []
    try:
        from services.embeddings import _embed_texts as _oe
        return _oe(titles)
    except Exception as e:
        logger.error("batch embed failed: %s", e)
        return []


def _exact_match(title, entity_type):
    """Return a score-1.0 candidate if an entity with this exact title exists."""
    from models import Entity
    from sqlalchemy import func
    entity = Entity.query.filter(
        Entity.type == entity_type,
        func.lower(Entity.title) == title.lower(),
        Entity.lifecycle != "deleted",
    ).first()
    if entity is None:
        return []
    return [{
        "id": entity.id,
        "title": entity.title,
        "type": entity.type,
        "status": entity.status,
        "due_at": entity.due_at.isoformat() if entity.due_at else None,
        "follow_up_at": entity.follow_up_at.isoformat() if entity.follow_up_at else None,
        "content_preview": (entity.content or "")[:300],
        "score": 1.0,
    }]


# ── Workspace catalog ────────────────────────────────────────────────────────

def _build_catalog_block():
    """Return a formatted string listing all active projects and areas.

    Used to give the reconciler model explicit visibility into the workspace
    so it can match paraphrased project names (e.g. "Deals agent family" →
    "GTM agent family support") without relying solely on embedding similarity.

    Capped at CATALOG_CHAR_CAP characters (≈ 2k tokens), truncated by most
    recently updated first.
    """
    from models import Entity

    entities = (
        Entity.query
        .filter(
            Entity.type.in_(["project", "area"]),
            Entity.lifecycle == "active",
        )
        .order_by(Entity.updated_at.desc())
        .all()
    )

    if not entities:
        return ""

    lines = []
    total = 0
    header = "WORKSPACE CATALOG (active projects and areas — check before deciding 'new'):\n"
    total += len(header)

    for e in entities:
        summary = (e.content or "").replace("\n", " ")[:120].strip()
        line = f"  [{e.type}] {e.title}"
        if summary:
            line += f" — {summary}"
        line += "\n"
        if total + len(line) > CATALOG_CHAR_CAP:
            break
        lines.append(line)
        total += len(line)

    if not lines:
        return ""

    return header + "".join(lines)


# ── LLM reconciliation call ───────────────────────────────────────────────────

def _call_model(enriched):
    if not os.getenv("OPENAI_API_KEY"):
        return _heuristic_decisions(enriched)

    today = date.today().isoformat()
    catalog_block = _build_catalog_block()
    user_payload = [
        {
            "index": i,
            "candidate": {
                "type": item["candidate"].get("type"),
                "title": item["candidate"].get("title"),
                "content": item["candidate"].get("content"),
                "evidence": item["candidate"].get("evidence"),
                "due_at": item["candidate"].get("due_at"),
                "follow_up_at": item["candidate"].get("follow_up_at"),
                "assigned_to": item["candidate"].get("assigned_to"),
                "relationship_type": item["candidate"].get("relationship_type"),
                "confidence": item["candidate"].get("confidence"),
            },
            "existing_matches": [
                {
                    "id": m["id"],
                    "title": m["title"],
                    "status": m["status"],
                    "due_at": m["due_at"],
                    "follow_up_at": m["follow_up_at"],
                    "content_preview": m["content_preview"],
                    "similarity_score": round(m["score"], 3),
                }
                for m in item["matches"]
            ],
        }
        for i, item in enumerate(enriched)
    ]

    try:
        response = get_openai_client().chat.completions.create(
            model=RECONCILIATION_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.format(
                    today=today,
                    catalog_block=catalog_block,
                )},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        if raw.strip().startswith("["):
            logger.warning(
                "reconciliation model returned an array (not an object). "
                "Content snippet: %r. Falling back to heuristics.",
                raw[:200],
            )
            return _heuristic_decisions(enriched)
        if not raw.strip().startswith("{"):
            logger.warning(
                "reconciliation model returned non-object response (type hint: %r). "
                "Content snippet: %r. Falling back to heuristics.",
                type(raw).__name__, raw[:200],
            )
            return _heuristic_decisions(enriched)
        parsed = json.loads(raw)
        logger.info("reconciliation raw response OK (type=%s, snippet=%r)", type(parsed).__name__, str(parsed)[:100])
        raw_decisions = parsed.get("decisions")
        if not isinstance(raw_decisions, list):
            logger.warning(
                "reconciliation model response has no 'decisions' list (got %s). "
                "Content snippet: %r. Falling back to heuristics.",
                type(raw_decisions).__name__, raw[:200],
            )
            return _heuristic_decisions(enriched)
        logger.info("reconciliation model returned %d decisions", len(raw_decisions))
        return raw_decisions
    except Exception as e:
        logger.error("reconciliation model call failed: %s", e)
        return _heuristic_decisions(enriched)


def _heuristic_decisions(enriched):
    """Fallback when the model call fails or OPENAI_API_KEY is absent.

    Exact matches (score=1.0) → link; everything else → new.
    """
    decisions = []
    for item in enriched:
        matches = item.get("matches") or []
        candidate = item["candidate"]
        top = matches[0] if matches else None
        if top and top["score"] >= 1.0:
            decisions.append({
                "action": "link",
                "target_id": top["id"],
                "fields": {},
                "relationship_type": None,
                "confidence": candidate.get("confidence", 0.5),
                "reason": "exact title match (heuristic fallback)",
            })
        else:
            decisions.append({
                "action": "new",
                "target_id": None,
                "fields": {},
                "relationship_type": None,
                "confidence": candidate.get("confidence", 0.0),
                "reason": "no match found (heuristic fallback)",
            })
    return decisions


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
