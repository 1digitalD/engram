"""Tests for v4 capture extraction and auto-apply behavior."""

import os
from unittest.mock import patch

from extensions import db
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


def test_capture_suppresses_tentative_low_value_task(client, app):
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
    assert data["suggestions"] == []

    with app.app_context():
        assert Entity.query.filter_by(type="task").count() == 0
        assert AiSuggestion.query.filter_by(suggestion_type="create_task").count() == 0


def test_capture_near_duplicate_task_routes_to_suggestion(client, app):
    """A high-confidence "new" task with a strong similarity match is suggested,
    not auto-created — duplicates are worse than an extra review item."""
    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Ship the rollout plan",
                "confidence": 0.95,
                "evidence": "ship the rollout plan",
            }
        ]
    }
    decisions = [
        {
            "action": "new",
            "target_id": None,
            "fields": {},
            "relationship_type": "derived_from",
            "confidence": 0.95,
            "reason": "model voted new despite near-match",
            "top_match_score": 0.82,
            "top_match_id": "existing-task-id",
            "top_match_title": "Ship rollout plan",
        }
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), \
         patch("services.v4_reconciliation.reconcile_candidates", return_value=decisions):
        response = client.post("/api/v4/capture", json={"content": "Ship the rollout plan"})

    assert response.status_code == 201
    data = response.get_json()
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["suggestion_type"] == "create_task"

    with app.app_context():
        assert Entity.query.filter_by(type="task").count() == 0
        suggestion = AiSuggestion.query.filter_by(suggestion_type="create_task").one()
        assert suggestion.payload["near_match"]["title"] == "Ship rollout plan"
        assert suggestion.payload["near_match"]["score"] == 0.82


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


def test_capture_drops_new_project_link_candidate_with_no_near_match(client, app):
    """Project creation is never auto-applied, and a "new project" decision with
    no plausible existing match is dropped silently rather than queued as a
    create_project suggestion (these have a 0% historical acceptance rate)."""
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
    assert not any(c["type"] == "entity_created" for c in data["applied_changes"])

    with app.app_context():
        assert Entity.query.filter_by(type="project", title="Memory Lookup").count() == 0
        assert AiSuggestion.query.filter_by(suggestion_type="create_project").count() == 0


def test_capture_redirects_new_project_to_link_existing_when_near_match(client, app):
    """A "new project" decision with a plausible near-duplicate existing project
    becomes a link_existing suggestion instead of a create_project suggestion."""
    existing = Entity(type="project", title="Memory Lookup v2", lifecycle="active", status="active")
    with app.app_context():
        db.session.add(existing)
        db.session.commit()
        existing_id = existing.id

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
    decisions = [
        {
            "action": "new",
            "target_id": None,
            "fields": {},
            "relationship_type": "related",
            "confidence": 0.92,
            "reason": "looks new",
            "top_match_score": 0.81,
            "top_match_id": existing_id,
            "top_match_title": "Memory Lookup v2",
        }
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates",
        return_value=decisions,
    ):
        response = client.post("/api/v4/capture", json={"content": "Ask Henry about Memory Lookup"})

    assert response.status_code == 201
    data = response.get_json()
    assert len(data["suggestions"]) == 1
    assert data["suggestions"][0]["suggestion_type"] == "link_existing"
    assert data["suggestions"][0]["payload"]["target_entity_id"] == existing_id

    with app.app_context():
        assert Entity.query.filter_by(type="project", title="Memory Lookup").count() == 0
        assert AiSuggestion.query.filter_by(suggestion_type="create_project").count() == 0


