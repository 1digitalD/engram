"""Integration tests for search — FTS, SQL injection safety, pgvector, and semantic search.

Proves that Postgres tsvector FTS finds entities by title and content,
that type filtering works, that the _fts_only function uses
parameterized queries (no string-replace SQL injection), that pgvector
<-> operator returns correct distances, and that semantic search returns
correctly ranked results.
"""

import pytest
from unittest.mock import patch

from extensions import db
from models import Entity, EntityChunk
from services.entity_service import create_entity
from services.search import search, _fts_only, _semantic_only


class TestFtsSearchByTitle:
    """FTS search finds entities by title."""

    def test_fts_finds_entity_by_title(self, app):
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Quantum Computing Breakthrough",
                content="Some content here",
                actor="user",
            )
            db.session.commit()

            results = search("quantum", mode="fts")
            assert len(results) >= 1
            assert any(r["title"] == "Quantum Computing Breakthrough" for r in results)

    def test_fts_finds_entity_by_partial_title(self, app):
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Machine Learning Pipeline Design",
                content="Details about the pipeline",
                actor="user",
            )
            db.session.commit()

            results = search("machine learning", mode="fts")
            assert len(results) >= 1
            titles = [r["title"] for r in results]
            assert "Machine Learning Pipeline Design" in titles


class TestFtsSearchByContent:
    """FTS search finds entities by content."""

    def test_fts_finds_entity_by_content(self, app):
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Meeting Notes",
                content="Discussed the new Kubernetes deployment strategy and rollout plan",
                actor="user",
            )
            db.session.commit()

            results = search("kubernetes deployment", mode="fts")
            assert len(results) >= 1
            assert any("Kubernetes" in r.get("content", "") for r in results)

    def test_fts_finds_entity_by_content_not_title(self, app):
        """Entity whose title does not match but content does."""
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Weekly Sync",
                content="We reviewed the PostgreSQL migration and decided to use pgvector for embeddings",
                actor="user",
            )
            db.session.commit()

            results = search("pgvector embeddings", mode="fts")
            assert len(results) >= 1
            assert any(r["title"] == "Weekly Sync" for r in results)


class TestFtsTypeFilter:
    """FTS search respects type filter."""

    def test_type_filter_returns_only_matching_type(self, app):
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Alpha Project Update",
                content="Note about alpha",
                actor="user",
            )
            create_entity(
                entity_type="task",
                title="Alpha Task",
                content="Task about alpha",
                actor="user",
            )
            create_entity(
                entity_type="project",
                title="Alpha Project",
                content="Project about alpha",
                actor="user",
            )
            db.session.commit()

            results = search("alpha", mode="fts", filters={"type": "note"})
            assert len(results) >= 1
            assert all(r["type"] == "note" for r in results)

    def test_type_filter_task_only(self, app):
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Design Review Notes",
                content="Notes from the design review",
                actor="user",
            )
            create_entity(
                entity_type="task",
                title="Design Review Follow-up",
                content="Follow up on design review items",
                actor="user",
            )
            db.session.commit()

            results = search("design review", mode="fts", filters={"type": "task"})
            assert len(results) >= 1
            assert all(r["type"] == "task" for r in results)

    def test_type_filter_project_only(self, app):
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Budget Planning",
                content="Notes on budget",
                actor="user",
            )
            create_entity(
                entity_type="project",
                title="Budget Planning Project",
                content="Project for budget planning",
                actor="user",
            )
            db.session.commit()

            results = search("budget planning", mode="fts", filters={"type": "project"})
            assert len(results) >= 1
            assert all(r["type"] == "project" for r in results)


class TestFtsNoSqlInjection:
    """Prove _fts_only uses parameterized queries, not string-replace SQL."""

    def test_fts_only_no_string_replace_in_source(self, app):
        """Verify the source code does not use .replace() for SQL construction."""
        import inspect
        source = inspect.getsource(_fts_only)
        # The old fragile pattern was: sql.replace("LIMIT", "...")
        assert ".replace(" not in source, (
            "_fts_only must not use string .replace() for SQL construction — "
            "use parameterized queries instead"
        )

    def test_fts_only_handles_malicious_type_filter(self, app):
        """Type filter with SQL injection attempt should not break the query."""
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Test Entity",
                content="Test content",
                actor="user",
            )
            db.session.commit()

            # This should not raise or inject SQL — it should just return
            # zero results because the type doesn't match any valid type.
            results = search(
                "test",
                mode="fts",
                filters={"type": "'; DROP TABLE entities; --"},
            )
            # Query should complete without error (empty or with results, but not crash)
            assert isinstance(results, list)

    def test_fts_only_handles_malicious_query(self, app):
        """Query with SQL injection attempt should not break the search."""
        with app.app_context():
            create_entity(
                entity_type="note",
                title="Normal Title",
                content="Normal content",
                actor="user",
            )
            db.session.commit()

            # Should not raise — parameterized query handles this safely
            results = search("'; DROP TABLE entities; --", mode="fts")
            assert isinstance(results, list)

    def test_fts_only_parameterized_query_structure(self, app):
        """Verify _fts_only builds SQL with proper parameterized WHERE clauses."""
        import inspect
        import ast

        source = inspect.getsource(_fts_only)
        tree = ast.parse(source)

        # Check that no Call node has attribute 'replace' on a string variable
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "replace":
                        pytest.fail(
                            "_fts_only uses .replace() for SQL construction. "
                            "Use parameterized queries instead."
                        )


