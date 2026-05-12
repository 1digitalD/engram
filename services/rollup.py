"""Project completion rollup: summarize project notes → area retrospective note.

v2 rewrite: uses Entity, EntityLink, EntityTag, create_entity, archive_entity,
create_link. Replaces Note.query with Entity queries, project.name with
project.title, note.raw_text with note.content.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from extensions import db
from models import Entity, EntityLink, EntityTag, Tag
from services.entity_service import archive_entity
from services.link_service import create_link
from services.summarizer import Summarizer


class _NoteAdapter:
    """Adapt an Entity to look like a legacy Note for the summarizer."""

    def __init__(self, entity: Entity):
        self._entity = entity

    @property
    def raw_text(self) -> str:
        return self._entity.content or ""

    @property
    def id(self) -> str:
        return self._entity.id

    @property
    def created_at(self):
        return self._entity.created_at


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


def _entities_for_project(project_id: str) -> list[Entity]:
    """Active note-type entities linked to the project via EntityLink."""
    linked_subq = select(EntityLink.src_id).where(
        EntityLink.dst_id == project_id
    )
    return (
        Entity.query.filter(
            Entity.type == "note",
            Entity.lifecycle == "active",
            Entity.id.in_(linked_subq),
        )
        .order_by(Entity.created_at.asc())
        .distinct()
        .all()
    )


def _retrospective_body_markdown(project_title: str, sections: dict) -> str:
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
        f"# Project retrospective: {project_title}\n\n"
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


def rollup_project_to_area(
    project_id: str,
    *,
    summarizer: Summarizer | None = None,
) -> Entity:
    """
    Summarize all notes linked to ``project_id`` with Claude, create a summary
    note Entity in the project's parent Area with hashtags ``#retrospective``
    and ``#project-complete``, then archive the project.

    Returns the new summary ``Entity`` (type='note').
    """
    project = Entity.query.filter_by(id=project_id, type="project").first()
    if not project:
        raise ValueError(f"project not found: {project_id}")

    area_id = (project.properties or {}).get("area_id")
    if not area_id:
        raise ValueError("project has no parent area; cannot rollup to area")

    area_id = str(area_id)
    project_id_str = str(project_id)

    note_entities = _entities_for_project(project_id_str)
    svc = summarizer or Summarizer()

    if not note_entities:
        sections = {"_empty_project": True}
        token_hint = {"token_count": 0, "model_used": svc._model}
    else:
        adapted = [_NoteAdapter(e) for e in note_entities]
        result = svc.summarize_project_retrospective(adapted, project.title)
        sections = {
            k: result.get(k, "")
            for k in ("accomplished", "key_decisions", "lessons_learned", "outstanding_items")
        }
        token_hint = {
            "token_count": result.get("token_count", 0),
            "model_used": result.get("model_used"),
        }

    content = _retrospective_body_markdown(project.title, sections)

    tag_objs = _resolve_or_create_tags(["retrospective", "project-complete"])

    summary_note = Entity(
        type="note",
        title=f"Retrospective: {project.title}",
        content=content,
        properties={"bucket": "AREAS", "area_id": area_id},
        source="rollup",
        lifecycle="active",
        ai_meta={
            "rollup": True,
            "rollup_project_id": project_id_str,
            "rollup_generated_at": datetime.utcnow().isoformat() + "Z",
            "rollup_note_count": len(note_entities),
            **token_hint,
        },
        ai_status="pending",
    )
    db.session.add(summary_note)
    db.session.flush()

    for tag in tag_objs:
        db.session.add(EntityTag(entity_id=summary_note.id, tag_id=tag.id))

    create_link(
        src_id=summary_note.id,
        dst_id=project_id_str,
        link_type="related",
        source="rollup",
        actor="system",
    )

    archive_entity(project_id_str, actor="system")

    return summary_note