def test_capture_drops_low_confidence_missing_project_link(client, app):
    """When a link candidate references a non-existent project at low confidence
    with no near match, nothing is queued (no create_project suggestion)."""
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
    assert data["suggestions"] == []

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
    decisions = [
        {
            "action": "link",
            "target_id": project_id,
            "fields": {},
            "relationship_type": "related",
            "confidence": 0.95,
            "reason": "existing project, medium confidence",
        },
        {
            "action": "link",
            "target_id": person_id,
            "fields": {},
            "relationship_type": "mentions",
            "confidence": 0.92,
            "reason": "existing person",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
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


def test_capture_auto_created_task_links_to_source_note_projects(client, app):
    """Tasks auto-created from a note should get parent links to any
    projects the source note is already linked to.

    This is the critical path that turns extracted tasks into visible
    children of their projects, fixing project task_counts and the
    project detail 'Open Tasks' section."""
    project = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "Memory Lookup"},
    ).get_json()["data"]

    extraction = {
        "links": [
            {
                "target_type": "project",
                "title": "Memory Lookup",
                "relationship_type": "related",
                "confidence": 0.95,
                "evidence": "Memory Lookup is the project",
            }
        ],
        "entities": [
            {
                "type": "task",
                "title": "Follow up on Memory Lookup rollout",
                "confidence": 0.91,
                "evidence": "need to follow up",
            }
        ],
    }
    decisions = [
        {
            "action": "link",
            "target_id": project["id"],
            "relationship_type": "related",
            "reason": "Matches the existing project already named in the note.",
        },
        {
            "action": "new",
            "relationship_type": "derived_from",
            "reason": "This is a concrete follow-up task extracted from the note.",
        },
    ]

    with (
        patch("services.v4_extraction.extract_capture_candidates", return_value=extraction),
        patch("services.v4_reconciliation.reconcile_candidates", return_value=decisions),
    ):
        response = client.post(
            "/api/v4/capture",
            json={"content": "Follow up on Memory Lookup rollout"},
        )

    assert response.status_code == 201
    data = response.get_json()
    note_id = data["source_note"]["id"]

    # Task should be auto-created
    task_created = next(
        (c for c in data["applied_changes"] if c["type"] == "entity_created" and c["entity_type"] == "task"),
        None,
    )
    assert task_created is not None, "expected task to be auto-created"
    task_id = task_created["entity_id"]

    with app.app_context():
        # Task → note (derived_from) — preserved for provenance
        note_link = EntityLink.query.filter_by(
            source_entity_id=task_id,
            target_entity_id=note_id,
            relationship_type="derived_from",
        ).first()
        assert note_link is not None, "task must have derived_from link to source note"

        # Task → project (parent) — this is the new behavior
        parent_link = EntityLink.query.filter_by(
            source_entity_id=task_id,
            target_entity_id=project["id"],
            relationship_type="parent",
        ).first()
        assert parent_link is not None, "task must have parent link to project"

        # Project detail should show the task in open_tasks
        detail = client.get(f"/api/v4/entities/{project['id']}/detail")
        sections = {s["key"]: s for s in detail.get_json()["sections"]}
        open_tasks = sections["open_tasks"]["items"]
        assert len(open_tasks) == 1
        assert open_tasks[0]["entity"]["id"] == task_id
        assert open_tasks[0]["entity"]["title"] == "Follow up on Memory Lookup rollout"

        # Note detail should still show the task in derived_tasks
        note_detail = client.get(f"/api/v4/entities/{note_id}/detail")
        note_sections = {s["key"]: s for s in note_detail.get_json()["sections"]}
        derived = note_sections["derived_tasks"]["items"]
        assert len(derived) == 1
        assert derived[0]["entity"]["id"] == task_id


