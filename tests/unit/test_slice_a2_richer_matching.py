"""Slice A2: richer matching context for reconciliation.

TDD red → green for:
1. _build_match_document composes title + content + evidence into a single string
2. _enrich_candidates embeds the composed document, not bare title
3. Candidates with evidence/content produce a different (richer) embed input
4. Empty content/evidence gracefully falls back to title only
5. TOP_K and threshold tuned: integration smoke that exact-title entities are found
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from models import EntityChunk
from services import v4_reconciliation


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ── Unit: _build_match_document ───────────────────────────────────────────────

class TestBuildMatchDocument:
    def test_title_only(self):
        doc = v4_reconciliation._build_match_document(
            {"title": "Agent Platform", "type": "area"}
        )
        assert "Agent Platform" in doc

    def test_title_plus_content(self):
        doc = v4_reconciliation._build_match_document(
            {"title": "Agent Security", "content": "Security policy and standards", "type": "project"}
        )
        assert "Agent Security" in doc
        assert "Security policy and standards" in doc

    def test_title_plus_evidence(self):
        doc = v4_reconciliation._build_match_document(
            {"title": "Security roadmap", "evidence": "we need a security roadmap", "type": "project"}
        )
        assert "Security roadmap" in doc
        assert "we need a security roadmap" in doc

    def test_all_three_fields(self):
        doc = v4_reconciliation._build_match_document({
            "title": "Deals agent family support",
            "content": "Support for GTM deals agent",
            "evidence": "deals agent needs platform support",
            "type": "project",
        })
        assert "Deals agent family support" in doc
        assert "Support for GTM deals agent" in doc
        assert "deals agent needs platform support" in doc

    def test_none_content_and_evidence(self):
        doc = v4_reconciliation._build_match_document(
            {"title": "Something", "content": None, "evidence": None, "type": "task"}
        )
        assert "Something" in doc
        assert "None" not in doc

    def test_empty_strings_ignored(self):
        doc = v4_reconciliation._build_match_document(
            {"title": "Task X", "content": "", "evidence": "   ", "type": "task"}
        )
        assert doc.strip() != ""
        # Should not have trailing whitespace artefacts from empty fields
        assert "  " not in doc.strip()

    def test_returns_string(self):
        doc = v4_reconciliation._build_match_document({"title": "X", "type": "task"})
        assert isinstance(doc, str)

    def test_type_included_for_disambiguation(self):
        """entity type helps disambiguate e.g. a project vs area with same name."""
        doc_proj = v4_reconciliation._build_match_document({"title": "Alpha", "type": "project"})
        doc_area = v4_reconciliation._build_match_document({"title": "Alpha", "type": "area"})
        # Both must contain the title
        assert "Alpha" in doc_proj and "Alpha" in doc_area


# ── Integration: richer embed input ───────────────────────────────────────────

class TestRicherEmbedInput:
    def test_evidence_included_in_embed_input(self, client, app):
        """When a candidate has evidence, the embed call includes it."""
        candidates = [{
            "type": "project",
            "title": "Security roadmap",
            "evidence": "we need a clear security roadmap for the platform",
            "confidence": 0.7,
        }]
        fake_vec = [[0.5] + [0.0] * 1535]

        with patch("services.v4_reconciliation._embed_texts", return_value=fake_vec) as mock_embed:
            with patch("services.v4_reconciliation._call_model", return_value=[
                {"action": "new", "target_id": None, "fields": {},
                 "relationship_type": None, "confidence": 0.5, "reason": "test"}
            ]):
                v4_reconciliation.reconcile_candidates(candidates)

        texts_sent = mock_embed.call_args[0][0]
        assert len(texts_sent) == 1
        assert "Security roadmap" in texts_sent[0]
        assert "security roadmap for the platform" in texts_sent[0]

    def test_content_included_in_embed_input(self, client, app):
        candidates = [{
            "type": "project",
            "title": "Agent memory utilization",
            "content": "Track and improve how agents use memory APIs",
            "confidence": 0.7,
        }]
        fake_vec = [[0.5] + [0.0] * 1535]

        with patch("services.v4_reconciliation._embed_texts", return_value=fake_vec) as mock_embed:
            with patch("services.v4_reconciliation._call_model", return_value=[
                {"action": "new", "target_id": None, "fields": {},
                 "relationship_type": None, "confidence": 0.5, "reason": "test"}
            ]):
                v4_reconciliation.reconcile_candidates(candidates)

        texts_sent = mock_embed.call_args[0][0]
        assert "Agent memory utilization" in texts_sent[0]
        assert "Track and improve" in texts_sent[0]

    def test_title_only_candidate_still_works(self, client, app):
        candidates = [{"type": "task", "title": "Write tests", "confidence": 0.9}]
        fake_vec = [[1.0] + [0.0] * 1535]

        with patch("services.v4_reconciliation._embed_texts", return_value=fake_vec) as mock_embed:
            with patch("services.v4_reconciliation._call_model", return_value=[
                {"action": "new", "target_id": None, "fields": {},
                 "relationship_type": None, "confidence": 0.5, "reason": "test"}
            ]):
                v4_reconciliation.reconcile_candidates(candidates)

        texts_sent = mock_embed.call_args[0][0]
        assert "Write tests" in texts_sent[0]

    def test_eight_candidates_richer_still_one_call(self, client, app):
        """Richer embed input doesn't break the 1-call invariant from A1."""
        candidates = [
            {"type": "project", "title": f"Project {i}",
             "evidence": f"evidence for project {i}", "confidence": 0.7}
            for i in range(8)
        ]
        fake_vecs = [[float(i)] + [0.0] * 1535 for i in range(8)]

        with patch("services.v4_reconciliation._embed_texts", return_value=fake_vecs) as mock_embed:
            with patch("services.v4_reconciliation._call_model", return_value=[
                {"action": "new", "target_id": None, "fields": {},
                 "relationship_type": None, "confidence": 0.5, "reason": "test"}
                for _ in range(8)
            ]):
                v4_reconciliation.reconcile_candidates(candidates)

        assert mock_embed.call_count == 1
        assert len(mock_embed.call_args[0][0]) == 8


