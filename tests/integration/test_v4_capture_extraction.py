"""Tests for v4 capture extraction and auto-apply behavior."""

import os
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


def test_capture_auto_created_task_uses_task_to_note_derived_from_link(client, app):
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
    note_id = response.get_json()["source_note"]["id"]

    with app.app_context():
        task = Entity.query.filter_by(type="task", title="Follow up on rollout").one()
        link = EntityLink.query.filter_by(
            source_entity_id=task.id,
            target_entity_id=note_id,
            relationship_type="derived_from",
        ).one()
        assert link.source == "ai"

    note_detail = client.get(f"/api/v4/entities/{note_id}/detail")
    task_detail = client.get(f"/api/v4/entities/{task.id}/detail")
    assert note_detail.status_code == 200
    assert task_detail.status_code == 200

    note_sections = {section["key"]: section for section in note_detail.get_json()["sections"]}
    task_sections = {section["key"]: section for section in task_detail.get_json()["sections"]}
    assert [item["entity"]["id"] for item in note_sections["derived_tasks"]["items"]] == [task.id]
    assert [item["entity"]["id"] for item in task_sections["source_notes"]["items"]] == [note_id]


def test_capture_auto_created_task_applies_assigned_to_person_link(client, app):
    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Follow up on rollout",
                "content": "Ask Henry for rollout status.",
                "assigned_to": "Henry",
                "confidence": 0.91,
                "evidence": "Henry: follow up on rollout",
            }
        ]
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post("/api/v4/capture", json={"content": "Henry should follow up on rollout"})

    assert response.status_code == 201
    data = response.get_json()
    assert any(
        change["type"] == "entity_created" and change["entity_type"] == "person" and change["title"] == "Henry"
        for change in data["applied_changes"]
    )

    with app.app_context():
        task = Entity.query.filter_by(type="task", title="Follow up on rollout").one()
        person = Entity.query.filter_by(type="person", title="Henry").one()
        EntityLink.query.filter_by(
            source_entity_id=task.id,
            target_entity_id=person.id,
            relationship_type="assigned_to",
        ).one()
        assert EntityEvent.query.filter_by(entity_id=task.id, event_type="relationship_added").count() >= 1


def test_capture_reuses_existing_ai_person_assignee_without_recreating_it(client, app):
    with app.app_context():
        person = Entity(
            type="person",
            title="Henry",
            content=None,
            status="active",
            lifecycle="active",
            source="ai_capture",
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        app.extensions["sqlalchemy"].session.add(person)
        app.extensions["sqlalchemy"].session.flush()
        person_id = person.id
        app.extensions["sqlalchemy"].session.commit()

    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Follow up on rollout",
                "content": "Ask Henry for rollout status.",
                "assigned_to": "Henry",
                "confidence": 0.91,
                "evidence": "Henry: follow up on rollout",
            }
        ]
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post("/api/v4/capture", json={"content": "Henry should follow up on rollout"})

    assert response.status_code == 201
    data = response.get_json()
    assert not any(
        change["type"] == "entity_created" and change["entity_type"] == "person" and change["title"] == "Henry"
        for change in data["applied_changes"]
    )

    with app.app_context():
        task = Entity.query.filter_by(type="task", title="Follow up on rollout").one()
        assert Entity.query.filter_by(type="person", title="Henry").count() == 1
        EntityLink.query.filter_by(
            source_entity_id=task.id,
            target_entity_id=person_id,
            relationship_type="assigned_to",
        ).one()
        assert EntityEvent.query.filter_by(entity_id=person_id, event_type="created").count() == 0