def test_capture_applies_progress_update_decisions_to_existing_entities(client, app):
    project_response = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "Agent Platform", "content": "Project"},
    )
    person_response = client.post(
        "/api/v4/entities",
        json={"type": "person", "title": "Akash", "content": "Person"},
    )
    project_id = project_response.get_json()["data"]["id"]
    person_id = person_response.get_json()["data"]["id"]

    extraction = {
        "entities": [
            {
                "type": "project",
                "title": "Agent Platform",
                "content": "Shipped the HITL piece",
                "confidence": 0.9,
                "evidence": "Shipped the HITL piece for Agent Platform",
            },
            {
                "type": "person",
                "title": "Akash",
                "content": "Still waiting on infra",
                "confidence": 0.9,
                "evidence": "Akash is still waiting on infra",
            },
        ]
    }
    decisions = [
        {
            "action": "progress_update",
            "target_id": project_id,
            "update_text": "Shipped the HITL piece",
            "confidence": 0.92,
            "reason": "progress on Agent Platform",
        },
        {
            "action": "progress_update",
            "target_id": person_id,
            "update_text": "Still waiting on infra",
            "confidence": 0.9,
            "reason": "status update for Akash",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": "Standup notes"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["suggestions"] == []

    activity_changes = [c for c in data["applied_changes"] if c["type"] == "activity_update_added"]
    assert {c["target_entity_id"] for c in activity_changes} == {project_id, person_id}

    with app.app_context():
        # No new project/task entities created.
        assert Entity.query.filter_by(type="project").count() == 1
        assert Entity.query.filter_by(type="person").count() == 1

    project_updates = client.get(f"/api/v4/entities/{project_id}/activity_updates").get_json()["data"]
    assert any(u["content"] == "Shipped the HITL piece" for u in project_updates)

    person_updates = client.get(f"/api/v4/entities/{person_id}/activity_updates").get_json()["data"]
    assert any(u["content"] == "Still waiting on infra" for u in person_updates)


def test_capture_progress_update_with_hallucinated_target_is_skipped(client, app):
    extraction = {
        "entities": [
            {
                "type": "project",
                "title": "Ghost Project",
                "content": "Some progress",
                "confidence": 0.9,
                "evidence": "progress on Ghost Project",
            },
        ]
    }
    decisions = [
        {
            "action": "progress_update",
            "target_id": "00000000-0000-0000-0000-000000000000",
            "update_text": "Some progress",
            "confidence": 0.9,
            "reason": "progress update",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": "Standup notes"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["suggestions"] == []
    assert all(c["type"] != "activity_update_added" for c in data["applied_changes"])

    with app.app_context():
        # No new project entity created from a hallucinated progress_update target.
        assert Entity.query.filter_by(type="project").count() == 0


def test_capture_progress_update_dedups_within_24h(client, app):
    project_response = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "Agent Platform", "content": "Project"},
    )
    project_id = project_response.get_json()["data"]["id"]

    extraction = {
        "entities": [
            {
                "type": "project",
                "title": "Agent Platform",
                "content": "Shipped the HITL piece",
                "confidence": 0.9,
                "evidence": "Shipped the HITL piece for Agent Platform",
            },
        ]
    }
    decisions = [
        {
            "action": "progress_update",
            "target_id": project_id,
            "update_text": "Shipped the HITL piece",
            "confidence": 0.92,
            "reason": "progress on Agent Platform",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        client.post("/api/v4/capture", json={"content": "Standup notes 1"})
        client.post("/api/v4/capture", json={"content": "Standup notes 2"})

    updates = client.get(f"/api/v4/entities/{project_id}/activity_updates").get_json()["data"]
    matching = [u for u in updates if u["content"] == "Shipped the HITL piece"]
    assert len(matching) == 1


def test_capture_progress_update_with_high_confidence_status_auto_applies(client, app):
    task_response = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Build HITL piece", "content": "Task"},
    )
    task_id = task_response.get_json()["data"]["id"]

    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Build HITL piece",
                "content": "Shipped the HITL piece",
                "confidence": 0.9,
                "evidence": "Shipped the HITL piece",
            },
        ]
    }
    decisions = [
        {
            "action": "progress_update",
            "target_id": task_id,
            "update_text": "Shipped the HITL piece",
            "fields": {"status": "done"},
            "confidence": 0.92,
            "reason": "task delivered",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": "Standup notes"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["suggestions"] == []

    activity_changes = [c for c in data["applied_changes"] if c["type"] == "activity_update_added"]
    assert len(activity_changes) == 1

    status_changes = [c for c in data["applied_changes"] if c["type"] == "entity_updated"]
    assert status_changes == [
        {
            "type": "entity_updated",
            "entity_id": task_id,
            "entity_type": "task",
            "title": "Build HITL piece",
            "changes": {"status": "done"},
        }
    ]

    with app.app_context():
        from extensions import db
        task = db.session.get(Entity, task_id)
        assert task.status == "done"

        event = (
            EntityEvent.query.filter_by(entity_id=task_id, event_type="ai_updated")
            .order_by(EntityEvent.created_at.desc())
            .first()
        )
        assert event is not None
        assert event.old_value == {"status": "open"}
        assert event.new_value == {"status": "done"}


def test_capture_progress_update_with_low_confidence_status_becomes_suggestion(client, app):
    task_response = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Build infra", "content": "Task"},
    )
    task_id = task_response.get_json()["data"]["id"]

    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Build infra",
                "content": "Still waiting on infra",
                "confidence": 0.6,
                "evidence": "Still waiting on infra",
            },
        ]
    }
    decisions = [
        {
            "action": "progress_update",
            "target_id": task_id,
            "update_text": "Still waiting on infra",
            "fields": {"status": "waiting"},
            "confidence": 0.5,
            "reason": "possible status change",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": "Standup notes"})

    assert response.status_code == 201
    data = response.get_json()

    # Activity update is additive/safe — still applied even at low confidence.
    activity_changes = [c for c in data["applied_changes"] if c["type"] == "activity_update_added"]
    assert len(activity_changes) == 1

    # Status change is not auto-applied below the confidence gate.
    assert all(c["type"] != "entity_updated" for c in data["applied_changes"])

    assert len(data["suggestions"]) == 1
    suggestion = data["suggestions"][0]
    assert suggestion["operation_type"] == "update_entity"
    assert suggestion["payload"]["target_entity_id"] == task_id
    assert suggestion["payload"]["fields"] == {"status": "waiting"}

    with app.app_context():
        from extensions import db
        task = db.session.get(Entity, task_id)
        assert task.status == "open"


def test_capture_progress_update_with_invalid_status_is_ignored(client, app):
    task_response = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Build infra", "content": "Task"},
    )
    task_id = task_response.get_json()["data"]["id"]

    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Build infra",
                "content": "Some progress",
                "confidence": 0.9,
                "evidence": "Some progress",
            },
        ]
    }
    decisions = [
        {
            "action": "progress_update",
            "target_id": task_id,
            "update_text": "Some progress",
            "fields": {"status": "not_a_real_status"},
            "confidence": 0.95,
            "reason": "progress note",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": "Standup notes"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["suggestions"] == []
    assert all(c["type"] != "entity_updated" for c in data["applied_changes"])

    with app.app_context():
        from extensions import db
        task = db.session.get(Entity, task_id)
        assert task.status == "open"


def test_capture_progress_update_blocked_status_creates_blocks_link(client, app):
    blocked_response = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Ship rollout memo", "content": "Task"},
    )
    blocked_id = blocked_response.get_json()["data"]["id"]

    blocker_response = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Finalize API contract", "content": "Task"},
    )
    blocker_id = blocker_response.get_json()["data"]["id"]

    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Ship rollout memo",
                "content": "Still blocked on the API contract",
                "confidence": 0.9,
                "evidence": "Still blocked on the API contract",
            },
        ]
    }
    decisions = [
        {
            "action": "progress_update",
            "target_id": blocked_id,
            "update_text": "Still blocked on the API contract",
            "fields": {"status": "blocked"},
            "blocked_by_id": blocker_id,
            "confidence": 0.92,
            "reason": "blocked on API contract",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": "Standup notes"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["suggestions"] == []

    link_changes = [c for c in data["applied_changes"] if c["type"] == "relationship_added"]
    assert any(
        c["source_entity_id"] == blocker_id
        and c["target_entity_id"] == blocked_id
        and c["relationship_type"] == "blocks"
        for c in link_changes
    )

    with app.app_context():
        from extensions import db
        task = db.session.get(Entity, blocked_id)
        assert task.status == "blocked"

        link = EntityLink.query.filter_by(
            source_entity_id=blocker_id,
            target_entity_id=blocked_id,
            relationship_type="blocks",
        ).one()
        assert link is not None


def test_capture_progress_update_escalation_creates_priority_suggestion(client, app):
    task_response = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Fix prod outage", "content": "Task"},
    )
    task_id = task_response.get_json()["data"]["id"]

    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Fix prod outage",
                "content": "This is now urgent, escalating",
                "confidence": 0.9,
                "evidence": "This is now urgent, escalating",
            },
        ]
    }
    decisions = [
        {
            "action": "progress_update",
            "target_id": task_id,
            "update_text": "Escalated to urgent",
            "fields": {"priority": "urgent"},
            "confidence": 0.95,
            "reason": "escalation language detected",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": "Standup notes"})

    assert response.status_code == 201
    data = response.get_json()

    # Activity update is applied, but the priority change is never auto-applied.
    activity_changes = [c for c in data["applied_changes"] if c["type"] == "activity_update_added"]
    assert len(activity_changes) == 1
    assert all(c["type"] != "entity_updated" for c in data["applied_changes"])

    assert len(data["suggestions"]) == 1
    suggestion = data["suggestions"][0]
    assert suggestion["operation_type"] == "update_entity"
    assert suggestion["payload"]["target_entity_id"] == task_id
    assert suggestion["payload"]["fields"] == {"priority": "urgent"}

    with app.app_context():
        from extensions import db
        task = db.session.get(Entity, task_id)
        assert (task.properties or {}).get("priority") is None


def test_capture_progress_update_no_escalation_below_current_priority(client, app):
    task_response = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Polish docs", "content": "Task", "properties": {"priority": "high"}},
    )
    task_id = task_response.get_json()["data"]["id"]

    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Polish docs",
                "content": "Made some progress on this",
                "confidence": 0.9,
                "evidence": "Made some progress on this",
            },
        ]
    }
    decisions = [
        {
            "action": "progress_update",
            "target_id": task_id,
            "update_text": "Made progress",
            "fields": {"priority": "low"},
            "confidence": 0.95,
            "reason": "no escalation",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": "Standup notes"})

    assert response.status_code == 201
    data = response.get_json()
    assert data["suggestions"] == []


def test_capture_changes_lists_agent_applied_changes_for_note(client, app):
    task_response = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Build HITL piece", "content": "Task"},
    )
    task_id = task_response.get_json()["data"]["id"]

    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Build HITL piece",
                "content": "Shipped the HITL piece",
                "confidence": 0.9,
                "evidence": "Shipped the HITL piece",
            },
        ]
    }
    decisions = [
        {
            "action": "progress_update",
            "target_id": task_id,
            "update_text": "Shipped the HITL piece",
            "fields": {"status": "done"},
            "confidence": 0.92,
            "reason": "task delivered",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": "Standup notes"})

    note_id = response.get_json()["source_note"]["id"]

    changes_response = client.get(f"/api/v4/entities/{note_id}/capture-changes")
    assert changes_response.status_code == 200
    events = changes_response.get_json()["data"]

    event_types = {e["event_type"] for e in events}
    assert "ai_updated" in event_types
    assert "activity_update_added" in event_types
    for e in events:
        assert e["actor"] == "agent:v4-capture"
        assert e["reverted_at"] is None


def test_revert_ai_updated_status_change_restores_old_status(client, app):
    task_response = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Build HITL piece", "content": "Task"},
    )
    task_id = task_response.get_json()["data"]["id"]

    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Build HITL piece",
                "content": "Shipped the HITL piece",
                "confidence": 0.9,
                "evidence": "Shipped the HITL piece",
            },
        ]
    }
    decisions = [
        {
            "action": "progress_update",
            "target_id": task_id,
            "update_text": "Shipped the HITL piece",
            "fields": {"status": "done"},
            "confidence": 0.92,
            "reason": "task delivered",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": "Standup notes"})

    note_id = response.get_json()["source_note"]["id"]

    with app.app_context():
        from extensions import db
        event = (
            EntityEvent.query.filter_by(entity_id=task_id, event_type="ai_updated")
            .order_by(EntityEvent.created_at.desc())
            .first()
        )
        event_id = event.id

    revert_response = client.post(f"/api/v4/events/{event_id}/revert")
    assert revert_response.status_code == 200

    with app.app_context():
        from extensions import db
        task = db.session.get(Entity, task_id)
        assert task.status == "open"

        reverted_event = db.session.get(EntityEvent, event_id)
        assert reverted_event.reverted_at is not None

        revert_log = (
            EntityEvent.query.filter_by(entity_id=task_id, event_type="reverted")
            .order_by(EntityEvent.created_at.desc())
            .first()
        )
        assert revert_log is not None
        assert revert_log.old_value == {"status": "done"}
        assert revert_log.new_value == {"status": "open"}

    # Reverting again is rejected
    second_response = client.post(f"/api/v4/events/{event_id}/revert")
    assert second_response.status_code == 409


def test_revert_activity_update_archives_note(client, app):
    project_response = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "Agent Platform", "content": "Project"},
    )
    project_id = project_response.get_json()["data"]["id"]

    extraction = {
        "entities": [
            {
                "type": "project",
                "title": "Agent Platform",
                "content": "Made progress",
                "confidence": 0.9,
                "evidence": "Made progress on Agent Platform",
            },
        ]
    }
    decisions = [
        {
            "action": "progress_update",
            "target_id": project_id,
            "update_text": "Made progress",
            "confidence": 0.92,
            "reason": "progress update",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        client.post("/api/v4/capture", json={"content": "Standup notes"})

    with app.app_context():
        from extensions import db
        event = (
            EntityEvent.query.filter_by(entity_id=project_id, event_type="activity_update_added")
            .order_by(EntityEvent.created_at.desc())
            .first()
        )
        event_id = event.id
        au_note_id = event.new_value["note_id"]

    revert_response = client.post(f"/api/v4/events/{event_id}/revert")
    assert revert_response.status_code == 200

    with app.app_context():
        from extensions import db
        au_note = db.session.get(Entity, au_note_id)
        assert au_note.lifecycle == "archived"


def test_revert_relationship_added_removes_link(client, app):
    project_response = client.post(
        "/api/v4/entities",
        json={"type": "project", "title": "Agent Platform", "content": "Project"},
    )
    project_id = project_response.get_json()["data"]["id"]

    extraction = {
        "entities": [
            {
                "type": "project",
                "title": "Agent Platform",
                "content": "Related discussion",
                "confidence": 0.9,
                "evidence": "Discussed Agent Platform",
            },
        ]
    }
    decisions = [
        {
            "action": "link",
            "target_id": project_id,
            "relationship_type": "related",
            "confidence": 0.92,
            "reason": "mentions Agent Platform",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": "Standup notes"})

    note_id = response.get_json()["source_note"]["id"]

    with app.app_context():
        from extensions import db
        event = (
            EntityEvent.query.filter_by(entity_id=note_id, event_type="relationship_added")
            .order_by(EntityEvent.created_at.desc())
            .first()
        )
        event_id = event.id
        link_id = event.new_value["id"]

    revert_response = client.post(f"/api/v4/events/{event_id}/revert")
    assert revert_response.status_code == 200

    with app.app_context():
        from extensions import db
        link = db.session.get(EntityLink, link_id)
        assert link is None


def test_revert_created_entity_marks_lifecycle_deleted(client, app):
    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Write release notes",
                "content": "Need to write release notes",
                "confidence": 0.9,
                "evidence": "Need to write release notes",
            },
        ]
    }
    decisions = [
        {
            "action": "new",
            "confidence": 0.95,
            "reason": "new task",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": "Standup notes"})

    data = response.get_json()
    created = [c for c in data["applied_changes"] if c["type"] == "entity_created"]
    assert len(created) == 1
    task_id = created[0]["entity_id"]

    with app.app_context():
        from extensions import db
        event = (
            EntityEvent.query.filter_by(entity_id=task_id, event_type="created")
            .order_by(EntityEvent.created_at.desc())
            .first()
        )
        event_id = event.id

    revert_response = client.post(f"/api/v4/events/{event_id}/revert")
    assert revert_response.status_code == 200

    with app.app_context():
        from extensions import db
        task = db.session.get(Entity, task_id)
        assert task.lifecycle == "deleted"


def test_revert_unknown_event_returns_404(client, app):
    response = client.post("/api/v4/events/does-not-exist/revert")
    assert response.status_code == 404


def test_capture_assigns_delegation_sets_follow_up_at_cadence(client, app):
    from datetime import datetime, timezone
    from api.v4_entities import _add_working_days, _delegation_cadence_days

    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Design GTM trigger doc",
                "content": "Akash: design GTM trigger doc",
                "assigned_to": "Akash",
                "confidence": 0.91,
                "evidence": "Akash: design GTM trigger doc",
            }
        ]
    }

    before = datetime.now(timezone.utc)
    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post("/api/v4/capture", json={"content": "Akash: design GTM trigger doc"})

    assert response.status_code == 201

    with app.app_context():
        task = Entity.query.filter_by(type="task", title="Design GTM trigger doc").one()
        assert task.follow_up_at is not None
        expected = _add_working_days(before, _delegation_cadence_days())
        assert abs((task.follow_up_at - expected).total_seconds()) < 60
        assert EntityEvent.query.filter_by(entity_id=task.id, event_type="ai_updated").count() >= 1


