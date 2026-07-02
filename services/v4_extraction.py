"""v4 capture extraction boundary.

The extractor returns candidates only. Reconciliation decides which candidates
are safe to apply and which must become reviewable suggestions.
"""
from __future__ import annotations

import json
import logging
import os

from api.v4_entities import DONE_TASK_STATUSES
from services.title_utils import title_or_placeholder
from utils import get_openai_client
from services.llm_models import resolve_chat_model

logger = logging.getLogger(__name__)

EXTRACTION_MODEL = resolve_chat_model("OPENAI_EXTRACTION_MODEL")
ACTIVITY_UPDATE_EXTRACTION_MODEL = resolve_chat_model("OPENAI_ACTIVITY_UPDATE_MODEL")
ALLOWED_ENTITY_TYPES = {"task", "project", "area", "person", "resource"}
ALLOWED_RELATIONSHIP_TYPES = {"parent", "related", "derived_from", "mentions", "assigned_to", "references", "blocks"}
EXISTING_ENTITY_LIMIT = 50
TASK_RECENT_LIMIT = 15

SYSTEM_PROMPT_TEMPLATE = """You are an extraction engine for a personal knowledge workspace. \
Analyze the note below and return JSON with metadata, link candidates, and entity creation candidates.

RULES:
- Return JSON only. No prose, no markdown fences.
- Do NOT re-extract the source note itself as an entity or link candidate.
- Be exhaustive: extract every actionable item, person, project, area, and resource mentioned.
- Prefer over-extraction — the reconciliation layer decides what to apply.
- Confidence: 0.9+ explicit/unambiguous, 0.7–0.9 strongly implied, 0.5–0.7 inferred, <0.5 speculative.
- DEDUPE WITHIN THIS NOTE: each real-world entity must appear at most ONCE across the entire \
output (combining the `links` and `entities` arrays). If a person, project, area, or resource \
is mentioned multiple times in the note — even with different surface forms ("Priya", "Priya \
Sharma", "she") — emit a single candidate using the most complete name as the title. Likewise, \
do not emit two task candidates that describe the same action; if one action is a more specific \
restatement of another, emit only the more specific one. The reconciliation layer handles \
matches against EXISTING entities; it does NOT dedupe new candidates against each other, so the \
responsibility is yours.
- EXISTING_ENTITIES below lists real projects and areas already in the workspace. \
Treat them two ways at once:
    (a) Direct references: if the note refers to one of these (even loosely / paraphrased), \
reuse its exact title verbatim so the reconciler can match it. Do not invent a variant, \
do not change capitalization, do not pluralize.
    (b) Few-shot examples: they show the level of granularity and naming style this workspace \
uses for "project" and "area". When extracting NEW projects or areas, follow the same shape \
(scope, specificity, phrasing) as these examples.

TASKS — DEDICATED RULE (highest priority extraction):
Tasks are routinely missed when prompts are vague. Apply ALL of the following:
  1. Any section titled "Action Items", "Action items", "Tasks", "TODO", "To do", "Next Steps", \
"Next steps", "Follow-ups", or "Follow ups" — every bullet (or sub-bullet) inside it is a separate \
task candidate, but only if it describes a concrete next action.
  2. Any bullet formatted as "Name:" or "Name —" followed by an action description is a task. \
The Name is the assignee; emit `assigned_to: "<Name>"` and also emit the Name as a `person` candidate.
  3. Any sentence that begins with an imperative verb ("Ship", "Draft", "Send", "Schedule", \
"Define", "Review", "Build"), or contains "needs to", "will", "should", "TODO", "follow up with", \
"remind me", "let's", or "we should" describes a task only when it names a concrete next step, \
owner, or deliverable. Ignore hedged, tentative, or purely reflective language.
  4. Do NOT collapse multiple actions into a single task. "Ask Henry and follow up with Priya" is \
two tasks. "Draft the doc and share by Friday" is one task with a due date; "Draft the doc; then \
review with the team" is two tasks. When in doubt, split.
  5. Keep task titles specific and concrete (≤10 words, starts with a verb, sentence case). \
Prefer the most actionable phrasing; avoid tentative wording like "maybe", "possibly", "could", \
"consider", or "think about". Put extra detail in `content`, not the title.

ENTITY TYPES — use exactly these strings:
  "task"     — See dedicated TASKS rule above. Be selective about tentative phrasing: prefer \
concrete next steps with clear ownership or deliverables over vague intentions.
  "project"  — A named multi-step initiative with a defined outcome. Signals: named goals, \
campaigns, products, anything with multiple tasks beneath it. Do NOT emit a new project for \
a deliverable, milestone, or sub-effort of an existing project (a deck, doc, one-pager, plan, \
review, or meeting belonging to a project in EXISTING_ENTITIES) — emit that as a task and \
link it to the existing project instead. When a note discusses an EXISTING_ENTITIES project \
from a new angle (roadmap, governance, status, planning), that is the SAME project, not a new one.
  "area"     — An ongoing responsibility or life/work domain with no end date. Signals: \
"health", "finance", "work", "home", recurring themes without a completion state.
  "person"   — A named individual. Signals: proper names, @mentions, roles with a clear \
referent ("my manager John"), pronouns only when the referent is unambiguous.
  "resource" — A reference artifact to be consulted or used. Signals: URLs, book/article \
titles, tool names, file names, documents, frameworks, systems.

RELATIONSHIP TYPES — use exactly these strings:
  "parent"       — Source belongs under / is a child of the target (e.g. task under a project, \
project under an area).
  "related"      — General thematic connection when no stronger type fits.
  "derived_from" — Source was created from, inspired by, or is a follow-up to the target.
  "mentions"     — Source references the target without a stronger structural relationship.
  "assigned_to"  — A task or project is owned by or delegated to a person.
  "references"   — Source cites the target as a source, resource, or external reference.
  "blocks"       — A task or project cannot proceed until the target is resolved.

TAGS — lowercase, single words or short kebab-case phrases, high signal-to-noise. \
Extract topic tags, status hints, and domain labels useful for filtering (e.g. "meeting", \
"finance", "follow-up", "engineering", "q3-2025").

Return this exact schema (all fields required, use empty arrays not null):
{
  "title": "5–8 word headline-style title capturing what the note is about. \
No trailing punctuation. Sentence case. Concrete and specific (avoid 'Note about X').",
  "summary": "1–2 sentence summary of what this note is about",
  "intent": "update|task_signal|follow_up|blocker|delegation|reference|junk|note",
  "intent_confidence": 0.0,
  "confidence": 0.0,
  "tags": [{"name": "tag", "confidence": 0.0}],
  "links": [{
    "target_type": "task|project|area|person|resource",
    "title": "canonical title of the entity to link to",
    "relationship_type": "parent|related|derived_from|mentions|assigned_to|references|blocks",
    "confidence": 0.0,
    "evidence": "exact quote or brief rationale"
  }],
  "entities": [{
    "type": "task|project|area|person|resource",
    "title": "concise canonical title",
    "content": "optional detail or description (omit if empty)",
    "due_at": "ISO 8601 date if a deadline is mentioned, else null",
    "follow_up_at": "ISO 8601 date if a follow-up date is mentioned, else null",
    "assigned_to": "person name if task/project is assigned to someone, else null",
    "confidence": 0.0,
    "evidence": "exact quote or brief rationale"
  }]
}

WORKED EXAMPLE — note → expected extraction (illustrative; follow the same granularity):

Note (input):
  Sync notes — agent convergence

  Decisions:
  - Python is the preferred stack for new agents.

  Action Items
  - Danish: write a standardized boilerplate skill for new agents
  - Vignesh: document deal agent architecture for next week
  - Kurt: facilitate alignment with Vaibhav and David on TypeScript convergence

  Next Steps
  - Build evals infrastructure with interaction logging from day one
  - Review Vignesh's doc next week

Expected entities (abbreviated):
  - task "Write standardized boilerplate skill for new agents" assigned_to "Danish", evidence: \
"Danish: write a standardized boilerplate skill for new agents"
  - task "Document deal agent architecture" assigned_to "Vignesh", evidence: \
"Vignesh: document deal agent architecture for next week"
  - task "Facilitate TypeScript convergence alignment" assigned_to "Kurt", evidence: \
"Kurt: facilitate alignment with Vaibhav and David on TypeScript convergence"
  - task "Build evals infrastructure with interaction logging", evidence: "Build evals \
infrastructure with interaction logging from day one"
  - task "Review Vignesh's deal agent doc", evidence: "Review Vignesh's doc next week"
  - person "Danish"
  - person "Vignesh"
  - person "Kurt"
  - person "Vaibhav"
  - person "David"
  - project "Agent convergence"

Note that EVERY action-items bullet became a task. EVERY named person became a person candidate \
(exactly once each, even though Vaibhav and David are mentioned inside another task's description). \
Follow this density and dedup discipline.
"""

