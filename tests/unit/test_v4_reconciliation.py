"""Unit tests for reconciliation skip/uncertain decision vocabulary."""

from unittest.mock import patch

from services import v4_reconciliation


def test_low_confidence_defaults_to_skip():
    candidates = [
        {"type": "person", "title": "Mary", "confidence": 0.3},
    ]

    with patch("services.v4_reconciliation._enrich_candidates", return_value=[{"candidate": candidates[0], "matches": []}]), \
         patch("services.v4_reconciliation._call_model", return_value=[]):
        decisions = v4_reconciliation.reconcile_candidates(candidates)

    assert len(decisions) == 1
    assert decisions[0]["action"] == "skip"


def test_high_confidence_still_creates():
    candidates = [
        {"type": "task", "title": "Follow up with Henry", "confidence": 0.95},
    ]

    with patch("services.v4_reconciliation._enrich_candidates", return_value=[{"candidate": candidates[0], "matches": []}]), \
         patch("services.v4_reconciliation._call_model", return_value=[]):
        decisions = v4_reconciliation.reconcile_candidates(candidates)

    assert len(decisions) == 1
    assert decisions[0]["action"] == "new"


def test_uncertain_decision_labeled_in_reason():
    from api.v4_entities import _capture_suggestion_reason

    decision = {"action": "uncertain", "confidence": 0.7, "reason": "maybe a person"}
    reason = _capture_suggestion_reason(decision, confidence=0.7)
    assert reason == v4_reconciliation.UNCERTAIN_SUGGESTION_REASON

    reason_with_evidence = _capture_suggestion_reason(
        decision, confidence=0.7, evidence="follow up with Akash about Q3"
    )
    assert reason_with_evidence == "follow up with Akash about Q3"

    assert v4_reconciliation.is_uncertain_decision({"action": "skip", "confidence": 0.9}) is True
    assert v4_reconciliation.is_uncertain_decision({"action": "new", "confidence": 0.7}, confidence=0.7) is True
    assert v4_reconciliation.is_uncertain_decision({"action": "new", "confidence": 0.91}, confidence=0.91) is False


def test_enrich_candidates_biases_attached_thread_entity(client, app):
    project = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "HITL Pilot", "content": "Pilot rollout"},
    ).get_json()["data"]

    candidates = [
        {
            "type": "project",
            "title": "Parser fix shipped",
            "evidence": "shipped parser fix for the pilot",
            "confidence": 0.8,
        }
    ]
    fake_vec = [[0.1] + [0.0] * 1535]

    with patch("services.v4_reconciliation._embed_texts", return_value=fake_vec):
        with app.app_context():
            enriched = v4_reconciliation._enrich_candidates(candidates, thread_id=project["id"])

    matches = enriched[0]["matches"]
    thread_match = next((m for m in matches if m["id"] == project["id"]), None)
    assert thread_match is not None
    assert thread_match["score"] == 0.95
    assert thread_match["title"] == "HITL Pilot"


def test_enrich_candidates_applies_thread_bias_without_embeddings(client, app):
    project = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "HITL Pilot", "content": "Pilot rollout"},
    ).get_json()["data"]

    candidates = [{"type": "project", "confidence": 0.8}]

    with patch("services.v4_reconciliation._embed_texts", return_value=[]):
        with app.app_context():
            enriched = v4_reconciliation._enrich_candidates(candidates, thread_id=project["id"])

    matches = enriched[0]["matches"]
    thread_match = next((m for m in matches if m["id"] == project["id"]), None)
    assert thread_match is not None
    assert thread_match["score"] == 0.95
