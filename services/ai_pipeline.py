"""Unified Async AI Pipeline — classify, embed, autolink via the Job system.

This module provides:
- enqueue_classify/embed/autolink: create jobs for async processing
- run_classify/embed/autolink: job handlers registered with the job worker
- chunk_text: split content into embedding-ready chunks

The capture flow is async:
1. Entity is created and saved to DB (fast, < 50ms)
2. classify + embed jobs are enqueued
3. Response returned to caller immediately
4. Background worker picks up jobs and processes them
"""

import logging
import os
import re
from datetime import datetime, timezone

from extensions import db
from models import Entity, EntityChunk, EntityTag, Job, Tag
from services.embeddings import chunk_text
from services.entity_service import _write_event

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────

CLASSIFY_CONFIDENCE_THRESHOLD = float(
    os.getenv("CLASSIFY_CONFIDENCE_THRESHOLD", "0.70")
)
AUTOLINK_CONFIDENCE_THRESHOLD = float(
    os.getenv("AUTOLINK_CONFIDENCE_THRESHOLD", "0.92")
)
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
EMBED_DIMS = int(os.getenv("EMBED_DIMS", "1536"))

# Chunking defaults (token-aware: ~4 chars/token)
DEFAULT_CHUNK_SIZE = 400  # tokens
DEFAULT_CHUNK_OVERLAP = 64  # tokens


def _normalize_tag_name(name):
    """Normalize a tag name for case-insensitive deduplication."""
    if not isinstance(name, str):
        return ""
    return name.strip().lower()


def _upsert_extracted_tags(entity, tag_names):
    """Create or reuse Tag records and attach them to the entity once each."""
    normalized_names = []
    seen = set()
    for raw_name in tag_names or []:
        name = _normalize_tag_name(raw_name)
        if not name or name in seen:
            continue
        seen.add(name)
        normalized_names.append(name)

    if not normalized_names:
        return

    existing_tag_ids = {
        et.tag_id for et in EntityTag.query.filter_by(entity_id=entity.id).all()
    }

    for name in normalized_names:
        tag = Tag.query.filter(Tag.name.ilike(name)).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
            db.session.flush()

        if tag.id in existing_tag_ids:
            continue

        db.session.add(EntityTag(entity_id=entity.id, tag_id=tag.id))
        existing_tag_ids.add(tag.id)

# ─── Job Enqueueing ──────────────────────────────────────────────────────────


def enqueue_classify(entity_id):
    """Enqueue a classify job for the given entity.

    Args:
        entity_id: UUID of the entity to classify.

    Returns:
        The created Job instance.
    """
    eid = str(entity_id)
    job = Job(
        job_type="classify",
        entity_id=eid,
        payload={"entity_id": eid},
    )
    db.session.add(job)
    db.session.flush()
    logger.info("Enqueued classify job for entity %s", eid)
    return job


def enqueue_embed(entity_id):
    """Enqueue an embed job for the given entity.

    Args:
        entity_id: UUID of the entity to embed.

    Returns:
        The created Job instance.
    """
    eid = str(entity_id)
    job = Job(
        job_type="embed",
        entity_id=eid,
        payload={"entity_id": eid},
    )
    db.session.add(job)
    db.session.flush()
    logger.info("Enqueued embed job for entity %s", eid)
    return job


def enqueue_autolink(entity_id):
    """Enqueue an autolink job for the given entity.

    Args:
        entity_id: UUID of the entity to autolink.

    Returns:
        The created Job instance.
    """
    eid = str(entity_id)
    job = Job(
        job_type="autolink",
        entity_id=eid,
        payload={"entity_id": eid},
    )
    db.session.add(job)
    db.session.flush()
    logger.info("Enqueued autolink job for entity %s", eid)
    return job


# ─── Job Handlers (registered with job_worker) ───────────────────────────────


