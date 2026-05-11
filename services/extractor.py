"""
GPT-4o Structured Outputs extraction service.
Extracts entities (tasks, people, tags, project/area match) from any content
in a single LLM call using strict Pydantic schemas.

Also provides deterministic markdown checkbox (- [ ] / - [x]) inline task sync.
"""
import hashlib
import os
import re
import logging
from typing import Optional, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Markdown checklist lines: '- [ ] title' / '- [x] title' (x/X = done)
_CHECKBOX_LINE_RE = re.compile(r"^\s*-\s*\[\s*([ xX])\s*\]\s+(.+)$")

_client = None


def normalize_inline_task_title(title: str) -> str:
    """Normalize checkbox task text for stable hashing (case- and whitespace-insensitive)."""
    return " ".join(title.strip().lower().split())


def inline_task_title_hash(title: str) -> str:
    return hashlib.sha256(normalize_inline_task_title(title).encode("utf-8")).hexdigest()


def parse_inline_checkbox_lines(raw_text: str) -> list[tuple[str, str, "TaskStatus"]]:
    """
    Parse '- [ ]' / '- [x]' lines. Returns deduped (title_hash, display_title, status) in first-seen order.
    Later duplicate hashes (same normalized title) keep the last line's title text and checkbox state.
    """
    from models import TaskStatus

    ordered: dict[str, tuple[str, str, TaskStatus]] = {}
    order: list[str] = []
    for line in (raw_text or "").splitlines():
        m = _CHECKBOX_LINE_RE.match(line)
        if not m:
            continue
        mark, title_raw = m.group(1), m.group(2)
        title = title_raw.strip()
        if not title:
            continue
        normalized = normalize_inline_task_title(title)
        if not normalized:
            continue
        h = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        status = TaskStatus.DONE if mark.strip().lower() == "x" else TaskStatus.PENDING
        if h not in ordered:
            order.append(h)
        ordered[h] = (h, title[:500], status)
    return [ordered[h] for h in order]


def extract_inline_tasks(
    note_id: str,
    raw_text: str,
    project_id: Optional[str] = None,
    area_id: Optional[str] = None,
) -> list[dict]:
    """
    Upsert Task rows for markdown checkbox lines on this note; cancel extractor-managed
    rows whose checkbox lines disappeared.

    Keys tasks by (note_id, inline_title_hash). Only rows with non-null inline_title_hash
    are cancelled when their line is removed; manually linked tasks (note_id set, hash null)
    are left unchanged.
    """
    from models import Task, TaskStatus
    from extensions import db

    parsed = parse_inline_checkbox_lines(raw_text)
    current_hashes = {h for h, _, _ in parsed}

    if current_hashes:
        stale = Task.query.filter(
            Task.note_id == note_id,
            Task.inline_title_hash.isnot(None),
            ~Task.inline_title_hash.in_(current_hashes),
        )
    else:
        stale = Task.query.filter(
            Task.note_id == note_id,
            Task.inline_title_hash.isnot(None),
        )
    for task in stale.all():
        task.status = TaskStatus.CANCELLED

    for h, title, status in parsed:
        task = Task.query.filter_by(note_id=note_id, inline_title_hash=h).first()
        if task:
            task.title = title
            task.status = status
            task.project_id = project_id
            task.area_id = area_id
        else:
            task = Task(
                title=title,
                note_id=note_id,
                project_id=project_id,
                area_id=area_id,
                status=status,
                inline_title_hash=h,
            )
            db.session.add(task)
    db.session.flush()
    results: list[dict] = []
    for h, _, _ in parsed:
        task = Task.query.filter_by(note_id=note_id, inline_title_hash=h).one()
        results.append(task.to_dict())
    return results


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _client = OpenAI(api_key=key)
    return _client


# ── Pydantic schemas for structured extraction ──────────────────────────────

class ExtractedTask(BaseModel):
    title: str = Field(description="Clear, actionable task title")
    priority: Literal["LOW", "MEDIUM", "HIGH", "URGENT"] = "MEDIUM"
    due_date: Optional[str] = Field(
        default=None,
        description="ISO 8601 date (YYYY-MM-DD) if mentioned, else null"
    )
    project_hint: Optional[str] = Field(
        default=None,
        description="Project name this task belongs to, if mentioned"
    )


