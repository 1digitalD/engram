"""
Embedding service: generate, store, and query embeddings via sqlite-vec.
Uses OpenAI text-embedding-3-small at 1536 dims.
Chunks notes using Markdown-heading splits + 400-token sliding window.
"""
from __future__ import annotations

import os
import json
import logging
import re

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536
CHUNK_SIZE = 400       # tokens (approx: 1 token ≈ 4 chars)
CHUNK_OVERLAP = 64     # tokens overlap between windows

_openai_client = None


def _get_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _openai_client = OpenAI(api_key=key)
    return _openai_client


# ── Chunking ─────────────────────────────────────────────────────────────────

def _approx_tokens(text: str) -> int:
    return len(text) // 4


def _split_chunks(text: str, note_id: str) -> list[tuple[int, str]]:
    """
    Split text into chunks with breadcrumb prefix.
    Returns list of (chunk_index, chunk_text).
    Strategy: split on Markdown headings first, then sliding window.
    """
    # Split on Markdown headings
    heading_pattern = re.compile(r'^#{1,3}\s+.+$', re.MULTILINE)
    sections = heading_pattern.split(text)
    headings = heading_pattern.findall(text)

    # Build labeled sections
    labeled = []
    for i, section in enumerate(sections):
        heading = headings[i - 1] if i > 0 else ""
        labeled.append((heading, section.strip()))

    chunks = []
    idx = 0

    for heading, section in labeled:
        if not section:
            continue
        prefix = f"{heading}\n" if heading else ""
        full = prefix + section

        if _approx_tokens(full) <= CHUNK_SIZE:
            chunks.append((idx, full))
            idx += 1
        else:
            # Sliding window within large section
            words = full.split()
            step = CHUNK_SIZE * 4 - CHUNK_OVERLAP * 4  # chars approx
            start = 0
            text_len = len(full)
            while start < text_len:
                end = start + CHUNK_SIZE * 4
                chunk = full[start:end]
                chunks.append((idx, chunk))
                idx += 1
                if end >= text_len:
                    break
                start += step

    if not chunks:
        chunks = [(0, text[:CHUNK_SIZE * 4])]

    return chunks


# ── OpenAI embedding call ─────────────────────────────────────────────────────