def run_classify(payload):
    """Handle a classify job: extract entities, classify, apply results.

    Flow:
    1. Load entity content
    2. Call extract() with temperature=0
    3. Apply results based on confidence thresholds:
       - >= 0.92: auto-create new entities (projects, areas)
       - 0.70-0.91: store suggestions in ai_meta only
       - < 0.70: store in ai_meta only, no mutations
    4. Update entity.ai_status
    5. Write entity_event('ai_classified')

    Called by job worker, not directly by API.
    """
    from services.extractor import extract, ExtractionResult

    entity_id = payload.get("entity_id")
    if not entity_id:
        raise ValueError("classify job missing entity_id in payload")

    entity = db.session.get(Entity, entity_id)
    if entity is None:
        raise ValueError(f"entity {entity_id} not found")

    # Update status to processing
    entity.ai_status = "processing"
    db.session.commit()

    try:
        # Get existing entities for context matching
        existing_projects = (
            Entity.query.filter_by(type="project", lifecycle="active").all()
        )
        existing_areas = (
            Entity.query.filter_by(type="area", lifecycle="active").all()
        )

        project_names = [p.title for p in existing_projects if p.title]
        area_names = [a.title for a in existing_areas if a.title]

        # Extract with temperature=0 (deterministic)
        extraction = extract(
            content=entity.content or "",
            projects=project_names,
            area_names=area_names,
        )

        # Apply results based on confidence
        ai_meta = entity.ai_meta or {}
        ai_meta["classification"] = {
            "summary": extraction.summary,
            "para_bucket": extraction.para_bucket,
            "confidence": extraction.confidence,
            "reasoning": extraction.reasoning,
            "suggested_project": extraction.suggested_project,
            "suggested_area": extraction.suggested_area,
        }

        if extraction.confidence >= AUTOLINK_CONFIDENCE_THRESHOLD:
            # High confidence: auto-create suggested entities
            if extraction.suggested_project:
                _create_or_link_project(
                    entity, extraction.suggested_project, extraction.confidence
                )
            if extraction.suggested_area:
                _create_or_link_area(
                    entity, extraction.suggested_area, extraction.confidence
                )
        else:
            # Lower confidence: store suggestions only
            ai_meta["suggestions"] = {
                "project": extraction.suggested_project,
                "area": extraction.suggested_area,
                "reason": f"confidence {extraction.confidence:.2f} below threshold {AUTOLINK_CONFIDENCE_THRESHOLD}",
            }

        # Store extracted items in ai_meta
        if extraction.tasks:
            ai_meta["extracted_tasks"] = [t.model_dump() for t in extraction.tasks]
        if extraction.people:
            ai_meta["extracted_people"] = [p.model_dump() for p in extraction.people]
        if extraction.tags:
            ai_meta["extracted_tags"] = extraction.tags[:6]

        entity.ai_meta = ai_meta
        _upsert_extracted_tags(entity, extraction.tags)
        if extraction.para_bucket:
            props = entity.properties or {}
            props["bucket"] = extraction.para_bucket.upper()
            entity.properties = props
        entity.ai_status = "done"

        # Write classification event
        _write_event(
            entity_id=entity.id,
            event_type="ai_classified",
            actor="agent:classify",
            new_value={
                "summary": extraction.summary,
                "para_bucket": extraction.para_bucket,
                "confidence": extraction.confidence,
            },
            confidence=extraction.confidence,
            reason=extraction.reasoning,
        )

        db.session.commit()
        logger.info(
            "Classified entity %s: bucket=%s confidence=%.2f",
            entity.id,
            extraction.para_bucket,
            extraction.confidence,
        )

    except Exception as e:
        entity.ai_status = "failed"
        ai_meta = entity.ai_meta or {}
        ai_meta["classify_error"] = str(e)
        entity.ai_meta = ai_meta
        db.session.commit()

        _write_event(
            entity_id=entity.id,
            event_type="ai_classified",
            actor="agent:classify",
            new_value={"error": str(e)},
            confidence=0.0,
            reason=f"classification failed: {e}",
        )
        db.session.commit()

        logger.error("Classify failed for entity %s: %s", entity.id, e)
        raise  # Re-raise so job worker can handle retry


def run_embed(payload):
    """Handle an embed job: chunk content, generate embeddings, store chunks.

    Flow:
    1. Load entity (title + content)
    2. Chunk text (markdown headings + sliding window)
    3. For each chunk: generate embedding via OpenAI
    4. Upsert entity_chunks (delete old, insert new)

    Called by job worker, not directly by API.
    """
    entity_id = payload.get("entity_id")
    if not entity_id:
        raise ValueError("embed job missing entity_id in payload")

    entity = db.session.get(Entity, entity_id)
    if entity is None:
        raise ValueError(f"entity {entity_id} not found")

    # Update status to processing
    entity.ai_status = "processing"
    db.session.commit()

    try:
        content = entity.content or ""
        if not content.strip():
            # Nothing to embed
            entity.ai_status = "done"
            db.session.commit()
            return

        # Chunk the text
        text_chunks = chunk_text(content)
        if not text_chunks:
            entity.ai_status = "done"
            db.session.commit()
            return

        # Delete old chunks for this entity (upsert pattern)
        EntityChunk.query.filter_by(entity_id=entity.id).delete()
        db.session.flush()

        # Generate embeddings and store chunks
        for i, txt in enumerate(text_chunks):
            embedding = _generate_embedding(txt)

            chunk = EntityChunk(
                entity_id=entity.id,
                chunk_index=i,
                chunk_text=txt,
                embedding=embedding,
                embedding_model=EMBED_MODEL,
            )
            db.session.add(chunk)

        entity.ai_status = "done"
        db.session.commit()

        logger.info(
            "Embedded entity %s: %d chunks",
            entity.id,
            len(text_chunks),
        )

    except Exception as e:
        entity.ai_status = "failed"
        ai_meta = entity.ai_meta or {}
        ai_meta["embed_error"] = str(e)
        entity.ai_meta = ai_meta
        db.session.commit()

        logger.error("Embed failed for entity %s: %s", entity.id, e)
        raise  # Re-raise so job worker can handle retry