# Backwards-compatible alias for tests / other importers.
SYSTEM_PROMPT = SYSTEM_PROMPT_TEMPLATE


def _recent_existing_entities(limit=EXISTING_ENTITY_LIMIT):
    """Fetch the most recently updated active projects, areas, and open tasks.

    Returns a dict {"project": [titles], "area": [titles], "task": [titles]}.
    Returns empty lists if no Flask app context or DB is available.
    """
    try:
        from models import Entity
    except Exception:
        return {"project": [], "area": [], "task": []}

    out = {"project": [], "area": [], "task": []}
    type_limits = {"project": limit, "area": limit, "task": TASK_RECENT_LIMIT}
    for entity_type in ("project", "area", "task"):
        try:
            query = Entity.query.filter(
                Entity.type == entity_type,
                Entity.lifecycle == "active",
            )
            if entity_type == "task":
                query = query.filter(~Entity.status.in_(DONE_TASK_STATUSES))
            rows = (
                query.order_by(Entity.updated_at.desc())
                .limit(type_limits[entity_type])
                .all()
            )
            out[entity_type] = [r.title for r in rows if r.title]
        except Exception as exc:
            logger.warning("failed to fetch recent %s entities: %s", entity_type, exc)
            out[entity_type] = []
    return out


def _format_existing_entities_block(existing):
    """Render the EXISTING_ENTITIES section appended to the system prompt."""
    def fmt(items):
        return "\n".join(f"- {t}" for t in items) if items else "- (none yet)"

    return (
        "\n\nEXISTING_ENTITIES (use as direct references AND as few-shot examples "
        "for the corresponding type):\n"
        "Projects:\n"
        f"{fmt(existing.get('project') or [])}\n"
        "Recent Active Open Tasks:\n"
        f"{fmt(existing.get('task') or [])}\n"
        "Areas:\n"
        f"{fmt(existing.get('area') or [])}\n"
    )


