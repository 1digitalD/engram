"""Tests for the trust metrics endpoint."""

from datetime import datetime, timezone

from extensions import db
from models import AiSuggestion, EntityEvent


def _entity(client, entity_type="task", title="T"):
    response = client.post("/api/v4/entities", json={"type": entity_type, "title": title})
    return response.get_json()["data"]


def test_trust_metrics_aggregates_outcomes(client, app):
    note = client.post("/api/v4/capture", json={"content": "note for metrics"}).get_json()["source_note"]
    task = _entity(client, "task", "Agent-created task")

    with app.app_context():
        now = datetime.now(timezone.utc)
        for status in ("accepted", "dismissed", "dismissed", "pending"):
            db.session.add(
                AiSuggestion(
                    source_entity_id=note["id"],
                    suggestion_type="create_task",
                    operation_type="create_entity",
                    payload={"type": "task", "title": "x"},
                    status=status,
                    resolved_at=now if status != "pending" else None,
                )
            )

        db.session.add(EntityEvent(entity_id=task["id"], event_type="created", actor="agent:v4-capture"))
        db.session.add(EntityEvent(entity_id=task["id"], event_type="deleted", actor="user"))
        db.session.add(EntityEvent(entity_id=task["id"], event_type="merged", actor="user"))
        db.session.commit()

    data = client.get("/api/v4/metrics/trust?days=30").get_json()

    assert data["window_days"] == 30
    assert data["suggestions"]["accepted"] == 1
    assert data["suggestions"]["dismissed"] == 2
    assert data["suggestions"]["pending"] == 1
    assert data["suggestions"]["acceptance_rate"] == round(1 / 3, 3)
    assert data["corrections"]["merges"] == 1
    assert data["corrections"]["dismissals"] == 2
    assert data["corrections"]["quick_kills"] == 1
    assert data["corrections"]["total"] == 0 + 1 + 2 + 1  # reverts + merges + dismissals + kills
    assert data["correction_rate"] == round(
        data["corrections"]["total"] / data["agent_actions"]["total"], 3
    )
    assert data["review"]["completed_reports"] == 0
    assert data["review"]["median_duration_ms"] is None


def test_trust_metrics_defaults_to_30_day_window(client):
    data = client.get("/api/v4/metrics/trust").get_json()
    assert data["window_days"] == 30


def test_review_duration_events_are_recorded_in_trust_metrics(client):
    response = client.post(
        "/api/v4/metrics/trust/review",
        json={"report_id": "report-1", "duration_ms": 45000, "suggestion_count": 3},
    )

    assert response.status_code == 201
    payload = response.get_json()["data"]
    assert payload["report_id"] == "report-1"
    assert payload["duration_ms"] == 45000
    assert payload["suggestion_count"] == 3

    metrics = client.get("/api/v4/metrics/trust?days=30").get_json()
    assert metrics["review"]["completed_reports"] == 1
    assert metrics["review"]["median_duration_ms"] == 45000
    assert metrics["review"]["median_duration_seconds"] == 45.0
    assert metrics["review"]["last_completed_at"] is not None
