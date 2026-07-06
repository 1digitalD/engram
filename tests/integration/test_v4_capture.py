"""Cycle 6 tests for basic v4 capture."""

import uuid
from unittest.mock import patch

from models import Entity, Job
from services.job_worker import get_handler, process_job


CAPTURE_RESPONSE_TOP_KEYS = {"source_note", "applied_changes", "suggestions", "warnings"}

SOURCE_NOTE_BASELINE_FIELDS = {
    "id": str,
    "type": str,
    "title": str,
    "content": str,
    "status": str,
    "lifecycle": str,
    "source": str,
    "properties": dict,
    "tags": list,
    "ai": dict,
    "relationship_counts": dict,
    "task_counts": dict,
    "projects": list,
    "areas": list,
    "people": list,
    "linked_counts": dict,
}

APPLIED_CHANGE_BASELINE_FIELDS = {
    "entity_created": {
        "type": str,
        "entity_id": str,
        "entity_type": str,
        "title": str,
        "confidence": (int, float),
    },
    "relationship_added": {
        "type": str,
        "relationship_type": str,
        "confidence": (int, float),
    },
    "entity_updated": {
        "type": str,
        "entity_id": str,
        "entity_type": str,
        "title": str,
        "changes": dict,
    },
}

SUGGESTION_BASELINE_FIELDS = {
    "id": str,
    "source_entity_id": str,
    "suggestion_type": str,
    "operation_type": str,
    "payload": dict,
    "status": str,
    "created_at": str,
    "updated_at": str,
}


def _assert_field_type(value, expected_type):
    if isinstance(expected_type, tuple):
        assert isinstance(value, expected_type), f"expected one of {expected_type}, got {type(value)}"
        return
    assert isinstance(value, expected_type), f"expected {expected_type}, got {type(value)}"


def _assert_baseline_shape(item, baseline_fields):
    for field, expected_type in baseline_fields.items():
        assert field in item, f"missing baseline field {field!r}"
        _assert_field_type(item[field], expected_type)


def _assert_capture_response_contract(data):
    assert set(data) >= CAPTURE_RESPONSE_TOP_KEYS
    _assert_baseline_shape(data["source_note"], SOURCE_NOTE_BASELINE_FIELDS)
    assert isinstance(data["applied_changes"], list)
    assert isinstance(data["suggestions"], list)
    assert isinstance(data["warnings"], list)

    for change in data["applied_changes"]:
        baseline = APPLIED_CHANGE_BASELINE_FIELDS.get(change.get("type"))
        if baseline:
            _assert_baseline_shape(change, baseline)

    for suggestion in data["suggestions"]:
        _assert_baseline_shape(suggestion, SUGGESTION_BASELINE_FIELDS)


def test_capture_saves_source_note_and_queues_embedding(client, app):
    response = client.post(
        "/api/v4/capture",
        json={"content": "Remember to ask Henry about rollout", "source": "quick_capture"},
    )

    assert response.status_code == 201
    data = response.get_json()
    assert set(data) == {"source_note", "applied_changes", "suggestions", "warnings"}
    assert data["source_note"]["type"] == "note"
    assert data["source_note"]["content"] == "Remember to ask Henry about rollout"
    assert data["applied_changes"] == []
    assert data["suggestions"] == []
    assert data["warnings"] == []

    with app.app_context():
        note = Entity.query.filter_by(type="note").one()
        assert note.id == data["source_note"]["id"]
        job = Job.query.filter_by(entity_id=note.id, job_type="embed").one()
        assert job.status == "pending"
        assert job.payload["entity_id"] == note.id
        assert get_handler("embed") is not None


def test_capture_embedding_job_is_processable(client, app):
    response = client.post("/api/v4/capture", json={"content": "Remember the rollout plan"})
    assert response.status_code == 201

    with app.app_context():
        job = Job.query.filter_by(job_type="embed").one()
        with patch("services.embeddings.embed_entity") as mock_embed:
            process_job(job)

        assert job.status == "done"
        mock_embed.assert_called_once()


def test_capture_ai_failure_does_not_lose_note(client, app):
    with patch("api.v4_entities._run_basic_capture_extraction", side_effect=RuntimeError("ai down")):
        response = client.post("/api/v4/capture", json={"content": "Raw note"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["source_note"]["content"] == "Raw note"
    assert "ai down" in data["warnings"][0]
    with app.app_context():
        assert Entity.query.filter_by(type="note", content="Raw note").count() == 1


def test_capture_does_not_auto_create_other_entity_types(client, app):
    response = client.post(
        "/api/v4/capture",
        json={"content": "TODO: create a task for the rollout", "mode": "auto"},
    )

    assert response.status_code == 201
    with app.app_context():
        assert Entity.query.filter(Entity.type != "note").count() == 0


def test_capture_requires_content(client):
    response = client.post("/api/v4/capture", json={"content": ""})

    assert response.status_code == 400
    assert "content is required" in response.get_json()["error"]


def test_capture_response_contract_preserves_baseline_shape(client, app):
    """LAB-01 contract: baseline capture fields unchanged; trust fields are additive."""
    project = client.post(
        "/api/v4/entities", json={"type": "project", "title": "Rollout", "content": "Project"}
    ).get_json()["data"]
    content = f"Need to ask Henry about rollout by Friday {uuid.uuid4()}"
    extraction = {
        "links": [
            {
                "target_type": "project",
                "title": "Rollout",
                "relationship_type": "related",
                "confidence": 0.95,
                "evidence": "rollout project",
            }
        ],
        "entities": [
            {
                "type": "task",
                "title": "Follow up with Henry on rollout",
                "content": "Ask Henry for rollout status.",
                "assigned_to": "Henry",
                "due_at": "2026-07-10",
                "confidence": 0.91,
                "evidence": "ask Henry about rollout",
            },
        ],
    }
    decisions = [
        {
            "action": "link",
            "target_id": project["id"],
            "relationship_type": "related",
            "confidence": 0.95,
            "reason": "existing project",
        },
        {
            "action": "new",
            "relationship_type": "derived_from",
            "confidence": 0.91,
            "reason": "concrete follow-up with named owner",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post(
            "/api/v4/capture",
            json={"content": content, "mode": "auto"},
        )

    assert response.status_code == 201
    data = response.get_json()
    _assert_capture_response_contract(data)

    created = next(c for c in data["applied_changes"] if c["type"] == "entity_created")
    assert created["confidence"] == 0.91
    assert created.get("reason")
    assert created.get("match_confidence") == 0.91
    assert created.get("matched_entity", {}).get("title") == "Follow up with Henry on rollout"