def run_autolink(payload):
    """Handle an autolink job: find semantically similar entities, create links.

    Flow:
    1. Load entity embeddings
    2. pgvector ANN search: top 10 nearest entity_chunks
    3. For each result with cosine_similarity >= threshold:
       - If no existing link between entities: create link
       - Write entity_event('link_added')

    Called by job worker, not directly by API.
    """
    from models import EntityLink

    entity_id = payload.get("entity_id")
    if not entity_id:
        raise ValueError("autolink job missing entity_id in payload")

    entity = db.session.get(Entity, entity_id)
    if entity is None:
        raise ValueError(f"entity {entity_id} not found")

    entity.ai_status = "processing"
    db.session.commit()

    try:
        # Get chunks for this entity
        chunks = EntityChunk.query.filter_by(entity_id=entity.id).all()
        if not chunks:
            # No embeddings to compare against
            entity.ai_status = "done"
            db.session.commit()
            return

        # Use the first chunk's embedding for similarity search
        primary_embedding = chunks[0].embedding
        if not primary_embedding:
            entity.ai_status = "done"
            db.session.commit()
            return

        # Find similar entities via pgvector cosine similarity
        # This uses the pgvector <-> operator for cosine distance
        # similarity = 1 - distance
        similar_results = _find_similar_entities(primary_embedding, entity_id)

        links_created = 0
        for similar_entity_id, similarity in similar_results:
            if similarity < CLASSIFY_CONFIDENCE_THRESHOLD:
                continue

            # Check if link already exists
            existing = EntityLink.query.filter(
                (
                    (EntityLink.src_id == entity.id)
                    & (EntityLink.dst_id == similar_entity_id)
                    & (EntityLink.link_type == "related")
                )
                | (
                    (EntityLink.src_id == similar_entity_id)
                    & (EntityLink.dst_id == entity.id)
                    & (EntityLink.link_type == "related")
                )
            ).first()

            if existing:
                continue

            # Create the link
            link = EntityLink(
                src_id=entity.id,
                dst_id=similar_entity_id,
                link_type="related",
                inverse="related",
                source="embedding",
                confidence=similarity,
            )
            db.session.add(link)
            links_created += 1

            # Write events for both entities
            _write_event(
                entity_id=entity.id,
                event_type="link_added",
                actor="agent:autolink",
                new_value={
                    "dst_entity_id": similar_entity_id,
                    "link_type": "related",
                    "source": "embedding",
                    "confidence": similarity,
                },
                confidence=similarity,
            )
            _write_event(
                entity_id=similar_entity_id,
                event_type="link_added",
                actor="agent:autolink",
                new_value={
                    "src_entity_id": entity.id,
                    "link_type": "related",
                    "source": "embedding",
                    "confidence": similarity,
                },
                confidence=similarity,
            )

        entity.ai_status = "done"
        db.session.commit()

        logger.info(
            "Autolinked entity %s: %d new links",
            entity.id,
            links_created,
        )

    except Exception as e:
        entity.ai_status = "failed"
        ai_meta = entity.ai_meta or {}
        ai_meta["autolink_error"] = str(e)
        entity.ai_meta = ai_meta
        db.session.commit()

        logger.error("Autolink failed for entity %s: %s", entity.id, e)
        raise  # Re-raise so job worker can handle retry


# ─── Internal Helpers ────────────────────────────────────────────────────────


