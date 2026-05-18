"""Cycle 7 tests for v4 capture extraction and suggestions."""

from unittest.mock import patch

from models import AiSuggestion, Entity, EntityEvent, EntityLink


def test_capture_creates_task_suggestion_without_creating_task(client, app):
    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Follow up on rollout",
                "content": "Ask Henry for rollout status.",
                "confidence": 0.91,
                "evidence": "ask Henry about rollout",
            }
        ]
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post("/api/v4/capture", json={"content": "Need to ask Henry about rollout"})

    assert response.status_code == 201
    data = response.get_json()
    assert len(data["suggestions"]) == 1
    suggestion = data["suggestions"][0]
    assert suggestion["suggestion_type"] == "create_task"
    assert suggestion["operation_type"] == "create_entity"
    assert suggestion["payload"]["source_note_id"] == data["source_note"]["id"]
    assert suggestion["payload"]["evidence"] == "ask Henry about rollout"

    with app.app_context():
        assert Entity.query.filter_by(type="task").count() == 0
        assert AiSuggestion.query.filter_by(suggestion_type="create_task").count() == 1


def test_capture_creates_person_suggestion_without_creating_person(client, app):
    extraction = {
        "entities": [
            {
                "type": "person",
                "title": "Henry",
                "confidence": 0.89,
                "evidence": "Henry owns the rollout",
            }
        ]
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post("/api/v4/capture", json={"content": "Henry owns the rollout"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["suggestions"][0]["suggestion_type"] == "create_person"

    with app.app_context():
        assert Entity.query.filter_by(type="person").count() == 0
        person_suggestion = AiSuggestion.query.filter_by(suggestion_type="create_person").one()
        assert person_suggestion.payload["title"] == "Henry"
        assert person_suggestion.payload["source_note_id"] == data["source_note"]["id"]


def test_capture_auto_applies_summary_and_high_confidence_tags(client, app):
    extraction = {
        "summary": "Rollout follow-up with Henry.",
        "confidence": 0.93,
        "tags": [
            {"name": "rollout", "confidence": 0.96},
            {"name": "maybe", "confidence": 0.42},
        ],
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post("/api/v4/capture", json={"content": "Ask Henry about rollout"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["source_note"]["ai"]["summary"] == "Rollout follow-up with Henry."
    assert data["source_note"]["ai"]["status"] == "done"
    assert [tag["name"] for tag in data["source_note"]["tags"]] == ["rollout"]
    assert {"type": "summary_updated", "summary": "Rollout follow-up with Henry."} in data["applied_changes"]
    assert {"type": "tag_added", "tag": "rollout", "confidence": 0.96} in data["applied_changes"]
    assert data["suggestions"] == []


def test_capture_auto_links_existing_project_and_person(client, app):
    project_response = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "Memory Lookup", "content": "Project"},
    )
    person_response = client.post(
        "/api/v4/entities",
        json={"type": "person", "title": "Henry", "content": "Person"},
    )
    project_id = project_response.get_json()["data"]["id"]
    person_id = person_response.get_json()["data"]["id"]
    extraction = {
        "links": [
            {
                "target_type": "project",
                "title": "Memory Lookup",
                "relationship_type": "related",
                "confidence": 0.95,
                "evidence": "Memory Lookup rollout note",
            },
            {
                "target_type": "person",
                "title": "Henry",
                "relationship_type": "mentions",
                "confidence": 0.92,
                "evidence": "Ask Henry",
            },
        ]
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post("/api/v4/capture", json={"content": "Ask Henry about Memory Lookup"})

    assert response.status_code == 201
    data = response.get_json()
    note_id = data["source_note"]["id"]
    assert data["suggestions"] == []
    assert {
        "type": "relationship_added",
        "target_entity_id": project_id,
        "relationship_type": "related",
        "confidence": 0.95,
    } in data["applied_changes"]
    assert {
        "type": "relationship_added",
        "target_entity_id": person_id,
        "relationship_type": "mentions",
        "confidence": 0.92,
    } in data["applied_changes"]

    with app.app_context():
        links = EntityLink.query.filter_by(source_entity_id=note_id).all()
        assert {(link.target_entity_id, link.relationship_type) for link in links} == {
            (project_id, "related"),
            (person_id, "mentions"),
        }
        assert EntityEvent.query.filter_by(entity_id=note_id, event_type="relationship_added").count() == 2


def test_low_confidence_existing_link_is_suggested_not_applied(client, app):
    project_response = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "Memory Lookup", "content": "Project"},
    )
    project_id = project_response.get_json()["data"]["id"]
    extraction = {
        "links": [
            {
                "target_type": "project",
                "title": "Memory Lookup",
                "relationship_type": "related",
                "confidence": 0.51,
                "evidence": "maybe related",
            }
        ]
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post("/api/v4/capture", json={"content": "Maybe Memory Lookup"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["applied_changes"] == []
    assert data["suggestions"][0]["suggestion_type"] == "link_existing"
    assert data["suggestions"][0]["operation_type"] == "link_existing"
    assert data["suggestions"][0]["payload"]["target_entity_id"] == project_id

    with app.app_context():
        assert EntityLink.query.count() == 0
