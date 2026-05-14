"""
Multi-modal ingestion pipeline — v2 Entity model.

Handles text, image, PDF, and URL inputs — extracts content, classifies,
resolves entities, and auto-creates Entity records at >= 85% confidence.

Tags attached via EntityTag. Links created via EntityLink.
Embed/autolink jobs enqueued via ai_pipeline job queue.
"""
from __future__ import annotations

import base64
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.85


# ── Media extraction ────────────────────────────────────────────────────────

def extract_from_pdf(pdf_bytes: bytes) -> str:
    """Extract Markdown text from PDF bytes using pymupdf4llm."""
    doc = None
    try:
        import pymupdf4llm
        import pymupdf
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        md = pymupdf4llm.to_markdown(doc)
        return md
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return ""
    finally:
        if doc:
            doc.close()


def extract_from_url(url: str) -> str:
    """Extract article text from a URL using trafilatura."""
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        text = trafilatura.extract(downloaded, output_format="markdown", include_links=False)
        return text or ""
    except Exception as e:
        logger.error(f"URL extraction failed ({url}): {e}")
        return ""


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.m4a") -> str:
    """Transcribe audio using OpenAI Whisper API."""
    import os
    if not os.getenv("OPENAI_API_KEY"):
        return ""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        import io
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        return transcript.text
    except Exception as e:
        logger.error(f"Audio transcription failed: {e}")
        return ""


def fetch_media_bytes(url: str) -> bytes:
    """Download raw bytes from a URL."""
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read()
    except Exception as e:
        logger.error(f"Failed to fetch media from {url}: {e}")
        return b""


# ── Entity resolution ────────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    return re.sub(r"[^\w\s]", "", s.lower()).strip()


def _resolve_entity(name: str, existing: list, fuzzy_threshold: int = 88) -> object | None:
    """
    Find an entity in `existing` whose `.title` matches `name`.
    Cascade: exact normalized match -> rapidfuzz token_set_ratio >= fuzzy_threshold.
    Returns the matched ORM object or None.
    """
    if not name or not existing:
        return None

    norm = _normalize(name)

    for entity in existing:
        if _normalize(entity.title or "") == norm:
            return entity

    try:
        from rapidfuzz import fuzz
        best_score = 0
        best_match = None
        for entity in existing:
            score = fuzz.token_set_ratio(_normalize(entity.title or ""), norm)
            if score > best_score:
                best_score = score
                best_match = entity
        if best_score >= fuzzy_threshold:
            return best_match
    except ImportError:
        pass

    return None


# ── Main pipeline ────────────────────────────────────────────────────────────