class ExtractedPerson(BaseModel):
    name: str
    email: Optional[str] = None
    context: Optional[str] = Field(
        default=None,
        description="How this person is mentioned (e.g. 'meeting contact', 'collaborator')"
    )


class ExtractionResult(BaseModel):
    summary: str = Field(description="One-sentence summary of the note, present tense")
    para_bucket: Literal["INBOX", "PROJECTS", "AREAS", "RESOURCES", "ARCHIVES"] = Field(
        description="PARA classification bucket"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Classification confidence: 0.9+=clear, 0.7-0.9=confident, 0.5-0.7=uncertain, <0.5=very unclear"
    )
    suggested_project: Optional[str] = Field(
        default=None,
        description="Exact name of matching project from the provided list, or new project name if clearly needed"
    )
    suggested_area: Optional[str] = Field(
        default=None,
        description="Exact name of matching area from the provided list, or new area name if clearly needed"
    )
    tasks: list[ExtractedTask] = Field(
        default_factory=list,
        description="Action items explicitly mentioned. Max 5."
    )
    people: list[ExtractedPerson] = Field(
        default_factory=list,
        description="People explicitly named. Max 10."
    )
    tags: list[str] = Field(
        default_factory=list,
        description="2-6 lowercase topic tags. Only add what is clearly relevant."
    )
    reasoning: str = Field(description="One sentence explaining the PARA classification")


EXTRACTION_SYSTEM = """You are an expert knowledge management assistant using the PARA method:
- PROJECTS: active work with a specific outcome/deadline
- AREAS: ongoing responsibilities with no end date (health, finance, relationships)
- RESOURCES: reference material to keep for later (articles, tutorials, facts)
- ARCHIVES: completed or dormant content worth preserving
- INBOX: unclear, needs more context, or doesn't fit above

Extract ALL entities explicitly present in the note. Do not invent information.
For tasks: only extract if there's a clear action item ("need to", "follow up", "schedule", imperative verbs).
For people: only extract proper names of individuals.
For tags: lowercase, specific, 2-6 total."""

EXTRACTION_USER = """Classify and extract entities from this note.

Existing projects (match these names if relevant): {projects}
Existing areas (match these names if relevant): {areas}

Note:
---
{content}
---"""


def extract(content: str, projects: list = None, area_names: list = None) -> ExtractionResult:
    """
    Extract entities and classify content using GPT-4o Structured Outputs.
    Returns ExtractionResult with all extracted entities and PARA classification.
    Falls back to a minimal INBOX result on error.
    """
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not set — returning INBOX fallback")
        return ExtractionResult(
            summary=content[:100],
            para_bucket="INBOX",
            confidence=0.0,
            reasoning="no API key configured",
        )

    projects_str = ", ".join(projects) if projects else "(none)"
    areas_str = ", ".join(area_names) if area_names else "(none)"

    try:
        client = _get_client()
        response = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM},
                {"role": "user", "content": EXTRACTION_USER.format(
                    content=content,
                    projects=projects_str,
                    areas=areas_str,
                )},
            ],
            response_format=ExtractionResult,
            temperature=0,
            max_tokens=800,
        )
        result = response.choices[0].message.parsed
        if result is None:
            raise ValueError("Model returned null parsed result")
        # Clamp tags to 6
        result.tags = result.tags[:6]
        # Clamp tasks to 5
        result.tasks = result.tasks[:5]
        return result

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return ExtractionResult(
            summary=content[:100],
            para_bucket="INBOX",
            confidence=0.0,
            reasoning=f"extraction failed: {e}",
        )


def describe_image(image_data: str, mime_type: str = "image/jpeg") -> str:
    """
    Use GPT-4o vision to extract text description from a base64-encoded image.
    image_data: base64 string (no data: prefix needed here)
    Returns a text description suitable for further extraction.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return ""
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Describe everything in this image that would be useful for a "
                                "personal knowledge management system: text, diagrams, people, "
                                "key topics, action items visible. Be thorough and specific."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}",
                                "detail": "auto",
                            },
                        },
                    ],
                }
            ],
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Image description failed: {e}")
        return ""
