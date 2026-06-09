"""Slice A1: batch embeddings in reconciliation.

TDD red → green for:
1. reconcile_candidates makes exactly ONE _embed_texts call for N candidates
   (not N calls), and the call includes all candidate titles.
2. The chunk set for each entity type is loaded once, not once per candidate
   of that type.
3. Match output is identical to the per-candidate path (same matches, same order).
4. Single-candidate and zero-candidate edge cases work correctly.
5. Fallback (no OPENAI_API_KEY) still works and uses exact-match heuristics.
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from models import Entity, EntityChunk
from services import v4_reconciliation


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_entity(client, entity_type, title, content=""):
    r = client.post("/api/v4/entities", json={"type": entity_type, "title": title, "content": content})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["data"]


def _add_chunk(app, entity_id, text, vector):
    with app.app_context():
        from extensions import db
        chunk = EntityChunk(
            entity_id=entity_id,
            chunk_index=0,
            chunk_text=text,
            embedding=vector,
            embedding_model="test",
        )
        db.session.add(chunk)
        db.session.commit()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestBatchEmbeddingCallCount:
    """Core invariant: one _embed_texts call per reconcile_candidates call."""

    def test_eight_candidates_one_embed_call(self, client, app):
        """8 candidates → 1 batch call with 8 titles, not 8 separate calls."""
        # Create some existing entities to give the matcher something to find
        p1 = _make_entity(client, "project", "Agent Platform Alpha")
        p2 = _make_entity(client, "project", "Agent Platform Beta")

        candidates = [
            {"type": "project", "title": f"Project {i}", "confidence": 0.7}
            for i in range(8)
        ]

        fake_vectors = [[float(i)] + [0.0] * 1535 for i in range(8)]

        with patch("services.v4_reconciliation._embed_texts", return_value=fake_vectors) as mock_embed:
            with patch("services.v4_reconciliation._call_model", return_value=[
                {"action": "new", "target_id": None, "fields": {}, "relationship_type": None,
                 "confidence": 0.5, "reason": "test"}
                for _ in range(8)
            ]):
                v4_reconciliation.reconcile_candidates(candidates)

        assert mock_embed.call_count == 1, (
            f"Expected 1 _embed_texts call for 8 candidates, got {mock_embed.call_count}"
        )
        docs_sent = mock_embed.call_args[0][0]
        assert len(docs_sent) == 8
        # Each doc must at minimum contain the candidate title (A2: composed doc)
        for cand, doc in zip(candidates, docs_sent):
            assert cand["title"] in doc

    def test_single_candidate_one_embed_call(self, client, app):
        candidates = [{"type": "task", "title": "Fix the bug", "confidence": 0.8}]
        fake_vectors = [[1.0] + [0.0] * 1535]

        with patch("services.v4_reconciliation._embed_texts", return_value=fake_vectors) as mock_embed:
            with patch("services.v4_reconciliation._call_model", return_value=[
                {"action": "new", "target_id": None, "fields": {}, "relationship_type": None,
                 "confidence": 0.5, "reason": "test"}
            ]):
                v4_reconciliation.reconcile_candidates(candidates)

        assert mock_embed.call_count == 1
        doc_sent = mock_embed.call_args[0][0][0]
        assert "Fix the bug" in doc_sent

    def test_zero_candidates_no_embed_call(self, client, app):
        with patch("services.v4_reconciliation._embed_texts") as mock_embed:
            result = v4_reconciliation.reconcile_candidates([])
        assert mock_embed.call_count == 0
        assert result == []

    def test_mixed_types_still_one_embed_call(self, client, app):
        """Candidates of different entity types still get one batched embed call."""
        candidates = [
            {"type": "project", "title": "Alpha Project", "confidence": 0.7},
            {"type": "person", "title": "Alice Smith", "confidence": 0.8},
            {"type": "task", "title": "Write tests", "confidence": 0.9},
            {"type": "area", "title": "Engineering", "confidence": 0.7},
        ]
        fake_vectors = [[float(i)] + [0.0] * 1535 for i in range(4)]

        with patch("services.v4_reconciliation._embed_texts", return_value=fake_vectors) as mock_embed:
            with patch("services.v4_reconciliation._call_model", return_value=[
                {"action": "new", "target_id": None, "fields": {}, "relationship_type": None,
                 "confidence": 0.5, "reason": "test"}
                for _ in range(4)
            ]):
                v4_reconciliation.reconcile_candidates(candidates)

        assert mock_embed.call_count == 1
        assert len(mock_embed.call_args[0][0]) == 4


class TestChunkLoadedOncePerType:
    """Each entity type's chunk set is fetched at most once per reconcile call."""

    def test_same_type_chunks_loaded_once(self, client, app):
        """3 project candidates → EntityChunk queried once for projects."""
        _make_entity(client, "project", "Existing Project One")
        _make_entity(client, "project", "Existing Project Two")

        candidates = [
            {"type": "project", "title": "Alpha", "confidence": 0.7},
            {"type": "project", "title": "Beta", "confidence": 0.7},
            {"type": "project", "title": "Gamma", "confidence": 0.7},
        ]
        fake_vectors = [[float(i)] + [0.0] * 1535 for i in range(3)]

        with patch("services.v4_reconciliation._embed_texts", return_value=fake_vectors):
            with patch("services.v4_reconciliation._call_model", return_value=[
                {"action": "new", "target_id": None, "fields": {}, "relationship_type": None,
                 "confidence": 0.5, "reason": "test"}
                for _ in range(3)
            ]):
                with patch("services.v4_reconciliation._load_chunks_for_type") as mock_load:
                    mock_load.return_value = []
                    v4_reconciliation.reconcile_candidates(candidates)

        # Should be called once for "project", not once per candidate
        project_calls = [c for c in mock_load.call_args_list if c[0][0] == "project"]
        assert len(project_calls) == 1, (
            f"Expected 1 chunk load for 'project', got {len(project_calls)}"
        )

    def test_different_types_each_loaded_once(self, client, app):
        """project + person candidates → each type loaded once."""
        candidates = [
            {"type": "project", "title": "Alpha Project", "confidence": 0.7},
            {"type": "project", "title": "Beta Project", "confidence": 0.7},
            {"type": "person", "title": "Alice", "confidence": 0.8},
            {"type": "person", "title": "Bob", "confidence": 0.8},
        ]
        fake_vectors = [[float(i)] + [0.0] * 1535 for i in range(4)]

        with patch("services.v4_reconciliation._embed_texts", return_value=fake_vectors):
            with patch("services.v4_reconciliation._call_model", return_value=[
                {"action": "new", "target_id": None, "fields": {}, "relationship_type": None,
                 "confidence": 0.5, "reason": "test"}
                for _ in range(4)
            ]):
                with patch("services.v4_reconciliation._load_chunks_for_type") as mock_load:
                    mock_load.return_value = []
                    v4_reconciliation.reconcile_candidates(candidates)

        types_loaded = [c[0][0] for c in mock_load.call_args_list]
        assert types_loaded.count("project") == 1
        assert types_loaded.count("person") == 1
        assert len(mock_load.call_args_list) == 2