RECENT_CONTEXT_NOTE_LIMIT = 4
RECENT_CONTEXT_EXCERPT_CHARS = 350


def _recent_context_notes(exclude_note_id=None, limit=RECENT_CONTEXT_NOTE_LIMIT):
    """Most recent notes (including activity updates) for situational context.

    Captured notes reference each other ("still waiting on the same thing",
    "no update on this"); without the recent thread the extractor can't
    resolve those references or tell new work from already-known work.
    """
    try:
        from models import Entity
    except Exception:
        return []

    try:
        query = Entity.query.filter(
            Entity.type == "note",
            Entity.lifecycle == "active",
        )
        if exclude_note_id:
            query = query.filter(Entity.id != exclude_note_id)
        rows = (
            query.order_by(Entity.created_at.desc())
            .limit(limit)
            .all()
        )
    except Exception as exc:
        logger.warning("failed to fetch recent context notes: %s", exc)
        return []

    out = []
    for note in rows:
        out.append({
            "title": title_or_placeholder(note),
            "date": note.created_at.date().isoformat() if note.created_at else "",
            "excerpt": (note.content or "")[:RECENT_CONTEXT_EXCERPT_CHARS],
        })
    return out


def _format_recent_context_block(notes):
    if not notes:
        return ""
    lines = []
    for note in notes:
        lines.append(f"- [{note['date']}] {note['title']}: {note['excerpt']}")
    return (
        "\n\nRECENT_CONTEXT (the user's most recent notes, newest first — situational "
        "awareness ONLY):\n"
        "Use these to resolve references in the new note (\"this\", \"same issue\", "
        "\"still waiting\"), to recognize ongoing threads, and to choose canonical "
        "titles consistent with how the work was previously described. Do NOT extract "
        "entities, tasks, or links that appear only in RECENT_CONTEXT — extract solely "
        "from the new note below.\n"
        + "\n".join(lines)
        + "\n"
    )


