"""Project completion rollup: summarize project notes → area retrospective note."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select

from extensions import db
from models import BucketType, Note, Project, Tag, note_projects
from services.summarizer import Summarizer


def _resolve_or_create_tags(tag_names: list[str]) -> list[Tag]:
    tags: list[Tag] = []
    for name in tag_names:
        name = name.strip().lower()
        if not name:
            continue
        tag = Tag.query.filter(Tag.name.ilike(name)).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
        tags.append(tag)
    return tags


def _notes_for_project(project_id: str) -> list[Note]:
    """Active notes linked via M2M or legacy ``project_id``."""
    nid_subq = select(note_projects.c.note_id).where(
        note_projects.c.project_id == project_id
    )
    return (
        Note.query.filter(
            Note.is_archived.is_(False),
            or_(Note.project_id == project_id, Note.id.in_(nid_subq)),
        )
        .order_by(Note.created_at.asc())
        .distinct()
        .all()
    )


def _retrospective_body_markdown(project_name: str, sections: dict) -> str:
    """Build markdown body from retrospective section strings."""
    if sections.get("_empty_project"):
        filler = "_No notes were linked to this project._"
        accomplished = key_decisions = lessons_learned = outstanding_items = filler
    else:
        accomplished = (sections.get("accomplished") or "").strip() or "_Nothing noteworthy captured._"
        key_decisions = (sections.get("key_decisions") or "").strip() or "_None noted._"
        lessons_learned = (sections.get("lessons_learned") or "").strip() or "_None noted._"
        outstanding_items = (sections.get("outstanding_items") or "").strip() or "_None noted._"

    return (
        f"# Project retrospective: {project_name}\n\n"
        "## What was accomplished\n\n"
        f"{accomplished}\n\n"
        "## Key decisions\n\n"
        f"{key_decisions}\n\n"
        "## Lessons learned\n\n"
        f"{lessons_learned}\n\n"
        "## Outstanding items\n\n"
        f"{outstanding_items}\n\n"
        "#retrospective #project-complete"
    )


def _maybe_queue_embedding(note_id: str, raw_text: str) -> None:
    try:
        from flask import has_request_context

        if has_request_context():
            from api.notes import _queue_embedding

            _queue_embedding(note_id, raw_text)
    except Exception:
        pass


def rollup_project_to_area(
    project_id: str,
    *,
    summarizer: Summarizer | None = None,
) -> Note:
    """
    Summarize all notes linked to ``project_id`` with Claude, create a summary note
    in the project's parent Area with hashtags ``#retrospective`` and
    ``#project-complete``, then archive the project.

    Returns the new ``Note``.
    """
    project = db.session.get(Project, project_id)
    if not project:
        raise ValueError(f"project not found: {project_id}")
    if not project.area_id:
        raise ValueError("project has no parent area; cannot rollup to area")

    notes = _notes_for_project(project_id)
    svc = summarizer or Summarizer()

    if not notes:
        sections = {"_empty_project": True}
        token_hint = {"token_count": 0, "model_used": svc._model}
    else:
        result = svc.summarize_project_retrospective(notes, project.name)
        sections = {k: result.get(k, "") for k in ("accomplished", "key_decisions", "lessons_learned", "outstanding_items")}
        token_hint = {
            "token_count": result.get("token_count", 0),
            "model_used": result.get("model_used"),
        }

    raw_text = _retrospective_body_markdown(project.name, sections)

    tag_objs = _resolve_or_create_tags(["retrospective", "project-complete"])
    summary_note = Note(
        raw_text=raw_text,
        bucket=BucketType.AREAS,
        area_id=project.area_id,
        project_id=None,
        ai_meta={
            "rollup": True,
            "rollup_project_id": project_id,
            "rollup_generated_at": datetime.utcnow().isoformat() + "Z",
            "rollup_note_count": len(notes),
            **token_hint,
        },
    )
    summary_note.tags = tag_objs
    db.session.add(summary_note)

    project.is_archived = True

    db.session.commit()
    _maybe_queue_embedding(summary_note.id, summary_note.raw_text)
    return summary_note