def run_ingestion(
    content: str = "",
    media_url: str = None,
    media_type: str = None,  # "image" | "pdf" | "audio" | "url"
    media_base64: str = None,
    media_mime: str = None,
    source: str = "api",
) -> dict:
    """
    Full ingestion pipeline. Accepts text + optional media.
    Returns a dict with created/matched entities.

    confidence >= CONFIDENCE_THRESHOLD -> auto-create entities
    confidence < threshold -> entity goes to INBOX bucket, suggestions in ai_meta only
    """
    from extensions import db
    from models import Entity, EntityTag, EntityLink, Tag

    # ── Step 1: Extract content from media ──────────────────────────────────
    media_text = ""
    image_b64 = None

    if media_url or media_base64:
        mtype = (media_type or "").lower()

        if mtype == "image":
            if media_base64:
                image_b64 = media_base64
            elif media_url:
                raw = fetch_media_bytes(media_url)
                if raw:
                    image_b64 = base64.b64encode(raw).decode()

            if image_b64:
                from services.extractor import describe_image
                mime = media_mime or "image/jpeg"
                media_text = describe_image(image_b64, mime)

        elif mtype == "pdf":
            raw = b""
            if media_base64:
                raw = base64.b64decode(media_base64)
            elif media_url:
                raw = fetch_media_bytes(media_url)
            if raw:
                media_text = extract_from_pdf(raw)

        elif mtype == "audio":
            raw = b""
            fname = "audio.m4a"
            if media_base64:
                raw = base64.b64decode(media_base64)
            elif media_url:
                raw = fetch_media_bytes(media_url)
                fname = media_url.split("/")[-1] or "audio.m4a"
            if raw:
                media_text = transcribe_audio(raw, fname)

        elif mtype == "url":
            target_url = media_url or ""
            media_text = extract_from_url(target_url)

    # Combine text sources
    full_content = "\n\n".join(filter(None, [content, media_text])).strip()
    if not full_content:
        return {"error": "no content to process"}

    # ── Step 2: Load existing entities for context ───────────────────────────
    existing_projects = Entity.query.filter_by(
        type="project", lifecycle="active"
    ).all()
    existing_areas = Entity.query.filter_by(
        type="area", lifecycle="active"
    ).all()

    project_names = [p.title for p in existing_projects if p.title]
    area_names = [a.title for a in existing_areas if a.title]

    # ── Step 3: AI extraction ────────────────────────────────────────────────
    from services.extractor import extract
    extraction = extract(full_content, projects=project_names, area_names=area_names)

    confident = extraction.confidence >= CONFIDENCE_THRESHOLD

    # ── Step 4: Determine bucket ─────────────────────────────────────────────
    bucket_str = extraction.para_bucket
    if not confident:
        bucket_str = "INBOX"

    # ── Step 5: Resolve / create project ─────────────────────────────────────
    resolved_project = None
    if extraction.suggested_project and confident:
        resolved_project = _resolve_entity(extraction.suggested_project, existing_projects)
        if not resolved_project:
            resolved_project = Entity(
                type="project",
                title=extraction.suggested_project,
                content=f"Auto-created during ingestion of: {full_content[:80]}",
                properties={},
                lifecycle="active",
                ai_meta={"source": "ingestion"},
                ai_status="pending",
            )
            db.session.add(resolved_project)
            db.session.flush()

        if resolved_project and bucket_str == "INBOX":
            bucket_str = "PROJECTS"

    # ── Step 6: Resolve / create area ────────────────────────────────────────
    resolved_area = None
    if extraction.suggested_area and not resolved_project and confident:
        resolved_area = _resolve_entity(extraction.suggested_area, existing_areas)
        if not resolved_area:
            resolved_area = Entity(
                type="area",
                title=extraction.suggested_area,
                properties={},
                lifecycle="active",
                ai_meta={"source": "ingestion"},
                ai_status="pending",
            )
            db.session.add(resolved_area)
            db.session.flush()

        if resolved_area and bucket_str == "INBOX":
            bucket_str = "AREAS"

    # ── Step 7: Resolve people (store in ai_meta, no separate entities) ──────
    resolved_people = []
    for ep in extraction.people:
        resolved_people.append({"name": ep.name, "email": ep.email})

    # ── Step 8: Resolve / create tags ────────────────────────────────────────
    tag_objects = []
    for tag_name in extraction.tags:
        name = tag_name.lower().strip()
        if not name:
            continue
        tag = Tag.query.filter(Tag.name.ilike(name)).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
            db.session.flush()
        tag_objects.append(tag)

    # ── Step 9: Create the note Entity ───────────────────────────────────────
    ai_meta = {
        "source": source,
        "confidence": extraction.confidence,
        "reasoning": extraction.reasoning,
        "bucket": bucket_str,
        "summary": extraction.summary,
        "suggested_project": extraction.suggested_project,
        "suggested_area": extraction.suggested_area,
        "suggested_tags": extraction.tags,
        "extracted_tasks": [t.model_dump() for t in extraction.tasks],
        "extracted_people": [p.model_dump() for p in extraction.people],
        "media_type": media_type,
        "media_url": media_url,
    }

    entity = Entity(
        type="note",
        title=extraction.summary[:100] if extraction.summary else None,
        content=full_content,
        properties={"bucket": bucket_str},
        source=source,
        lifecycle="active",
        ai_meta=ai_meta,
        ai_status="pending",
    )
    db.session.add(entity)
    db.session.flush()

    # ── Step 10: Attach tags via EntityTag ───────────────────────────────────
    for tag in tag_objects:
        et = EntityTag(entity_id=entity.id, tag_id=tag.id)
        db.session.add(et)

    # ── Step 11: Create links to project/area ────────────────────────────────
    if resolved_project:
        link = EntityLink(
            src_id=entity.id,
            dst_id=resolved_project.id,
            link_type="related",
            source="ingestion",
            confidence=extraction.confidence,
        )
        db.session.add(link)

    if resolved_area:
        link = EntityLink(
            src_id=entity.id,
            dst_id=resolved_area.id,
            link_type="related",
            source="ingestion",
            confidence=extraction.confidence,
        )
        db.session.add(link)

    # ── Step 12: Create task Entities from extraction ────────────────────────
    created_tasks = []
    if confident and extraction.tasks:
        for et in extraction.tasks:
            task_props = {"priority": et.priority}
            if et.due_date:
                task_props["due_date"] = et.due_date

            task = Entity(
                type="task",
                title=et.title,
                content=None,
                properties=task_props,
                source="ingestion",
                status="pending",
                lifecycle="active",
                ai_meta={"source_note_id": entity.id},
                ai_status="pending",
            )
            db.session.add(task)
            db.session.flush()
            created_tasks.append(task)

            # Link task to parent note
            task_link = EntityLink(
                src_id=task.id,
                dst_id=entity.id,
                link_type="related",
                source="ingestion",
            )
            db.session.add(task_link)

            # Link task to project if available
            task_project_id = resolved_project.id if resolved_project else None
            if et.project_hint and not task_project_id:
                tp = _resolve_entity(et.project_hint, existing_projects)
                if tp:
                    task_project_id = tp.id

            if task_project_id:
                proj_link = EntityLink(
                    src_id=task.id,
                    dst_id=task_project_id,
                    link_type="related",
                    source="ingestion",
                )
                db.session.add(proj_link)

    db.session.commit()

    # ── Step 13: Enqueue embed/autolink jobs via ai_pipeline ─────────────────
    try:
        from services.ai_pipeline import enqueue_embed, enqueue_autolink
        enqueue_embed(entity.id)
        enqueue_autolink(entity.id)
    except Exception as e:
        logger.warning(f"AI job enqueue failed for {entity.id}: {e}")

    return {
        "entity": entity.to_dict(),
        "tasks": [t.to_dict() for t in created_tasks],
        "people": resolved_people,
        "project": resolved_project.to_dict() if resolved_project else None,
        "area": resolved_area.to_dict() if resolved_area else None,
        "confident": confident,
        "extraction": {
            "summary": extraction.summary,
            "confidence": extraction.confidence,
            "reasoning": extraction.reasoning,
            "bucket": bucket_str,
            "tags": extraction.tags,
        },
    }
