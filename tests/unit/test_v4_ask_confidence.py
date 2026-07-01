"""Unit tests for services.v4_ask._compute_confidence and B-017 IDK threshold.

Tests the ask service's confidence scoring without going through the full
Flask test client. Avoids the database fixture deadlock that affects
integration tests.
"""

import sys
from unittest.mock import patch

sys.path.insert(0, "/Volumes/lex1t/dev/shared/repos/engram")

from services import v4_ask


def test_empty_citations_is_low():
    assert v4_ask._compute_confidence([]) == "low"


def test_two_high_relevance_is_high():
    citations = [
        {"entity_id": "a", "snippet": "x", "relevance": 0.8},
        {"entity_id": "b", "snippet": "x", "relevance": 0.75},
    ]
    assert v4_ask._compute_confidence(citations) == "high"


def test_one_high_relevance_is_medium():
    citations = [{"entity_id": "a", "snippet": "x", "relevance": 0.8}]
    assert v4_ask._compute_confidence(citations) == "medium"


def test_weak_citations_is_low_b017():
    """B-017: weak citations (max relevance below threshold) should be low.

    Previously the code only returned 'low' for empty citations. With weak
    citations (relevance 0.3-0.5) it returned 'medium' and the LLM
    confabulated. After the fix, weak citations are 'low' so the IDK path
    fires.
    """
    citations = [
        {"entity_id": "a", "snippet": "x", "relevance": 0.45},
        {"entity_id": "b", "snippet": "x", "relevance": 0.35},
        {"entity_id": "c", "snippet": "x", "relevance": 0.30},
    ]
    assert v4_ask._compute_confidence(citations) == "low"


def test_marginal_citations_is_medium():
    """Citations between WEAK_RELEVANCE (0.5) and HIGH_RELEVANCE (0.7) are
    'medium' — the LLM gets the context but isn't asked to be confident."""
    citations = [
        {"entity_id": "a", "snippet": "x", "relevance": 0.65},
        {"entity_id": "b", "snippet": "x", "relevance": 0.55},
    ]
    # 0.65 is above WEAK_RELEVANCE (0.5) but below HIGH_RELEVANCE (0.7).
    # Should be medium — context is provided but with caveats.
    result = v4_ask._compute_confidence(citations)
    assert result == "medium", f"Expected medium for marginal citations, got {result}"


def test_just_below_weak_threshold_is_low():
    """Edge case: max relevance exactly at WEAK_RELEVANCE-epsilon should
    trigger the low path. Verifies strict-less-than semantics."""
    citations = [
        {"entity_id": "a", "snippet": "x", "relevance": 0.499},
    ]
    assert v4_ask._compute_confidence(citations) == "low"


def test_exactly_at_weak_threshold_is_medium():
    """Edge case: max relevance exactly at WEAK_RELEVANCE stays medium."""
    citations = [
        {"entity_id": "a", "snippet": "x", "relevance": 0.5},
    ]
    assert v4_ask._compute_confidence(citations) == "medium"


def test_idk_response_shape():
    """B-017: IDK response should match the contract — answer string, no
    citations, low confidence, with caveat about weak grounding."""
    citations = [
        {"entity_id": "a", "snippet": "x", "relevance": 0.3},
    ]
    result = v4_ask._idk_response("What?", citations)
    assert result["answer"] == "I don't have anything in the workspace that answers this."
    assert result["confidence"] == "low"
    assert result["citations"] == []
    assert result["caveats"]
    assert any("matching" in c.lower() or "ground" in c.lower() for c in result["caveats"])


def test_idk_response_for_empty_citations():
    result = v4_ask._idk_response("What?", [])
    assert result["answer"] == "I don't have anything in the workspace that answers this."
    assert result["confidence"] == "low"
    assert result["citations"] == []
    assert any("matching" in c.lower() or "no matching" in c.lower() for c in result["caveats"])


if __name__ == "__main__":
    # Allow running without pytest as a smoke check
    test_empty_citations_is_low()
    test_two_high_relevance_is_high()
    test_one_high_relevance_is_medium()
    test_weak_citations_is_low_b017()
    test_marginal_citations_is_medium()
    test_just_below_weak_threshold_is_low()
    test_exactly_at_weak_threshold_is_medium()
    test_idk_response_shape()
    test_idk_response_for_empty_citations()
    print("All _compute_confidence + _idk_response unit tests passed.")