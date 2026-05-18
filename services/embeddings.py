"""
Embedding service: generate, store, and query embeddings via Postgres pgvector.
Uses OpenAI text-embedding-3-small at 1536 dims.
Chunks entity content using sliding window with configurable overlap.
"""
from __future__ import annotations

import os
import logging

logger = logging.getLogger(__name__)

from utils import get_openai_client

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536
CHUNK_SIZE = 400       # tokens (approx: 1 token ≈ 4 chars)
CHUNK_OVERLAP = 64     # tokens overlap between windows


# ── Chunking ─────────────────────────────────────────────────────────────────

def chunk_text(text, chunk_size=None, overlap=None):
    """Split text into overlapping chunks for embedding.

    Uses a sliding window approach at word boundaries.

    Returns list of text chunks (strings). Empty list if text is empty/None.
    """
    if not text or not text.strip():
        return []

    chunk_size = chunk_size or CHUNK_SIZE
    overlap = overlap or CHUNK_OVERLAP

    chunk_chars = chunk_size * 4
    overlap_chars = overlap * 4

    if len(text) <= chunk_chars:
        return [text.strip()]

    words = text.split()
    if not words:
        return []

    chunks = []
    current_chunk = []
    current_length = 0

    for word in words:
        word_len = len(word) + 1
        if current_length + word_len > chunk_chars and current_chunk:
            chunks.append(" ".join(current_chunk))
            overlap_words = []
            overlap_len = 0
            for w in reversed(current_chunk):
                if overlap_len + len(w) + 1 > overlap_chars:
                    break
                overlap_words.append(w)
                overlap_len += len(w) + 1
            current_chunk = list(reversed(overlap_words))
            current_length = overlap_len

        current_chunk.append(word)
        current_length += word_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


# ── OpenAI embedding call ─────────────────────────────────────────────────────

def _embed_texts(texts):
    """Call OpenAI embeddings API. Returns list of embedding vectors."""
    client = get_openai_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
        dimensions=EMBEDDING_DIMS,
    )
    return [item.embedding for item in response.data]


# ── Storage ──────────────────────────────────────────────────────────────────

def embed_entity(entity_id, text):
    """
    Generate embeddings for an entity and store them in entity_chunks.
    Replaces any existing chunks for this entity.
    """
    from extensions import db
    from models import EntityChunk

    try:
        from flask import current_app
        if current_app.config.get("TESTING"):
            return
    except RuntimeError:
        pass

    if not os.getenv("OPENAI_API_KEY"):
        return

    if not text or not text.strip():
        return

    try:
        EntityChunk.query.filter_by(entity_id=entity_id).delete()
        db.session.flush()

        text_chunks = chunk_text(text)
        if not text_chunks:
            return

        vectors = _embed_texts(text_chunks)

        for i, (txt, vector) in enumerate(zip(text_chunks, vectors)):
            chunk = EntityChunk(
                entity_id=entity_id,
                chunk_index=i,
                chunk_text=txt,
                embedding=vector,
                embedding_model=EMBEDDING_MODEL,
            )
            db.session.add(chunk)

        db.session.commit()
        logger.info("Embedded entity %s: %d chunks", entity_id, len(text_chunks))

    except Exception as e:
        logger.error("embed_entity failed for %s: %s", entity_id, e)
        try:
            db.session.rollback()
        except Exception as rb_e:
            logger.warning("Rollback failed after embed error: %s", rb_e)


def embed_query(query):
    """Embed a search query string. Returns vector or None."""
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        vectors = _embed_texts([query])
        return vectors[0] if vectors else None
    except Exception as e:
        logger.error("embed_query failed: %s", e)
        return None

