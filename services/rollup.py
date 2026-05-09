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
        body = "(No notes were linked to this project.)"
        token_hint = {"token_count": 0, "model_used": svc._model}
    else:
        result = svc.summarize_notes(
            notes,
            granularity="WEEKLY",
            entity_name=project.name,
        )
        body = result.get("summary_text") or ""
        token_hint = {"token_count": result.get("token_count", 0), "model_used": result.get("model_used")}

    title = f"Project retrospective: {project.name}"
    raw_lines = [
        f"# {title}",
        "",
        "## Summary",
        "",
        body.strip() or "(empty summary)",
        "",
        "#retrospective #project-complete",
    ]
    raw_text = "\n".join(raw_lines)

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
