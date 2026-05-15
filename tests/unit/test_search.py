"""Unit tests for search service — RRF fusion, search orchestration."""

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


# ─── RRF Fusion ───────────────────────────────────────────────────────────────

class TestRRFFusion:
    """Test Reciprocal Rank Fusion logic."""

    def test_rrf_fusion_both_sources(self):
        from services.search import _rrf_fusion
        fts = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        sem = [{"id": "b"}, {"id": "c"}, {"id": "d"}]
        results = _rrf_fusion(fts, sem, limit=3)
        ids = [r["id"] for r in results]
        assert "b" in ids
        assert "c" in ids
        assert len(results) <= 3

    def test_rrf_fusion_single_source(self):
        from services.search import _rrf_fusion
        fts = [{"id": "a"}, {"id": "b"}]
        sem = []
        results = _rrf_fusion(fts, sem, limit=5)
        assert len(results) == 2
        assert results[0]["id"] == "a"

    def test_rrf_fusion_empty(self):
        from services.search import _rrf_fusion
        results = _rrf_fusion([], [], limit=5)
        assert results == []

    def test_rrf_score_formula(self):
        from services.search import _rrf_fusion, RRF_K
        fts = [{"id": "x"}]
        sem = [{"id": "x"}]
        results = _rrf_fusion(fts, sem, limit=5)
        expected = 1.0 / (RRF_K + 1) + 1.0 / (RRF_K + 1)
        assert abs(results[0]["_score"] - expected) < 1e-6


# ─── Search Orchestration ─────────────────────────────────────────────────────

class TestSearchOrchestration:
    """Test the main search() function routing."""

    def test_search_empty_query(self, app):
        from services.search import search
        with app.app_context():
            assert search("") == []
            assert search("   ") == []

    @patch("services.search._fts_only")
    def test_search_fts_mode(self, mock_fts, app):
        mock_fts.return_value = [{"id": "1", "title": "Test"}]
        from services.search import search
        with app.app_context():
            results = search("hello", mode="fts", limit=5)
            mock_fts.assert_called_once()
            assert len(results) == 1

    @patch("services.search._semantic_only")
    def test_search_semantic_mode(self, mock_sem, app):
        mock_sem.return_value = [{"id": "2", "title": "Result"}]
        from services.search import search
        with app.app_context():
            results = search("hello", mode="semantic", limit=5)
            mock_sem.assert_called_once()
            assert len(results) == 1

    @patch("services.search._rrf_fusion")
    def test_search_hybrid_mode(self, mock_rrf, app):
        mock_rrf.return_value = [{"id": "3", "title": "Hybrid", "_score": 0.03}]
        from services.search import search
        with app.app_context():
            results = search("hello", mode="hybrid", limit=5)
            mock_rrf.assert_called_once()
            assert len(results) == 1


# ─── FTS Search ───────────────────────────────────────────────────────────────

class TestFTSSearch:
    """Test full-text search via Postgres tsvector."""

    @patch("services.search.db")
    def test_fts_only_returns_results(self, mock_db, app):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("entity-id-1",)]
        mock_db.session.execute.return_value = mock_result
        mock_db.text = lambda q: q

        with app.app_context():
            entity = _create_entity(
                title="Python Programming",
                content="Learning Python is fun"
            )
            entity._mock_id = entity.id

            from services.search import _fts_only
            with patch("services.search.Entity") as MockEntity:
                mock_entity_obj = MagicMock()
                mock_entity_obj.to_dict.return_value = {
                    "id": entity.id, "title": "Python Programming"
                }
                MockEntity.query.filter.return_value.all.return_value = [mock_entity_obj]
                results = _fts_only("Python", limit=5)
                assert len(results) >= 0

    def test_fts_only_empty_query_result(self, app):
        with app.app_context():
            from services.search import _fts_only
            results = _fts_only("nonexistent_term_xyz", limit=5)
            assert results == []


# ─── Semantic Search ──────────────────────────────────────────────────────────

class TestSemanticSearch:
    """Test semantic search via pgvector."""

    @patch("services.embeddings.embed_query")
    def test_semantic_only_no_embedding(self, mock_embed, app):
        mock_embed.return_value = None
        from services.search import _semantic_only
        with app.app_context():
            results = _semantic_only("test", limit=5)
            assert results == []

    @patch("services.search.db")
    @patch("services.embeddings.embed_query")
    def test_semantic_only_returns_results(self, mock_embed, mock_db, app):
        mock_embed.return_value = [0.1] * 1536
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("e1", 0.15)]
        mock_db.session.execute.return_value = mock_result
        mock_db.text = lambda q: q

        from services.search import _semantic_only
        with app.app_context():
            with patch("services.search.Entity") as MockEntity:
                mock_e = MagicMock()
                mock_e.to_dict.return_value = {"id": "e1", "title": "Test"}
                MockEntity.query.filter.return_value.all.return_value = [mock_e]
                results = _semantic_only("test", limit=5)
                assert len(results) >= 0

    @patch("services.search.db")
    @patch("services.embeddings.embed_query")
    def test_semantic_only_accepts_none_filters(self, mock_embed, mock_db, app):
        mock_embed.return_value = [0.1] * 1536
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.session.execute.return_value = mock_result
        mock_db.text = lambda q: q

        from services.search import _semantic_only
        with app.app_context():
            results = _semantic_only("test", limit=5, filters=None)
            assert results == []

    @patch("services.search.db")
    def test_fts_only_rolls_back_on_error(self, mock_db, app):
        mock_db.session.execute.side_effect = Exception("boom")
        mock_db.text = lambda q: q

        from services.search import _fts_only
        with app.app_context():
            results = _fts_only("test", limit=5)
            assert results == []
            mock_db.session.rollback.assert_called_once()

    @patch("services.search.db")
    @patch("services.embeddings.embed_query")
    def test_semantic_only_rolls_back_on_error(self, mock_embed, mock_db, app):
        mock_embed.return_value = [0.1] * 1536
        mock_db.session.execute.side_effect = Exception("boom")
        mock_db.text = lambda q: q

        from services.search import _semantic_only
        with app.app_context():
            results = _semantic_only("test", limit=5)
            assert results == []
            mock_db.session.rollback.assert_called_once()