def _format_thread_context_block(thread_entity):
    if thread_entity is None:
        return ""
    summary = (thread_entity.get("content") or "").replace("\n", " ")[:200].strip()
    title = thread_entity.get("title") or "Untitled"
    entity_type = thread_entity.get("type") or "entity"
    lines = [
        "\n\nTHREAD_CONTEXT (user attached this capture to the current thread — bias only):",
        f"The user is capturing while viewing: [{entity_type}] {title}",
    ]
    if summary:
        lines.append(f"Summary: {summary}")
    lines.append(
        "Prefer interpreting progress or status remarks in this note as referring to "
        "this thread when plausible. This is still a generic capture note, not an "
        "automatic activity update."
    )
    return "\n".join(lines) + "\n"


def _build_system_prompt(exclude_note_id=None, thread_entity=None):
    existing = _recent_existing_entities()
    context_notes = _recent_context_notes(exclude_note_id=exclude_note_id)
    return (
        SYSTEM_PROMPT_TEMPLATE
        + _format_existing_entities_block(existing)
        + _format_recent_context_block(context_notes)
        + _format_thread_context_block(thread_entity)
    )


def normalize_candidates(payload: dict) -> dict:
    """Normalize and validate a pre-extracted candidates payload.

    Accepts the same schema as the extraction output so a calling agent can
    skip the LLM step and submit structured candidates directly to reconciliation.
    """
    return _normalize_payload(payload)


def _thread_entity_dict(entity):
    if entity is None:
        return None
    return {
        "id": entity.id,
        "type": entity.type,
        "title": entity.title,
        "content": entity.content,
    }


def extract_capture_candidates(content, mode="auto", exclude_note_id=None, thread_entity=None):
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
        model=EXTRACTION_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _build_system_prompt(exclude_note_id=exclude_note_id, thread_entity=thread_entity)},
            {"role": "user", "content": content[:12000]},
        ],
    )
    raw = response.choices[0].message.content or "{}"
    return _normalize_payload(json.loads(raw))


def _normalize_payload(payload):
    if not isinstance(payload, dict):
        return {}

    return {
        "title": _text(payload.get("title")),
        "summary": _text(payload.get("summary")),
        "intent": _intent(payload.get("intent")),
        "intent_confidence": _confidence(payload.get("intent_confidence")),
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
        "due_at": _date(item.get("due_at")),
        "follow_up_at": _date(item.get("follow_up_at")),
        "assigned_to": _text(item.get("assigned_to")),
        "confidence": _confidence(item.get("confidence")),
        "evidence": _text(item.get("evidence") or item.get("reason")),
    }


def _date(value):
    """Return an ISO 8601 date string if parseable, otherwise None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"null", "none", "n/a", ""}:
        return None
    # Accept only plausible ISO-looking strings to avoid storing model hallucinations
    import re
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    return None


def _list(value):
    return value if isinstance(value, list) else []


def _text(value):
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    # Source notes (meeting transcripts, web captures) sometimes arrive
    # HTML-escaped and the model echoes the escapes back ("R&amp;D",
    # "&quot;blocked&quot;"). Stored titles must be plain text or both
    # display and title matching degrade.
    if "&" in cleaned:
        import html
        cleaned = html.unescape(cleaned)
    return cleaned or None


def _confidence(value):
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(confidence, 1.0))


def _intent(value):
    normalized = _text(value)
    if not normalized:
        return None
    normalized = normalized.lower().replace("-", "_").replace(" ", "_")
    if normalized in {"update", "task_signal", "follow_up", "blocker", "delegation", "reference", "junk", "note"}:
        return normalized
    return None


# ── Lightweight activity-update extraction ────────────────────────────────────

ACTIVITY_UPDATE_SYSTEM_PROMPT = """You are a lightweight extraction engine for activity/progress updates on tasks and projects. Your ONLY job is to extract three things:

1. STATUS: Optional status change implied about the entity being updated.
   Examples: "done for now" / "shipped" / "finished" → done, "waiting on infra" → waiting,
   "blocked by security review" → blocked, "started working on this" → in_progress.
   Return null if no status change is implied. Include a top-level confidence (0.0–1.0) for the status
   extraction when status is non-null.

