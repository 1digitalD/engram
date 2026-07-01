"""Tests for v4 decisions: explicit commitment extraction and record keeping."""

from datetime import datetime, timezone
from unittest.mock import patch

from extensions import db
from models import Decision, Entity, EntityEvent


def test_decision_extracted_from_explicit_commitment(client, app):
    """An explicit commitment in a note becomes a create_decision suggestion."""
    project = client.post(
        "/api/v4/entities", json={"type": "project", "title": "Agent Platform"}
    ).get_json()["data"]

    extraction = {
        "links": [
            {
                "target_type": "project",
                "title": "Agent Platform",
                "relationship_type": "related",
                "confidence": 0.95,
                "evidence": "Agent Platform project",
            }
        ],
        "entities": [
            {
                "type": "task",
                "title": "Ship HITL piece",
                "confidence": 0.9,
                "evidence": "ship HITL piece",
            }
        ],
    }
    decision_candidates = [
        {
            "statement": "Dan committed to ship the HITL piece by Friday",
            "context": "Dan committed to ship the HITL piece by Friday",
            "decided_at": "2026-06-30T10:00:00+00:00",
            "decided_by": "user",
        }
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), \
         patch("services.v4_decisions.extract_decisions_from_note", return_value=decision_candidates), \
         patch("api.v4_entities._decision_thread_id_for_note", return_value=project["id"]):
        response = client.post("/api/v4/capture", json={"content": "Dan committed to ship the HITL piece by Friday"})

    assert response.status_code == 201
    data = response.get_json()
    decision_suggestions = [s for s in data["suggestions"] if s["suggestion_type"] == "create_decision"]
    assert len(decision_suggestions) == 1
    suggestion = decision_suggestions[0]
    assert suggestion["operation_type"] == "create_decision"
    assert suggestion["reason"] == "Explicit commitment detected: Dan committed to ship the HITL piece by Friday"
    assert suggestion["payload"]["statement"] == "Dan committed to ship the HITL piece by Friday"
    assert suggestion["payload"]["thread_id"] == project["id"]

    with app.app_context():
        assert Decision.query.count() == 0


def test_decision_rejected_for_tentative_language(client, app):
    """Tentative phrasing does not produce a decision suggestion."""
    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Maybe ship by Friday",
                "confidence": 0.55,
                "evidence": "maybe ship by Friday",
            }
        ]
    }
    decision_candidates = []

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), \
         patch("services.v4_decisions.extract_decisions_from_note", return_value=decision_candidates):
        response = client.post("/api/v4/capture", json={"content": "We could maybe ship by Friday if things go well"})

    assert response.status_code == 201
    data = response.get_json()
    assert not any(s["suggestion_type"] == "create_decision" for s in data["suggestions"])

    with app.app_context():
        assert Decision.query.count() == 0


def test_decision_always_suggestion_not_auto(client, app):
    """Decisions extracted from capture never auto-create; they stay suggestions."""
    project = client.post(
        "/api/v4/entities", json={"type": "project", "title": "Agent Platform"}
    ).get_json()["data"]

    extraction = {}
    decision_candidates = [
        {
            "statement": "The agent decided to use Python for the stack",
            "context": "The agent decided to use Python for the stack",
            "decided_at": None,
            "decided_by": "agent:v4-capture",
        }
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), \
         patch("services.v4_decisions.extract_decisions_from_note", return_value=decision_candidates), \
         patch("api.v4_entities._decision_thread_id_for_note", return_value=project["id"]):
        response = client.post("/api/v4/capture", json={"content": "The agent decided to use Python for the stack"})

    assert response.status_code == 201
    data = response.get_json()
    decision_suggestions = [s for s in data["suggestions"] if s["suggestion_type"] == "create_decision"]
    assert len(decision_suggestions) == 1

    with app.app_context():
        assert Decision.query.count() == 0

    # Accepting the suggestion creates the decision.
    accept = client.post(f"/api/v4/suggestions/{decision_suggestions[0]['id']}/accept")
    assert accept.status_code == 200
    accepted = accept.get_json()
    assert accepted["decision"]["thread_id"] == project["id"]
    assert accepted["decision"]["statement"] == "The agent decided to use Python for the stack"
    assert accepted["decision"]["decided_by"] == "agent:v4-capture"

    with app.app_context():
        assert Decision.query.count() == 1
        event = EntityEvent.query.filter_by(
            entity_id=project["id"], event_type="decision_recorded"
        ).first()
        assert event is not None