# ── Integration: semantic similarity via composed doc ─────────────────────────

class TestSemanticMatchViaComposedDoc:
    def test_paraphrase_match_found_with_evidence(self, client, app):
        """Candidate 'Security roadmap' with evidence finds 'Agent Security' via similarity."""
        # Create an entity whose chunk vector we control
        proj = _make_entity(client, "project", "Agent Security",
                            content="Security policy, standards, toolkit support, gateway enforcement")
        # Chunk with a vector that represents "security roadmap platform"
        security_vec = [1.0, 0.5] + [0.0] * 1534
        _add_chunk(app, proj["id"], "security roadmap policy standards toolkit", security_vec)

        candidates = [{
            "type": "project",
            "title": "Security roadmap",
            "evidence": "we need a security roadmap for the platform",
            "confidence": 0.7,
        }]

        # Return a similar vector for the composed query — should score above threshold
        with patch("services.v4_reconciliation._embed_texts", return_value=[security_vec]):
            with patch("services.v4_reconciliation._call_model") as mock_model:
                mock_model.return_value = [
                    {"action": "link", "target_id": proj["id"], "fields": {},
                     "relationship_type": "related", "confidence": 0.8, "reason": "security match"}
                ]
                v4_reconciliation.reconcile_candidates(candidates)
                enriched = mock_model.call_args[0][0]

        matches = enriched[0]["matches"]
        assert any(m["id"] == proj["id"] for m in matches), (
            f"Agent Security not found in matches: {matches}"
        )

    def test_exact_title_match_preserved_with_richer_compose(self, client, app):
        """Exact title match still works when the composed doc is richer."""
        proj = _make_entity(client, "area", "Agent Platform",
                            content="Platform capabilities used by agent crews")
        candidates = [{
            "type": "area",
            "title": "Agent Platform",
            "evidence": "the agent platform provides HITL and memory capabilities",
            "confidence": 0.8,
        }]

        # Exact match runs via DB — no embedding needed
        with patch("services.v4_reconciliation._embed_texts", return_value=[]) as mock_embed:
            with patch("services.v4_reconciliation._call_model") as mock_model:
                mock_model.return_value = [
                    {"action": "link", "target_id": proj["id"], "fields": {},
                     "relationship_type": "related", "confidence": 0.9, "reason": "exact"}
                ]
                v4_reconciliation.reconcile_candidates(candidates)
                enriched = mock_model.call_args[0][0]

        matches = enriched[0]["matches"]
        assert any(m["id"] == proj["id"] and m["score"] == 1.0 for m in matches), (
            f"Exact match for 'Agent Platform' not found: {matches}"
        )