def test_capture_does_not_set_cadence_for_owner_assignee(client, app):
    extraction = {
        "entities": [
            {
                "type": "task",
                "title": "Review budget",
                "content": "Dan: review budget",
                "assigned_to": "Dan",
                "confidence": 0.91,
                "evidence": "Dan: review budget",
            }
        ]
    }

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction):
        response = client.post("/api/v4/capture", json={"content": "Dan: review budget"})

    assert response.status_code == 201

    with app.app_context():
        task = Entity.query.filter_by(type="task", title="Review budget").one()
        assert task.follow_up_at is None


def test_activity_update_refreshes_delegation_follow_up_at(client, app):
    from datetime import datetime, timezone
    from extensions import db
    from api.v4_entities import _add_working_days, _delegation_cadence_days

    with app.app_context():
        person = Entity(
            type="person", title="Akash", content=None, status="active", lifecycle="active",
            source="user", properties={}, ai_meta={}, ai_status="pending",
        )
        db.session.add(person)
        db.session.flush()
        task = Entity(
            type="task", title="Design GTM trigger doc", content=None, status="open", lifecycle="active",
            source="user", properties={}, ai_meta={}, ai_status="pending",
            follow_up_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        db.session.add(task)
        db.session.flush()
        link = EntityLink(
            source_entity_id=task.id,
            target_entity_id=person.id,
            relationship_type="assigned_to",
            source="user",
        )
        db.session.add(link)
        db.session.commit()
        task_id = task.id

    before = datetime.now(timezone.utc)
    response = client.post(
        f"/api/v4/entities/{task_id}/activity_updates",
        json={"content": "Akash shared the first draft of the GTM trigger doc"},
    )
    assert response.status_code == 201

    with app.app_context():
        task = db.session.get(Entity, task_id)
        expected = _add_working_days(before, _delegation_cadence_days())
        assert abs((task.follow_up_at - expected).total_seconds()) < 60
        assert EntityEvent.query.filter_by(entity_id=task_id, event_type="ai_updated").count() >= 1


def test_extraction_prompt_includes_recent_context_excluding_current_note(client, app):
    """The extraction system prompt carries recent notes for situational
    awareness, but never the note being processed."""
    from services.v4_extraction import _build_system_prompt

    older = client.post("/api/v4/capture", json={"content": "GTM agent trigger still flaky after retry fix"}).get_json()["source_note"]
    current = client.post("/api/v4/capture", json={"content": "same issue as yesterday, still flaky"}).get_json()["source_note"]

    with app.app_context():
        prompt = _build_system_prompt(exclude_note_id=current["id"])

    assert "RECENT_CONTEXT" in prompt
    assert "GTM agent trigger still flaky" in prompt
    assert "same issue as yesterday" not in prompt
    assert "Do NOT extract" in prompt
