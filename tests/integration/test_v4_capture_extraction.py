"""Tests for v4 capture extraction and auto-apply behavior."""

from unittest.mock import patch

from models import AiSuggestion, Entity, EntityEvent, EntityLink


def test_capture_auto_creates_high_confidence_task(client, app):
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
    assert data["suggestions"] == []
    entity_created = next((c for c in data["applied_changes"] if c["type"] == "entity_created"), None)
    assert entity_created is not None
    assert entity_created["entity_type"] == "task"
    assert entity_created["title"] == "Follow up on rollout"

    with app.app_context():
        assert Entity.query.filter_by(type="task").count() == 1
        assert AiSuggestion.query.filter_by(suggestion_type="create_task").count() == 0


def test_capture_auto_creates_high_confidence_person(client, app):
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
    assert data["suggestions"] == []
    entity_created = next((c for c in data["applied_changes"] if c["type"] == "entity_created"), None)
    assert entity_created is not None
    assert entity_created["entity_type"] == "person"
    assert entity_created["title"] == "Henry"

    with app.app_context():
        assert Entity.query.filter_by(type="person").count() == 1
        assert AiSuggestion.query.filter_by(suggestion_type="create_person").count() == 0


def test_capture_suggests_low_confidence_entity(client, app):
    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Maybe follow up",
                "confidence": 0.55,
                "evidence": "possibly",
            }
        ]
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post("/api/v4/capture", json={"content": "Maybe follow up"})

    assert response.status_code == 201
    data = response.get_json()
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["suggestion_type"] == "create_task"

    with app.app_context():
        assert Entity.query.filter_by(type="task").count() == 0
        assert AiSuggestion.query.filter_by(suggestion_type="create_task").count() == 1


def test_capture_auto_creates_high_confidence_link_candidate(client, app):
    """When a link candidate references a non-existent entity at high confidence, auto-create and link it."""
    extraction = {
        "links": [
            {
                "target_type": "project",
                "title": "Memory Lookup",
                "relationship_type": "related",
                "confidence": 0.92,
                "evidence": "Memory Lookup rollout note",
            }
        ]
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post("/api/v4/capture", json={"content": "Ask Henry about Memory Lookup"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["suggestions"] == []
    assert any(c["type"] == "entity_created" and c["entity_type"] == "project" for c in data["applied_changes"])
    assert any(c["type"] == "relationship_added" for c in data["applied_changes"])

    with app.app_context():
        assert Entity.query.filter_by(type="project", title="Memory Lookup").count() == 1


def test_capture_suggests_low_confidence_missing_link(client, app):
    """When a link candidate references a non-existent entity at low confidence, suggest don't create."""
    extraction = {
        "links": [
            {
                "target_type": "project",
                "title": "Unknown Project",
                "relationship_type": "related",
                "confidence": 0.55,
                "evidence": "maybe",
            }
        ]
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post("/api/v4/capture", json={"content": "Something about Unknown Project"})

    assert response.status_code == 201
    data = response.get_json()
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["suggestion_type"] == "create_project"

    with app.app_context():
        assert Entity.query.filter_by(type="project").count() == 0


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