def test_capture_auto_creates_high_confidence_person(client, app):
    extraction = {
        "entities": [
            {
                "type": "person",
                "title": "Henry",
                "confidence": 0.91,
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


def test_capture_suggests_entity_below_auto_create_threshold(client, app):
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
    assert data["applied_changes"] == []
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["suggestion_type"] == "create_person"

    with app.app_context():
        assert Entity.query.filter_by(type="person").count() == 0
        assert AiSuggestion.query.filter_by(suggestion_type="create_person").count() == 1


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


def test_capture_uses_reconciliation_confidence_for_auto_apply_gate(client, app):
    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Follow up on rollout",
                "content": "Ask Henry for rollout status.",
                "confidence": 0.95,
                "evidence": "ask Henry about rollout",
            }
        ]
    }
    decisions = [
        {
            "action": "new",
            "target_id": None,
            "fields": {},
            "relationship_type": "derived_from",
            "confidence": 0.42,
            "reason": "match confidence is too low for auto-apply",
        }
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates",
        return_value=decisions,
    ):
        response = client.post("/api/v4/capture", json={"content": "Need to ask Henry about rollout"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["applied_changes"] == []
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["operation_type"] == "create_entity"
    assert data["suggestions"][0]["confidence"] == 0.42

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
        "intent": "follow_up",
        "intent_confidence": 0.94,
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
    assert data["source_note"]["ai"]["intent"] == "follow_up"
    assert data["source_note"]["ai"]["intent_confidence"] == 0.94
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


def test_ai_generated_title_replaces_placeholder_and_writes_event(client, app):
    """Regression: ai_title_set used a disallowed event_type and broke capture.

    When no user title is supplied and extraction returns a title, the note's
    placeholder title should be replaced, ai_meta.title_auto stays True, and
    an ai_updated event with reason='ai_title_set' is written without
    violating entity_events_event_type_check.
    """
    extraction = {
        "title": "Resolve observability pipeline for agent telemetry",
        "summary": "Notes on the observability work for the agent telemetry stack.",
        "confidence": 0.9,
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post(
            "/api/v4/capture",
            json={"content": "Need to sort out the observability pipeline with Sai to make sure agent telemetry flows."},
        )

    assert response.status_code == 201, response.get_json()
    data = response.get_json()
    assert data["warnings"] == []
    title_change = next((c for c in data["applied_changes"] if c["type"] == "title_updated"), None)
    assert title_change is not None
    assert title_change["title"] == "Resolve observability pipeline for agent telemetry"

    note_id = data["source_note"]["id"]
    with app.app_context():
        from extensions import db
        note = db.session.get(Entity, note_id)
        assert note.title == "Resolve observability pipeline for agent telemetry"
        assert (note.ai_meta or {}).get("title_auto") is True

        events = EntityEvent.query.filter_by(entity_id=note_id).all()
        title_event = next(
            (e for e in events if e.actor == "agent:v4-capture" and e.reason == "ai_title_set"),
            None,
        )
        assert title_event is not None, "expected ai_updated event with reason=ai_title_set"
        assert title_event.event_type == "ai_updated"
        assert title_event.new_value["title"] == "Resolve observability pipeline for agent telemetry"


def test_duplicate_candidates_within_capture_are_deduped(client, app):
    """Regression: model emits the same entity in both `links` and `entities`
    arrays (or twice in one of them); without dedup we'd create / link it
    twice in the same capture."""
    extraction = {
        "links": [
            {
                "target_type": "person",
                "title": "Tomoko Watanabe",
                "relationship_type": "mentions",
                "confidence": 0.92,
                "evidence": "Tomoko Watanabe will draft the RFC",
            },
        ],
        "entities": [
            {
                "type": "person",
                "title": "Tomoko Watanabe",
                "confidence": 0.92,
                "evidence": "Tomoko Watanabe will draft the RFC",
            },
            {
                "type": "person",
                "title": "tomoko watanabe",
                "confidence": 0.88,
                "evidence": "mentioned again later",
            },
        ],
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post(
            "/api/v4/capture",
            json={"content": "Working with Tomoko Watanabe on the RFC. Tomoko will draft it."},
        )

    assert response.status_code == 201
    data = response.get_json()
    person_creates = [c for c in data["applied_changes"] if c.get("entity_type") == "person"]
    assert len(person_creates) == 1, f"expected 1 person create, got {len(person_creates)}: {person_creates}"

    with app.app_context():
        assert Entity.query.filter_by(type="person").count() == 1


def test_exact_duplicate_capture_is_skipped_without_reprocessing(client, app):
    first = client.post(
        "/api/v4/capture",
        json={"content": "Need to ask Henry about rollout"},
    )
    assert first.status_code == 201
    first_note_id = first.get_json()["source_note"]["id"]

    with patch("services.v4_extraction.extract_capture_candidates") as extract_mock:
        second = client.post(
            "/api/v4/capture",
            json={"content": "Need to ask Henry about rollout"},
        )

    assert second.status_code == 200
    data = second.get_json()
    assert data["skipped"] is True
    assert data["reason"] == "exact duplicate"
    assert data["source_note"]["id"] == first_note_id
    assert data["applied_changes"] == []
    assert data["suggestions"] == []
    extract_mock.assert_not_called()

    with app.app_context():
        assert Entity.query.filter_by(type="note").count() == 1


def test_user_supplied_title_is_not_overwritten_by_ai(client, app):
    """When the user supplies a title on capture, AI title is ignored."""
    extraction = {
        "title": "AI would have called this something else",
        "summary": "summary",
        "confidence": 0.9,
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post(
            "/api/v4/capture",
            json={"title": "My own title", "content": "Body of the note."},
        )

    assert response.status_code == 201
    note_id = response.get_json()["source_note"]["id"]
    with app.app_context():
        from extensions import db
        note = db.session.get(Entity, note_id)
        assert note.title == "My own title"
        assert (note.ai_meta or {}).get("title_auto") is False


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


def test_capture_without_openai_key_reuses_exact_existing_entity_instead_of_creating_duplicate(client, app):
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
                "confidence": 0.95,
                "evidence": "Memory Lookup rollout note",
            }
        ]
    }

    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), patch(
        "services.v4_extraction.extract_capture_candidates",
        return_value=extraction,
    ), patch(
        "services.embeddings.embed_query",
        return_value=None,
    ):
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

    with app.app_context():
        assert Entity.query.filter_by(type="project", title="Memory Lookup").count() == 1
        EntityLink.query.filter_by(
            source_entity_id=note_id,
            target_entity_id=project_id,
            relationship_type="related",
        ).one()


def test_capture_without_ai_extracts_heuristic_follow_up_intent(client):
    response = client.post("/api/v4/capture", json={"content": "Follow up with Henry next week about rollout"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["source_note"]["ai"]["intent"] == "follow_up"
    assert data["source_note"]["ai"]["intent_confidence"] > 0


def test_junk_intent_suppresses_low_value_suggestions(client, app):
    extraction = {
        "intent": "junk",
        "intent_confidence": 0.92,
        "entities": [
            {
                "type": "task",
                "title": "Maybe follow up",
                "confidence": 0.55,
                "evidence": "possibly",
            }
        ],
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post("/api/v4/capture", json={"content": "asdf"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["source_note"]["ai"]["intent"] == "junk"
    assert data["suggestions"] == []

    with app.app_context():
        assert Entity.query.filter_by(type="task").count() == 0
        assert AiSuggestion.query.count() == 0


def test_reference_intent_suppresses_low_confidence_task_suggestions(client, app):
    extraction = {
        "intent": "reference",
        "intent_confidence": 0.9,
        "entities": [
            {
                "type": "task",
                "title": "Review rollout doc",
                "confidence": 0.58,
                "evidence": "doc mentions review",
            }
        ],
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post("/api/v4/capture", json={"content": "Reference doc for rollout"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["source_note"]["ai"]["intent"] == "reference"
    assert data["suggestions"] == []

    with app.app_context():
        assert Entity.query.filter_by(type="task").count() == 0
        assert AiSuggestion.query.count() == 0


def test_capture_reuses_existing_pending_suggestion_instead_of_creating_duplicate(client, app):
    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Follow up with Henry",
                "confidence": 0.55,
                "evidence": "follow up with Henry",
            }
        ]
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        first = client.post("/api/v4/capture", json={"content": "Follow up with Henry"})
        second = client.post("/api/v4/capture", json={"content": "Follow up with Henry again tomorrow"})

    assert first.status_code == 201
    assert second.status_code == 201
    assert len(first.get_json()["suggestions"]) == 1
    assert second.get_json()["suggestions"] == []

    with app.app_context():
        assert AiSuggestion.query.filter_by(suggestion_type="create_task", status="pending").count() == 1


def test_capture_suppresses_recently_dismissed_duplicate_suggestion(client, app):
    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Follow up with Henry",
                "confidence": 0.55,
                "evidence": "follow up with Henry",
            }
        ]
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        first = client.post("/api/v4/capture", json={"content": "Follow up with Henry"})
    suggestion_id = first.get_json()["suggestions"][0]["id"]

    dismiss = client.post(f"/api/v4/suggestions/{suggestion_id}/dismiss")
    assert dismiss.status_code == 200

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        second = client.post("/api/v4/capture", json={"content": "Follow up with Henry again"})

    assert second.status_code == 201
    assert second.get_json()["suggestions"] == []

    with app.app_context():
        assert AiSuggestion.query.filter_by(suggestion_type="create_task").count() == 1