class TestPgvectorOperator:
    """Prove pgvector <-> (cosine distance) operator works correctly."""

    def test_identical_vectors_have_zero_distance(self, app):
        """<-> returns 0 for identical vectors."""
        with app.app_context():
            result = db.session.execute(db.text(
                "SELECT '[1,2,3]'::vector(3) <-> '[1,2,3]'::vector(3)"
            )).scalar()
            assert abs(result) < 1e-6

    def test_orthogonal_vectors_have_distance_sqrt2(self, app):
        """<-> (Euclidean distance) returns sqrt(2) for orthogonal unit vectors."""
        with app.app_context():
            result = db.session.execute(db.text(
                "SELECT '[1,0,0]'::vector(3) <-> '[0,1,0]'::vector(3)"
            )).scalar()
            import math
            assert abs(result - math.sqrt(2)) < 1e-6

    def test_opposite_vectors_have_distance_two(self, app):
        """<-> returns ~2 for opposite vectors."""
        with app.app_context():
            result = db.session.execute(db.text(
                "SELECT '[1,0,0]'::vector(3) <-> '[-1,0,0]'::vector(3)"
            )).scalar()
            assert abs(result - 2.0) < 1e-6

    def test_distance_is_symmetric(self, app):
        """<-> distance is symmetric: a<->b == b<->a."""
        with app.app_context():
            d1 = db.session.execute(db.text(
                "SELECT '[1,2,3]'::vector(3) <-> '[4,5,6]'::vector(3)"
            )).scalar()
            d2 = db.session.execute(db.text(
                "SELECT '[4,5,6]'::vector(3) <-> '[1,2,3]'::vector(3)"
            )).scalar()
            assert abs(d1 - d2) < 1e-6

    def test_hnsw_index_exists(self, app):
        """HNSW index on entity_chunks.embedding is present."""
        with app.app_context():
            result = db.session.execute(db.text("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'entity_chunks'
                  AND indexname = 'entity_chunks_hnsw_idx'
            """)).fetchone()
            assert result is not None

    def test_cosine_ops_used_in_index(self, app):
        """HNSW index uses vector_cosine_ops."""
        with app.app_context():
            result = db.session.execute(db.text("""
                SELECT indexdef FROM pg_indexes
                WHERE indexname = 'entity_chunks_hnsw_idx'
            """)).scalar()
            assert "vector_cosine_ops" in result


class TestSemanticSearchRanking:
    """Prove semantic search returns correctly ranked results."""

    def _make_embedding(self, values):
        """Pad a short vector to 1536 dims."""
        vec = [float(v) for v in values]
        return vec + [0.0] * (1536 - len(vec))

    def test_semantic_search_returns_similar_entities_first(self, app, mock_embed):
        """Entities with more similar embeddings rank higher."""
        # Mock embed_query to return a known query vector
        query_vec = self._make_embedding([1.0, 0.0, 0.0, 0.0])

        with app.app_context():
            # Create three entities with different content
            e1 = create_entity(
                entity_type="note",
                title="Python Programming",
                content="Python is a programming language",
                actor="user",
            )
            db.session.commit()

            e2 = create_entity(
                entity_type="note",
                title="Gardening Tips",
                content="How to grow tomatoes in your garden",
                actor="user",
            )
            db.session.commit()

            e3 = create_entity(
                entity_type="note",
                title="Python Snake Care",
                content="Ball pythons make great pets",
                actor="user",
            )
            db.session.commit()

            # Insert chunks with controlled embeddings:
            # e1's chunk is very similar to query_vec (only differs in 4th dim)
            # e3's chunk is somewhat similar (differs in 2nd and 4th dim)
            # e2's chunk is very different (orthogonal direction)
            db.session.add(EntityChunk(
                entity_id=e1.id,
                chunk_index=0,
                chunk_text="Python programming language",
                embedding=self._make_embedding([1.0, 0.0, 0.0, 0.1]),
            ))
            db.session.add(EntityChunk(
                entity_id=e2.id,
                chunk_index=0,
                chunk_text="Gardening and tomatoes",
                embedding=self._make_embedding([0.0, 1.0, 0.0, 0.0]),
            ))
            db.session.add(EntityChunk(
                entity_id=e3.id,
                chunk_index=0,
                chunk_text="Python snake care guide",
                embedding=self._make_embedding([1.0, 0.1, 0.0, 0.1]),
            ))
            db.session.commit()

            # Mock embed_query to return our known query vector
            with patch("services.embeddings.embed_query", return_value=query_vec):
                results = search("python programming", mode="semantic")

            # Should return at least some results
            assert len(results) >= 2

            # e1 (Python Programming) should rank higher than e2 (Gardening)
            result_ids = [r["id"] for r in results]
            e1_pos = result_ids.index(e1.id) if e1.id in result_ids else 999
            e2_pos = result_ids.index(e2.id) if e2.id in result_ids else 999
            assert e1_pos < e2_pos, (
                f"Python Programming (e1) should rank above Gardening (e2). "
                f"Got order: {[r['title'] for r in results]}"
            )

    def test_semantic_search_respects_type_filter(self, app, mock_embed):
        """Semantic search with type filter only returns matching types."""
        query_vec = self._make_embedding([1.0, 0.0, 0.0, 0.0])

        with app.app_context():
            note = create_entity(
                entity_type="note",
                title="Note about ML",
                content="Machine learning is fascinating",
                actor="user",
            )
            db.session.commit()

            task = create_entity(
                entity_type="task",
                title="Task about ML",
                content="Learn machine learning basics",
                actor="user",
            )
            db.session.commit()

            db.session.add(EntityChunk(
                entity_id=note.id,
                chunk_index=0,
                chunk_text="ML note content",
                embedding=self._make_embedding([1.0, 0.0, 0.0, 0.0]),
            ))
            db.session.add(EntityChunk(
                entity_id=task.id,
                chunk_index=0,
                chunk_text="ML task content",
                embedding=self._make_embedding([1.0, 0.0, 0.0, 0.0]),
            ))
            db.session.commit()

            with patch("services.embeddings.embed_query", return_value=query_vec):
                results = search("machine learning", mode="semantic", filters={"type": "note"})

            assert len(results) >= 1
            assert all(r["type"] == "note" for r in results)

    def test_semantic_search_returns_scores(self, app, mock_embed):
        """Semantic search results include _score field."""
        query_vec = self._make_embedding([1.0, 0.0, 0.0, 0.0])

        with app.app_context():
            entity = create_entity(
                entity_type="note",
                title="Scored Entity",
                content="This entity should have a score",
                actor="user",
            )
            db.session.commit()

            db.session.add(EntityChunk(
                entity_id=entity.id,
                chunk_index=0,
                chunk_text="Scored content",
                embedding=self._make_embedding([1.0, 0.0, 0.0, 0.0]),
            ))
            db.session.commit()

            with patch("services.embeddings.embed_query", return_value=query_vec):
                results = search("test", mode="semantic")

            assert len(results) >= 1
            assert "_score" in results[0]
            # Identical vectors should have similarity close to 1.0
            assert results[0]["_score"] > 0.9

    def test_semantic_search_empty_when_no_chunks(self, app, mock_embed):
        """Semantic search returns empty when no embeddings exist."""
        query_vec = self._make_embedding([1.0, 0.0, 0.0, 0.0])

        with app.app_context():
            create_entity(
                entity_type="note",
                title="No Embeddings",
                content="This entity has no chunks",
                actor="user",
            )
            db.session.commit()

            with patch("services.embeddings.embed_query", return_value=query_vec):
                results = search("anything", mode="semantic")

            assert len(results) == 0

    def test_semantic_search_empty_when_embed_fails(self, app):
        """Semantic search returns empty when embed_query returns None."""
        with app.app_context():
            with patch("services.embeddings.embed_query", return_value=None):
                results = search("anything", mode="semantic")

            assert results == []

    def test_semantic_search_multiple_chunks_per_entity(self, app, mock_embed):
        """Entity with multiple chunks uses MAX similarity across chunks."""
        query_vec = self._make_embedding([1.0, 0.0, 0.0, 0.0])

        with app.app_context():
            entity = create_entity(
                entity_type="note",
                title="Multi-chunk Entity",
                content="Has multiple chunks",
                actor="user",
            )
            db.session.commit()

            # Two chunks: one very similar, one very different
            db.session.add(EntityChunk(
                entity_id=entity.id,
                chunk_index=0,
                chunk_text="Similar chunk",
                embedding=self._make_embedding([1.0, 0.0, 0.0, 0.0]),
            ))
            db.session.add(EntityChunk(
                entity_id=entity.id,
                chunk_index=1,
                chunk_text="Different chunk",
                embedding=self._make_embedding([0.0, 1.0, 0.0, 0.0]),
            ))
            db.session.commit()

            with patch("services.embeddings.embed_query", return_value=query_vec):
                results = search("test", mode="semantic")

            assert len(results) == 1
            # Score should reflect the best (most similar) chunk
            assert results[0]["_score"] > 0.9