def _generate_embedding(text):
    """Generate embedding vector for text using OpenAI API.

    Args:
        text: Text to embed.

    Returns:
        List of floats (embedding vector of EMBED_DIMS dimensions).
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set — returning zero vector")
        return [0.0] * EMBED_DIMS

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            model=EMBED_MODEL,
            input=text,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error("Embedding generation failed: %s", e)
        raise


def _find_similar_entities(embedding, exclude_entity_id, limit=10):
    """Find similar entities via pgvector cosine similarity.

    Args:
        embedding: The query embedding vector.
        exclude_entity_id: Don't return chunks from this entity.
        limit: Maximum number of results.

    Returns:
        List of (entity_id, similarity_score) tuples.
    """
    from sqlalchemy import text

    # Format embedding as pgvector array string
    embedding_str = f"[{','.join(str(v) for v in embedding)}]"

    # Use pgvector cosine distance operator (<->)
    # similarity = 1 - cosine_distance
    results = db.session.execute(
        text("""
            SELECT DISTINCT ec.entity_id,
                   1 - (ec.embedding <-> :embedding)::float AS similarity
            FROM entity_chunks ec
            WHERE ec.entity_id != :exclude_id
              AND ec.embedding IS NOT NULL
            ORDER BY ec.embedding <-> :embedding
            LIMIT :limit
        """),
        {
            "embedding": embedding_str,
            "exclude_id": exclude_entity_id,
            "limit": limit,
        },
    )

    return [(row.entity_id, row.similarity) for row in results]


def _create_or_link_project(entity, project_name, confidence):
    """Create a new project entity or link to existing one.

    Args:
        entity: The source entity.
        project_name: Name of the project.
        confidence: Confidence score of the classification.
    """
    from models import EntityLink

    # Check for existing project with same name
    existing = Entity.query.filter_by(
        type="project", title=project_name, lifecycle="active"
    ).first()

    if existing:
        # Link to existing project
        link = EntityLink(
            src_id=entity.id,
            dst_id=existing.id,
            link_type="related",
            inverse="related",
            source="ai",
            confidence=confidence,
        )
        db.session.add(link)
        _write_event(
            entity_id=entity.id,
            event_type="ai_extracted",
            actor="agent:classify",
            new_value={
                "type": "project",
                "title": project_name,
                "action": "linked_existing",
                "entity_id": str(existing.id),
            },
            confidence=confidence,
        )
    else:
        # Create new project
        project = Entity(
            type="project",
            title=project_name,
            content=f"Auto-created during classification of entity {entity.id}",
            properties={},
            ai_meta={"source": "ai_classify", "parent_entity_id": str(entity.id)},
            ai_status="done",
        )
        db.session.add(project)
        db.session.flush()

        # Link entity to new project
        link = EntityLink(
            src_id=entity.id,
            dst_id=project.id,
            link_type="related",
            inverse="related",
            source="ai",
            confidence=confidence,
        )
        db.session.add(link)

        _write_event(
            entity_id=entity.id,
            event_type="ai_extracted",
            actor="agent:classify",
            new_value={
                "type": "project",
                "title": project_name,
                "action": "created_new",
                "entity_id": str(project.id),
            },
            confidence=confidence,
        )


def _create_or_link_area(entity, area_name, confidence):
    """Create a new area entity or link to existing one.

    Args:
        entity: The source entity.
        area_name: Name of the area.
        confidence: Confidence score of the classification.
    """
    from models import EntityLink

    existing = Entity.query.filter_by(
        type="area", title=area_name, lifecycle="active"
    ).first()

    if existing:
        link = EntityLink(
            src_id=entity.id,
            dst_id=existing.id,
            link_type="related",
            inverse="related",
            source="ai",
            confidence=confidence,
        )
        db.session.add(link)
    else:
        area = Entity(
            type="area",
            title=area_name,
            content=f"Auto-created during classification of entity {entity.id}",
            properties={},
            ai_meta={"source": "ai_classify", "parent_entity_id": str(entity.id)},
            ai_status="done",
        )
        db.session.add(area)
        db.session.flush()

        link = EntityLink(
            src_id=entity.id,
            dst_id=area.id,
            link_type="related",
            inverse="related",
            source="ai",
            confidence=confidence,
        )
        db.session.add(link)


# ─── Handler Registration ────────────────────────────────────────────────────

def register_handlers():
    """Register all AI pipeline handlers with the job worker.

    Call this during app initialization to wire up the pipeline.
    """
    from services.job_worker import register_handler

    register_handler("classify")(run_classify)
    register_handler("embed")(run_embed)
    register_handler("autolink")(run_autolink)

    logger.info("AI pipeline handlers registered")