def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API. Returns list of embedding vectors."""
    client = _get_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
        dimensions=EMBEDDING_DIMS,
    )
    return [item.embedding for item in response.data]


# ── Storage ──────────────────────────────────────────────────────────────────

def embed_note(note_id: str, text: str):
    """
    Generate embeddings for a note and store them in sqlite-vec.
    Replaces any existing chunks for this note.
    """
    from extensions import db
    from models import NoteChunk

    try:
        from flask import current_app

        if current_app.config.get("TESTING"):
            return
    except RuntimeError:
        pass

    if not os.getenv("OPENAI_API_KEY"):
        return

    try:
        # Remove old chunks
        NoteChunk.query.filter_by(note_id=note_id).delete()
        db.session.execute(
            db.text("DELETE FROM vec_chunks WHERE chunk_id LIKE :prefix"),
            {"prefix": f"{note_id}_%"}
        )

        chunks = _split_chunks(text, note_id)
        if not chunks:
            return

        chunk_texts = [c[1] for c in chunks]
        vectors = _embed_texts(chunk_texts)

        for (chunk_idx, chunk_text), vector in zip(chunks, vectors):
            chunk_id = f"{note_id}_{chunk_idx}"

            # Store metadata
            nc = NoteChunk(
                id=chunk_id,
                note_id=note_id,
                chunk_index=chunk_idx,
                chunk_text=chunk_text,
                embedding_model=EMBEDDING_MODEL,
            )
            db.session.add(nc)

            # Store vector in sqlite-vec
            try:
                db.session.execute(
                    db.text("INSERT OR REPLACE INTO vec_chunks(chunk_id, embedding) VALUES (:id, :vec)"),
                    {"id": chunk_id, "vec": json.dumps(vector)}
                )
            except Exception as vec_err:
                logger.debug(f"sqlite-vec insert skipped: {vec_err}")

        db.session.commit()
        logger.info(f"Embedded note {note_id}: {len(chunks)} chunks")

    except Exception as e:
        logger.error(f"embed_note failed for {note_id}: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass


def embed_query(query: str) -> list[float] | None:
    """Embed a search query string. Returns vector or None."""
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        vectors = _embed_texts([query])
        return vectors[0] if vectors else None
    except Exception as e:
        logger.error(f"embed_query failed: {e}")
        return None


# ── Similarity search ─────────────────────────────────────────────────────────

def semantic_search(query: str, limit: int = 20) -> list[dict]:
    """
    Search notes by semantic similarity to query.
    Returns list of note dicts ordered by similarity.
    """
    from extensions import db
    from models import Note, NoteChunk

    vector = embed_query(query)
    if vector is None:
        return []

    try:
        rows = db.session.execute(
            db.text("""
                SELECT vc.chunk_id, vc.distance
                FROM vec_chunks vc
                WHERE vc.embedding MATCH :vec AND k = :k
                ORDER BY vc.distance
            """),
            {"vec": json.dumps(vector), "k": limit * 3}
        ).fetchall()

        # De-duplicate by note_id, keep best (lowest) distance
        seen = {}
        for chunk_id, distance in rows:
            note_id = chunk_id.rsplit("_", 1)[0]
            if note_id not in seen or distance < seen[note_id]:
                seen[note_id] = distance

        # Sort by distance, take top limit
        ranked = sorted(seen.items(), key=lambda x: x[1])[:limit]

        results = []
        for note_id, distance in ranked:
            note = db.session.get(Note, note_id)
            if note and not note.is_archived:
                d = note.to_dict()
                d["_score"] = round(1.0 - distance, 4)
                results.append(d)

        return results

    except Exception as e:
        logger.debug(f"semantic_search failed (sqlite-vec may not be active): {e}")
        return []


def find_related_note_ids(note_id: str, limit: int = 5, min_similarity: float = 0.80) -> list[tuple[str, float]]:
    """
    Find notes similar to a given note using vector search.
    Returns list of (other_note_id, similarity_score) tuples.
    """
    from extensions import db
    from models import NoteChunk

    # Get any chunk embedding for this note to use as query
    chunk = NoteChunk.query.filter_by(note_id=note_id).first()
    if not chunk:
        return []

    try:
        rows = db.session.execute(
            db.text("""
                SELECT vc.chunk_id, vc.distance
                FROM vec_chunks vc
                WHERE vc.embedding MATCH (
                    SELECT embedding FROM vec_chunks WHERE chunk_id = :cid
                ) AND k = :k
                ORDER BY vc.distance
            """),
            {"cid": chunk.id, "k": (limit + 1) * 3}
        ).fetchall()

        seen = {}
        for chunk_id, distance in rows:
            other_note_id = chunk_id.rsplit("_", 1)[0]
            if other_note_id == note_id:
                continue
            similarity = 1.0 - distance
            if similarity >= min_similarity:
                if other_note_id not in seen or similarity > seen[other_note_id]:
                    seen[other_note_id] = similarity

        return sorted(seen.items(), key=lambda x: -x[1])[:limit]

    except Exception as e:
        logger.debug(f"find_related_note_ids failed: {e}")
        return []


def backfill_embeddings():
    """Embed all notes that don't have chunks yet. For CLI use."""
    from extensions import db
    from models import Note, NoteChunk

    notes_without_chunks = (
        Note.query
        .filter(~Note.id.in_(
            db.session.query(NoteChunk.note_id).distinct()
        ))
        .all()
    )

    logger.info(f"Backfilling embeddings for {len(notes_without_chunks)} notes...")
    for note in notes_without_chunks:
        try:
            embed_note(note.id, note.raw_text)
        except Exception as e:
            logger.error(f"Failed to embed note {note.id}: {e}")

    logger.info("Backfill complete.")