class TestMatchOutputCorrectness:
    """Batch path produces identical matches to the per-candidate path."""

    def test_exact_match_still_found(self, client, app):
        """Exact title match at score=1.0 is preserved in batch mode."""
        proj = _make_entity(client, "project", "My Exact Project")

        candidates = [{"type": "project", "title": "My Exact Project", "confidence": 0.9}]

        # No embedding needed for exact match — it uses DB title lookup
        with patch("services.v4_reconciliation._embed_texts", return_value=[]) as mock_embed:
            with patch("services.v4_reconciliation._call_model") as mock_model:
                mock_model.return_value = [
                    {"action": "link", "target_id": proj["id"], "fields": {},
                     "relationship_type": "related", "confidence": 0.9, "reason": "exact"}
                ]
                v4_reconciliation.reconcile_candidates(candidates)
                enriched = mock_model.call_args[0][0]

        # The enriched item should have the exact match in its matches list
        assert len(enriched) == 1
        matches = enriched[0]["matches"]
        assert any(m["id"] == proj["id"] and m["score"] == 1.0 for m in matches), (
            f"Exact match not found in: {matches}"
        )

    def test_semantic_match_found_via_batch(self, client, app):
        """High-similarity chunk found via batch embedding scores above threshold."""
        proj = _make_entity(client, "project", "Agent Memory Rollout")
        # Add a chunk with a known vector
        high_sim_vec = [1.0] + [0.0] * 1535
        _add_chunk(app, proj["id"], "agent memory rollout deployment", high_sim_vec)

        candidates = [{"type": "project", "title": "Agent Memory Rollout", "confidence": 0.8}]

        # Return the same vector for the query — cosine similarity will be 1.0
        with patch("services.v4_reconciliation._embed_texts", return_value=[high_sim_vec]):
            with patch("services.v4_reconciliation._call_model") as mock_model:
                mock_model.return_value = [
                    {"action": "link", "target_id": proj["id"], "fields": {},
                     "relationship_type": "related", "confidence": 0.9, "reason": "match"}
                ]
                v4_reconciliation.reconcile_candidates(candidates)
                enriched = mock_model.call_args[0][0]

        matches = enriched[0]["matches"]
        assert any(m["id"] == proj["id"] for m in matches), (
            f"Semantic match not found via batch path: {matches}"
        )

    def test_below_threshold_not_matched(self, client, app):
        """Candidates with similarity below SIMILARITY_THRESHOLD are not returned."""
        proj = _make_entity(client, "project", "Unrelated Project")
        orthogonal_vec = [0.0, 1.0] + [0.0] * 1534
        _add_chunk(app, proj["id"], "something completely unrelated", orthogonal_vec)

        candidates = [{"type": "project", "title": "Different Thing", "confidence": 0.7}]
        # Query vector orthogonal to the chunk → cosine = 0 < threshold
        query_vec = [1.0] + [0.0] * 1535

        with patch("services.v4_reconciliation._embed_texts", return_value=[query_vec]):
            with patch("services.v4_reconciliation._call_model") as mock_model:
                mock_model.return_value = [
                    {"action": "new", "target_id": None, "fields": {},
                     "relationship_type": None, "confidence": 0.5, "reason": "no match"}
                ]
                v4_reconciliation.reconcile_candidates(candidates)
                enriched = mock_model.call_args[0][0]

        # proj should NOT appear in matches (similarity = 0 < threshold 0.60)
        matches = enriched[0]["matches"]
        assert not any(m["id"] == proj["id"] for m in matches), (
            f"Below-threshold entity should not appear in matches: {matches}"
        )


class TestFallbackBehavior:
    """No OPENAI_API_KEY → heuristic fallback still works correctly."""

    def test_exact_match_heuristic_no_api_key(self, client, app, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        proj = _make_entity(client, "project", "Exact Match Project")

        candidates = [{"type": "project", "title": "Exact Match Project", "confidence": 0.9}]
        decisions = v4_reconciliation.reconcile_candidates(candidates)

        assert len(decisions) == 1
        assert decisions[0]["action"] == "link"
        assert decisions[0]["target_id"] == proj["id"]

    def test_no_match_heuristic_no_api_key(self, client, app, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        candidates = [{"type": "project", "title": "Brand New Thing XYZ123", "confidence": 0.7}]
        decisions = v4_reconciliation.reconcile_candidates(candidates)

        assert len(decisions) == 1
        assert decisions[0]["action"] == "new"

    def test_output_count_matches_input(self, client, app, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        candidates = [
            {"type": "task", "title": f"Task {i}", "confidence": 0.7}
            for i in range(5)
        ]
        decisions = v4_reconciliation.reconcile_candidates(candidates)
        assert len(decisions) == 5
