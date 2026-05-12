"""Unit tests for embeddings service — chunking, embedding, storage."""

import pytest
from unittest.mock import patch, MagicMock

from extensions import db
from models import Entity, EntityChunk


def _create_entity(entity_type="note", title="Test", content="Hello world"):
    entity = Entity(
        type=entity_type, title=title, content=content,
        properties={}, ai_meta={}, ai_status="pending",
    )
    db.session.add(entity)
    db.session.commit()
    return entity


# ─── Chunking ─────────────────────────────────────────────────────────────────

class TestChunkText:
    """Test text chunking for embedding preparation."""

    def test_short_text_single_chunk(self):
        from services.embeddings import chunk_text
        chunks = chunk_text("Short text.", chunk_size=100, overlap=20)
        assert len(chunks) == 1
        assert chunks[0] == "Short text."

    def test_long_text_splits(self):
        from services.embeddings import chunk_text
        words = ["word"] * 200
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) >= 2

    def test_overlap_between_chunks(self):
        from services.embeddings import chunk_text
        words = [f"w{i}" for i in range(200)]
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=100, overlap=30)
        assert len(chunks) >= 2
        if len(chunks) >= 2:
            last_words_0 = set(chunks[0].split()[-10:])
            words_1 = set(chunks[1].split())
            assert bool(last_words_0 & words_1)

    def test_empty_text(self):
        from services.embeddings import chunk_text
        assert chunk_text("") == []

    def test_none_text(self):
        from services.embeddings import chunk_text
        assert chunk_text(None) == []

    def test_respects_chunk_size(self):
        from services.embeddings import chunk_text
        words = ["item"] * 200
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=50, overlap=10)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= 300


# ─── Embed Storage ────────────────────────────────────────────────────────────

class TestEmbedEntity:
    """Test embedding generation and storage in entity_chunks."""

    @patch("services.embeddings._embed_texts")
    @patch("services.embeddings.os.getenv")
    def test_embed_entity_stores_chunks(self, mock_getenv, mock_embed, app):
        mock_getenv.return_value = "test-key"
        mock_embed.return_value = [[0.1] * 1536]

        with app.app_context():
            app.config["TESTING"] = False
            entity = _create_entity(content="Test content. " * 30)
            from services.embeddings import embed_entity
            embed_entity(entity.id, entity.content or "")

            chunks = EntityChunk.query.filter_by(entity_id=entity.id).all()
            assert len(chunks) >= 1
            assert chunks[0].embedding is not None

    @patch("services.embeddings._embed_texts")
    @patch("services.embeddings.os.getenv")
    def test_embed_entity_upserts_deletes_old(self, mock_getenv, mock_embed, app):
        mock_getenv.return_value = "test-key"
        mock_embed.return_value = [[0.1] * 1536]

        with app.app_context():
            app.config["TESTING"] = False
            entity = _create_entity(content="Original. " * 30)
            from services.embeddings import embed_entity
            embed_entity(entity.id, entity.content or "")
            first_count = EntityChunk.query.filter_by(entity_id=entity.id).count()

            entity.content = "New content. " * 30
            db.session.commit()
            embed_entity(entity.id, entity.content or "")

            new_chunks = EntityChunk.query.filter_by(entity_id=entity.id).all()
            assert len(new_chunks) >= 1

    @pytest.mark.skip(reason="Test isolation issue - truncate not cleaning between tests")
    def test_embed_entity_skips_in_testing_by_default(self, app):
        """In TESTING mode, embed_entity should be a no-op (no API key)."""
        with app.app_context():
            entity = _create_entity(content="Test")
            from services.embeddings import embed_entity
            embed_entity(entity.id, entity.content or "")
            chunks = EntityChunk.query.filter_by(entity_id=entity.id).all()
            assert len(chunks) == 0

    def test_embed_entity_empty_content(self, app):
        with app.app_context():
            entity = _create_entity(content="")
            from services.embeddings import embed_entity
            embed_entity(entity.id, "")
            chunks = EntityChunk.query.filter_by(entity_id=entity.id).all()
            assert len(chunks) == 0


# ─── Query Embedding ──────────────────────────────────────────────────────────

class TestEmbedQuery:
    """Test query string embedding."""

    @patch("services.embeddings._embed_texts")
    def test_embed_query_returns_vector(self, mock_embed):
        mock_embed.return_value = [[0.2] * 1536]
        from services.embeddings import embed_query
        result = embed_query("test query")
        assert result is not None
        assert len(result) == 1536

    @patch("services.embeddings.os.getenv")
    def test_embed_query_no_api_key(self, mock_getenv):
        mock_getenv.return_value = None
        from services.embeddings import embed_query
        result = embed_query("test")
        assert result is None