def test_decision_manual_create(client, app):
    """A user can manually record a decision without a source note."""
    project = client.post(
        "/api/v4/entities", json={"type": "project", "title": "Agent Platform"}
    ).get_json()["data"]

    response = client.post(
        "/api/v4/decisions",
        json={
            "thread_id": project["id"],
            "statement": "Use PostgreSQL for the v4 schema",
            "context": "Architecture review",
            "decided_by": "user",
        },
    )

    assert response.status_code == 201
    decision = response.get_json()["data"]
    assert decision["thread_id"] == project["id"]
    assert decision["statement"] == "Use PostgreSQL for the v4 schema"
    assert decision["context"] == "Architecture review"
    assert decision["decided_by"] == "user"
    assert decision["source_note_id"] is None

    # GET /api/v4/decisions returns it.
    list_response = client.get(f"/api/v4/decisions?thread_id={project['id']}")
    assert list_response.status_code == 200
    data = list_response.get_json()
    assert len(data["data"]) == 1
    assert data["data"][0]["statement"] == "Use PostgreSQL for the v4 schema"

    # Entity detail includes the count.
    detail = client.get(f"/api/v4/entities/{project['id']}/detail").get_json()
    assert detail["decisions_count"] == 1

    with app.app_context():
        event = EntityEvent.query.filter_by(
            entity_id=project["id"], event_type="decision_recorded"
        ).first()
        assert event is not None


def test_decision_superseded_chain(client, app):
    """Decisions can be superseded by newer decisions and filtering works."""
    project = client.post(
        "/api/v4/entities", json={"type": "project", "title": "Agent Platform"}
    ).get_json()["data"]

    first = client.post(
        "/api/v4/decisions",
        json={
            "thread_id": project["id"],
            "statement": "Use Python",
            "decided_at": "2026-06-01T00:00:00+00:00",
        },
    ).get_json()["data"]

    second = client.post(
        "/api/v4/decisions",
        json={
            "thread_id": project["id"],
            "statement": "Use TypeScript",
            "decided_at": "2026-06-15T00:00:00+00:00",
        },
    ).get_json()["data"]

    # Cross-thread superseding is rejected.
    other_project = client.post(
        "/api/v4/entities", json={"type": "project", "title": "Other Project"}
    ).get_json()["data"]
    cross_thread = client.post(
        "/api/v4/decisions",
        json={
            "thread_id": other_project["id"],
            "statement": "Use Rust",
            "superseded_by": first["id"],
        },
    )
    assert cross_thread.status_code == 400

    # Mark first as superseded by second directly for the filter assertions.
    with app.app_context():
        first_record = db.session.get(Decision, first["id"])
        first_record.superseded_by = second["id"]
        db.session.commit()

    all_response = client.get(f"/api/v4/decisions?thread_id={project['id']}&superseded=all")
    assert all_response.status_code == 200
    assert len(all_response.get_json()["data"]) == 2

    active_response = client.get(f"/api/v4/decisions?thread_id={project['id']}&superseded=exclude")
    assert active_response.status_code == 200
    active = active_response.get_json()["data"]
    assert len(active) == 1
    assert active[0]["id"] == second["id"]

    superseded_response = client.get(f"/api/v4/decisions?thread_id={project['id']}&superseded=only")
    assert superseded_response.status_code == 200
    superseded = superseded_response.get_json()["data"]
    assert len(superseded) == 1
    assert superseded[0]["id"] == first["id"]

    # Default ordering is decided_at desc.
    all_data = all_response.get_json()["data"]
    assert all_data[0]["id"] == second["id"]
    assert all_data[1]["id"] == first["id"]

    # Detail count reflects active decisions only.
    detail = client.get(f"/api/v4/entities/{project['id']}/detail").get_json()
    assert detail["decisions_count"] == 1
