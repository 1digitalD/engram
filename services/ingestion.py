"""
Multi-modal ingestion pipeline.
Handles text, image, PDF, and URL inputs — extracts content, classifies,
resolves entities, and auto-creates records at ≥ 85% confidence.
"""
import os
import base64
import logging
import re
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.85


# ── Media extraction ────────────────────────────────────────────────────────

def extract_from_pdf(pdf_bytes: bytes) -> str:
    """Extract Markdown text from PDF bytes using pymupdf4llm."""
    try:
        import pymupdf4llm
        import pymupdf
        import io
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        md = pymupdf4llm.to_markdown(doc)
        return md
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return ""


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
    Find an entity in `existing` whose `.name` matches `name`.
    Cascade: exact normalized match → rapidfuzz token_set_ratio ≥ fuzzy_threshold.
    Returns the matched ORM object or None.
    """
    if not name or not existing:
        return None

    norm = _normalize(name)

    for entity in existing:
        if _normalize(entity.name) == norm:
            return entity

    try:
        from rapidfuzz import fuzz
        best_score = 0
        best_match = None
        for entity in existing:
            score = fuzz.token_set_ratio(_normalize(entity.name), norm)
            if score > best_score:
                best_score = score
                best_match = entity
        if best_score >= fuzzy_threshold:
            return best_match
    except ImportError:
        pass

    return None


# Convenience aliases kept for any external callers
resolve_project = _resolve_entity
resolve_area = _resolve_entity
resolve_person = _resolve_entity


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
    Returns a dict with created/matched entities and the note.

    confidence ≥ CONFIDENCE_THRESHOLD → auto-create entities
    confidence < threshold → note goes to INBOX, entities stored in ai_meta only
    """
    from extensions import db
    from models import Note, BucketType, Tag, Project, Area, Person, Task

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
    existing_projects = Project.query.filter_by(is_archived=False).all()
    existing_areas = Area.query.all()
    existing_people = Person.query.all()

    project_names = [p.name for p in existing_projects]
    area_names = [a.name for a in existing_areas]

    # ── Step 3: AI extraction ────────────────────────────────────────────────
    from services.extractor import extract
    extraction = extract(full_content, projects=project_names, area_names=area_names)

    confident = extraction.confidence >= CONFIDENCE_THRESHOLD

    # ── Step 4: Entity resolution + auto-create ──────────────────────────────
    resolved_project = None
    resolved_area = None
    resolved_person = None  # primary person associated with the note
    created_tasks = []
    resolved_people = []

    bucket_str = extraction.para_bucket
    try:
        bucket = BucketType(bucket_str.upper())
    except ValueError:
        bucket = BucketType.INBOX

    if not confident:
        bucket = BucketType.INBOX

    # Resolve / create project
    if extraction.suggested_project and confident:
        resolved_project = resolve_project(extraction.suggested_project, existing_projects)
        if not resolved_project:
            resolved_project = Project(
                name=extraction.suggested_project,
                description=f"Auto-created during ingestion of: {full_content[:80]}",
            )
            db.session.add(resolved_project)
            db.session.flush()  # get ID before commit

        if resolved_project and bucket == BucketType.INBOX:
            bucket = BucketType.PROJECTS

    # Resolve / create area
    if extraction.suggested_area and not resolved_project and confident:
        resolved_area = resolve_area(extraction.suggested_area, existing_areas)
        if not resolved_area:
            resolved_area = Area(name=extraction.suggested_area)
            db.session.add(resolved_area)
            db.session.flush()

        if resolved_area and bucket == BucketType.INBOX:
            bucket = BucketType.AREAS

    # Resolve / create people
    for ep in extraction.people:
        person = resolve_person(ep.name, existing_people + resolved_people)
        if not person:
            if confident:
                person = Person(name=ep.name, email=ep.email)
                db.session.add(person)
                db.session.flush()
                resolved_people.append(person)
            # else: store mention in ai_meta only
        else:
            resolved_people.append(person)

    # Primary person = first one mentioned
    if resolved_people:
        resolved_person = resolved_people[0]

    # Resolve / create tags
    tag_objects = []
    for tag_name in extraction.tags:
        name = tag_name.lower().strip()
        if not name:
            continue
        tag = Tag.query.filter(Tag.name.ilike(name)).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
        tag_objects.append(tag)

    # ── Step 5: Create the note ──────────────────────────────────────────────
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

    note = Note(
        raw_text=full_content,
        bucket=bucket,
        project_id=resolved_project.id if resolved_project else None,
        area_id=resolved_area.id if resolved_area else None,
        person_id=resolved_person.id if resolved_person else None,
        ai_meta=ai_meta,
    )
    note.tags = tag_objects
    db.session.add(note)
    db.session.flush()

    # ── Step 6: Create tasks ─────────────────────────────────────────────────
    if confident and extraction.tasks:
        for et in extraction.tasks:
            # Resolve task's project hint
            task_project_id = resolved_project.id if resolved_project else None
            if et.project_hint and not task_project_id:
                tp = resolve_project(et.project_hint, existing_projects)
                if tp:
                    task_project_id = tp.id

            due = None
            if et.due_date:
                try:
                    due = datetime.fromisoformat(et.due_date)
                except ValueError:
                    pass

            from models import Priority, TaskStatus
            try:
                priority = Priority(et.priority.upper())
            except ValueError:
                priority = Priority.MEDIUM

            task = Task(
                title=et.title,
                project_id=task_project_id,
                priority=priority,
                due_date=due,
            )
            db.session.add(task)
            created_tasks.append(task)

    db.session.commit()

    # Queue embedding + auto-link in background (with app context)
    try:
        from flask import current_app
        app = current_app._get_current_object()

        def _bg_embed_and_link(note_id, text, _app):
            with _app.app_context():
                _background_embed(note_id, text)
                _background_autolink(note_id)

        threading.Thread(
            target=_bg_embed_and_link,
            args=(note.id, full_content, app),
            daemon=True,
        ).start()
    except RuntimeError:
        # Outside request context (e.g. tests) — skip background work
        pass

    return {
        "note": note.to_dict(),
        "tasks": [t.to_dict() for t in created_tasks],
        "people": [p.to_dict() for p in resolved_people],
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


def _background_embed(note_id: str, text: str):
    try:
        from services.embeddings import embed_note
        embed_note(note_id, text)
    except Exception as e:
        logger.warning(f"Background embedding failed for {note_id}: {e}")


def _background_autolink(note_id: str):
    try:
        from services.embeddings import find_related_note_ids
        from services.links import create_embedding_links
        related = find_related_note_ids(note_id, limit=5, min_similarity=0.82)
        if related:
            create_embedding_links(note_id, related)
    except Exception as e:
        logger.debug(f"Auto-link skipped for {note_id}: {e}")