2. FOLLOW-UP DATES: Any explicit date, day, or time frame when the next follow-up or check-in should happen.
   Examples: "review next Friday" → next Friday's date, "circle back in 3 days" → 3 days from now,
   "follow up June 15" → 2026-06-15, "check in 2 weeks" → 2 weeks from now.
   Return as ISO 8601 date string (YYYY-MM-DD). Use today's date as context for relative dates.
   Return null if no follow-up date is mentioned.

3. NEW TASKS: Any new actionable items mentioned in the update that are NOT the same as the update itself.
   Examples: "Need to update the docs too" → task, "Priya will handle the deployment" → task assigned to Priya.
   Each task should have a title (concise, starts with verb, ≤10 words), optional content, optional due date,
   optional follow_up_at (when the follow-up date refers to that new work), optional assignee name.
   Return empty list if no new tasks are mentioned.

FOLLOW-UP ROUTING:
- Top-level follow_up_at is for checking back on the entity being updated.
- When the update closes the entity (status done/cancelled) AND introduces new work, put the follow-up
  date on the new task (due_at or follow_up_at), NOT on the top-level follow_up_at for the closing entity.
- When follow-up language clearly refers to new work ("follow up next week on security review"), attach
  the date to that task instead of the top-level follow_up_at.

Example — closure + spin-off:
Update: "This is done for now. Need to clear security review before launch — follow up next week on that."
→ status: "done", confidence: 0.9, follow_up_at: null,
  tasks: [{title: "Clear security review", follow_up_at: "YYYY-MM-DD", confidence: 0.88}]
(where YYYY-MM-DD is ~7 days from today)

Return JSON only. No prose, no markdown fences.

Schema:
{
  "status": "done" | "waiting" | "blocked" | "in_progress" | null,
  "confidence": 0.0,
  "follow_up_at": "YYYY-MM-DD" or null,
  "tasks": [{
    "title": "concise task title",
    "content": "optional detail",
    "due_at": "YYYY-MM-DD" or null,
    "follow_up_at": "YYYY-MM-DD" or null,
    "assigned_to": "person name" or null,
    "confidence": 0.0
  }]
}"""


ACTIVITY_UPDATE_STATUSES = {"done", "waiting", "blocked", "in_progress"}


def _normalize_activity_status(value):
    normalized = _text(value)
    if not normalized:
        return None
    normalized = normalized.lower().replace("-", "_").replace(" ", "_")
    if normalized in ACTIVITY_UPDATE_STATUSES:
        return normalized
    return None


def extract_dates_and_tasks_from_update(content, today_iso=None):
    """Lightweight extraction for activity-update content.

    Returns {"status": str|None, "confidence": float, "follow_up_at": "YYYY-MM-DD"|None, "tasks": [...]}.
    Uses a cheaper/faster model than the full capture extraction.
    """
    empty = {"status": None, "confidence": 0.0, "follow_up_at": None, "tasks": []}
    if not content or not content.strip():
        return empty

    try:
        from flask import current_app
        if current_app.config.get("TESTING") and os.getenv("ENGRAM_ALLOW_TEST_AI") != "1":
            return empty
    except RuntimeError:
        pass

    if not os.getenv("OPENAI_API_KEY"):
        return empty

    from datetime import date
    today = today_iso or date.today().isoformat()

    user_prompt = f"Today is {today}.\n\nUpdate content:\n{content[:4000]}"

    try:
        response = get_openai_client().chat.completions.create(
            model=ACTIVITY_UPDATE_EXTRACTION_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": ACTIVITY_UPDATE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)
    except Exception as exc:
        logger.warning("activity-update extraction failed: %s", exc)
        return empty

    status = _normalize_activity_status(result.get("status"))
    return {
        "status": status,
        "confidence": _confidence(result.get("confidence")) if status else 0.0,
        "follow_up_at": _date(result.get("follow_up_at")),
        "tasks": _normalize_activity_tasks(result.get("tasks") or []),
    }


def _normalize_activity_tasks(items):
    tasks = []
    for item in (_list(items)):
        if not isinstance(item, dict):
            continue
        title = _text(item.get("title"))
        if not title:
            continue
        tasks.append({
            "title": title[:160],
            "content": _text(item.get("content")),
            "due_at": _date(item.get("due_at")),
            "follow_up_at": _date(item.get("follow_up_at")),
            "assigned_to": _text(item.get("assigned_to")),
            "confidence": _confidence(item.get("confidence")),
        })
    return tasks
