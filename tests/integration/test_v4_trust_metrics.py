"""Tests for the trust metrics endpoint."""

from datetime import datetime, timezone

from extensions import db
from models import AiSuggestion, Entity, EntityEvent


def _entity(client, entity_type="task", title="T"):
    return client.post("/api/v4/entities", json={"type": entity_type, "title": title}).get_json()["data"]


def test_trust_metrics_aggregates_outcomes(client, app):
    note = client.post("/api/v4/capture", json={"content": "note for metrics"}).get_json()["source_note"]
    task = _entity(client, "task", "Agent-created task")

    with app.app_context():
        now = datetime.now(timezone.utc)
        # One accepted, two dismissed suggestions, one pending.
        for status in ("accepted", "dismissed", "dismissed", "pending"):
            db.session.add(AiSuggestion(
                source_entity_id=note["id"],
                suggestion_type="create_task",
                operation_type="create_entity",
                payload={"type": "task", "title": "x"},
                status=status,
                resolved_at=now if status != "pending" else None,
            ))
        # Agent created the task, user deleted it (quick kill), one merge event.
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
    assert data["corrections"]["quick_kills"] == 1
    assert data["corrections"]["total"] == 0 + 1 + 2 + 1  # reverts + merges + dismissals + kills
    assert data["agent_actions"]["total"] >= 1
    assert data["correction_rate"] is not None
    assert isinstance(data["weekly"], list) and len(data["weekly"]) >= 1


def test_trust_metrics_empty_db(client, app):
    data = client.get("/api/v4/metrics/trust").get_json()
    assert data["suggestions"]["acceptance_rate"] is None
    assert data["corrections"]["total"] == 0
