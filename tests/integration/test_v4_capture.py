"""Cycle 6 tests for basic v4 capture."""

from unittest.mock import patch

from models import Entity, Job


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
