"""Tests for SQ-05 intent-routed capture and SQ-06 thread-attached unification.

Captures whose extraction reports intent=update/follow_up (confidence >= 0.7)
route through activity-update semantics instead of full entity-extraction
reconciliation; junk intent skips reconciliation entirely; everything else is
unchanged.
"""

import json
from unittest.mock import patch

from extensions import db
from models import AiSuggestion, Entity


def _create_entity(client, entity_type, title, content=None):
    response = client.post(
        "/api/v4/entities",
        json={"type": entity_type, "title": title, "content": content or title},
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def _parse_capture_sse_events(response_data):
    events = []
    for block in response_data.decode().strip().split("\n\n"):
        if not block.strip():
            continue
        event_type = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if event_type is not None:
            events.append((event_type, data))
    return events


UPDATE_EXTRACTION = {
    "summary": "Task can be closed.",
    "intent": "update",
    "intent_confidence": 0.9,
    "confidence": 0.9,
}


def test_update_intent_with_thread_id_closes_target(client, app):
    """Scenario 1: update intent + thread attachment applies status to target."""
    task = _create_entity(client, "task", "Ship parser fix")

    au_extraction = {"status": "done", "confidence": 0.9, "follow_up_at": None, "tasks": []}

    with patch(
        "services.v4_extraction.extract_capture_candidates",
        return_value=UPDATE_EXTRACTION,
    ), patch(
        "services.v4_extraction.extract_dates_and_tasks_from_update",
        return_value=au_extraction,
    ), patch(
        "services.v4_reconciliation.reconcile_candidates"
    ) as mock_reconcile:
        response = client.post(
            "/api/v4/capture",
            json={
                "content": "Talked to the design partners. We can close this task now.",
                "thread_id": task["id"],
            },
        )

    assert response.status_code == 201
    data = response.get_json()
    mock_reconcile.assert_not_called()

    with app.app_context():
        entity = db.session.get(Entity, task["id"])
        assert entity.status == "done"

    change_types = [change["type"] for change in data["applied_changes"]]
    assert "activity_update_added" in change_types
    status_changes = [
        c for c in data["applied_changes"]
        if c["type"] == "entity_updated" and c.get("changes", {}).get("status") == "done"
    ]
    assert len(status_changes) == 1
    assert status_changes[0]["entity_id"] == task["id"]
    assert all(s["suggestion_type"] != "create_task" for s in data["suggestions"])

    updates = client.get(f"/api/v4/entities/{task['id']}/activity_updates").get_json()["data"]
    assert len(updates) == 1


def test_update_intent_unresolved_creates_single_suggestion(client, app):
    """Scenario 2: no thread, no mention, no embedding match -> update_unresolved."""
    au_extraction = {"status": "done", "confidence": 0.85, "follow_up_at": None, "tasks": []}

    with patch(
        "services.v4_extraction.extract_capture_candidates",
        return_value=UPDATE_EXTRACTION,
    ), patch(
        "services.v4_extraction.extract_dates_and_tasks_from_update",
        return_value=au_extraction,
    ), patch(
        "services.v4_reconciliation.reconcile_candidates"
    ) as mock_reconcile:
        response = client.post(
            "/api/v4/capture",
            json={"content": "We can close this task now."},
        )

    assert response.status_code == 201
    data = response.get_json()
    mock_reconcile.assert_not_called()

    assert len(data["suggestions"]) == 1
    suggestion = data["suggestions"][0]
    assert suggestion["suggestion_type"] == "update_unresolved"
    assert suggestion["operation_type"] == "update_unresolved"
    assert suggestion["payload"]["content"] == "We can close this task now."
    assert suggestion["payload"]["status"] == "done"

    with app.app_context():
        assert Entity.query.filter_by(type="task").count() == 0
        assert AiSuggestion.query.count() == 1


def test_update_intent_with_explicit_mention_targets_mentioned_task(client, app):
    """Scenario 3: explicit mention resolves the update target."""
    task = _create_entity(client, "task", "Ship parser fix")
    content = f"Update on [Ship parser fix](/tasks/{task['id']}): all done now."
    au_extraction = {"status": "done", "confidence": 0.9, "follow_up_at": None, "tasks": []}

    with patch(
        "services.v4_extraction.extract_capture_candidates",
        return_value=UPDATE_EXTRACTION,
    ), patch(
        "services.v4_extraction.extract_dates_and_tasks_from_update",
        return_value=au_extraction,
    ):
        response = client.post("/api/v4/capture", json={"content": content})

    assert response.status_code == 201
    data = response.get_json()

    with app.app_context():
        entity = db.session.get(Entity, task["id"])
        assert entity.status == "done"

    assert all(s["suggestion_type"] != "update_unresolved" for s in data["suggestions"])
    au_changes = [c for c in data["applied_changes"] if c["type"] == "activity_update_added"]
    assert len(au_changes) == 1
    assert au_changes[0]["target_entity_id"] == task["id"]


def test_update_intent_resolves_target_via_embedding_similarity(client, app):
    """Ladder step 3: strong embedding match against active tasks resolves target."""
    task = _create_entity(client, "task", "Ship parser fix")
    au_extraction = {"status": "done", "confidence": 0.9, "follow_up_at": None, "tasks": []}

    def fake_chunks(entity_type):
        if entity_type != "task":
            return []
        entity_data = {"id": task["id"], "title": task["title"], "type": "task", "status": "open"}
        return [(task["id"], "Ship parser fix", [1.0, 0.0], entity_data)]

    with patch(
        "services.v4_extraction.extract_capture_candidates",
        return_value=UPDATE_EXTRACTION,
    ), patch(
        "services.v4_extraction.extract_dates_and_tasks_from_update",
        return_value=au_extraction,
    ), patch(
        "services.v4_reconciliation._embed_texts", return_value=[[1.0, 0.0]]
    ), patch(
        "services.v4_reconciliation._load_chunks_for_type", side_effect=fake_chunks
    ):
        response = client.post(
            "/api/v4/capture",
            json={"content": "Parser fix is finished, shipping it."},
        )

    assert response.status_code == 201
    with app.app_context():
        entity = db.session.get(Entity, task["id"])
        assert entity.status == "done"


def test_update_intent_weak_embedding_match_stays_unresolved(client, app):
    """Below the 0.75 similarity floor no target is guessed."""
    task = _create_entity(client, "task", "Ship parser fix")
    au_extraction = {"status": "done", "confidence": 0.9, "follow_up_at": None, "tasks": []}

    def fake_chunks(entity_type):
        if entity_type != "task":
            return []
        entity_data = {"id": task["id"], "title": task["title"], "type": "task", "status": "open"}
        return [(task["id"], "Ship parser fix", [1.0, 1.0], entity_data)]

    with patch(
        "services.v4_extraction.extract_capture_candidates",
        return_value=UPDATE_EXTRACTION,
    ), patch(
        "services.v4_extraction.extract_dates_and_tasks_from_update",
        return_value=au_extraction,
    ), patch(
        "services.v4_reconciliation._embed_texts", return_value=[[1.0, 0.0]]
    ), patch(
        "services.v4_reconciliation._load_chunks_for_type", side_effect=fake_chunks
    ):
        response = client.post(
            "/api/v4/capture",
            json={"content": "Wrapped up something unrelated today."},
        )

    assert response.status_code == 201
    data = response.get_json()
    assert [s["suggestion_type"] for s in data["suggestions"]] == ["update_unresolved"]
    with app.app_context():
        entity = db.session.get(Entity, task["id"])
        assert entity.status == "open"


def test_follow_up_intent_with_thread_id_applies_follow_up(client, app):
    """Scenario 4: follow_up intent applies follow_up_at per sq-02 semantics."""
    task = _create_entity(client, "task", "Ship parser fix")
    extraction = {
        "intent": "follow_up",
        "intent_confidence": 0.88,
        "confidence": 0.88,
    }
    au_extraction = {"status": None, "confidence": 0.0, "follow_up_at": "2026-08-15", "tasks": []}

    with patch(
        "services.v4_extraction.extract_capture_candidates",
        return_value=extraction,
    ), patch(
        "services.v4_extraction.extract_dates_and_tasks_from_update",
        return_value=au_extraction,
    ):
        response = client.post(
            "/api/v4/capture",
            json={"content": "Circle back with Henry on 2026-08-15.", "thread_id": task["id"]},
        )

    assert response.status_code == 201
    data = response.get_json()
    with app.app_context():
        entity = db.session.get(Entity, task["id"])
        assert entity.follow_up_at is not None
        assert entity.follow_up_at.date().isoformat() == "2026-08-15"
        assert entity.status == "open"

    follow_up_changes = [
        c for c in data["applied_changes"]
        if c["type"] == "entity_updated" and "follow_up_at" in c.get("changes", {})
    ]
    assert len(follow_up_changes) == 1


def test_follow_up_intent_closing_target_routes_follow_up_to_spinoff_task(client, app):
    """sq-02 semantics: closing status keeps follow-up off the target, on the spin-off."""
    task = _create_entity(client, "task", "Ship parser fix")
    extraction = {"intent": "update", "intent_confidence": 0.9, "confidence": 0.9}
    au_extraction = {
        "status": "done",
        "confidence": 0.9,
        "follow_up_at": "2026-08-15",
        "tasks": [
            {"title": "Check adoption metrics", "content": None, "due_at": None,
             "follow_up_at": None, "assigned_to": None, "confidence": 0.8}
        ],
    }

    with patch(
        "services.v4_extraction.extract_capture_candidates",
        return_value=extraction,
    ), patch(
        "services.v4_extraction.extract_dates_and_tasks_from_update",
        return_value=au_extraction,
    ):
        response = client.post(
            "/api/v4/capture",
            json={"content": "Done with this; check adoption metrics on 2026-08-15.", "thread_id": task["id"]},
        )

    assert response.status_code == 201
    data = response.get_json()
    with app.app_context():
        entity = db.session.get(Entity, task["id"])
        assert entity.status == "done"
        assert entity.follow_up_at is None

    task_suggestions = [s for s in data["suggestions"] if s["suggestion_type"] == "create_task"]
    assert len(task_suggestions) == 1
    assert task_suggestions[0]["payload"]["follow_up_at"] == "2026-08-15"


def test_junk_intent_skips_reconciliation_entirely(client, app):
    """Scenario 5: junk intent never reaches reconcile_candidates; note still created."""
    extraction = {
        "intent": "junk",
        "intent_confidence": 0.95,
        "entities": [
            {"type": "task", "title": "asdf", "confidence": 0.9, "evidence": "asdf"}
        ],
    }

    with patch(
        "services.v4_extraction.extract_capture_candidates",
        return_value=extraction,
    ), patch(
        "services.v4_reconciliation.reconcile_candidates"
    ) as mock_reconcile:
        response = client.post("/api/v4/capture", json={"content": "asdf test test"})

    assert response.status_code == 201
    data = response.get_json()
    mock_reconcile.assert_not_called()
    assert data["suggestions"] == []
    assert data["source_note"]["ai"]["intent"] == "junk"
    assert data["source_note"]["ai"]["status"] == "done"

    with app.app_context():
        assert Entity.query.filter_by(type="note").count() == 1
        assert Entity.query.filter_by(type="task").count() == 0


def test_task_signal_intent_still_uses_full_reconciliation(client, app):
    """Scenario 6: task_signal intent keeps the existing full pipeline."""
    extraction = {
        "intent": "task_signal",
        "intent_confidence": 0.9,
        "entities": [
            {
                "type": "task",
                "title": "Draft rollout plan",
                "confidence": 0.9,
                "evidence": "draft the rollout plan",
            }
        ],
    }

    with patch(
        "services.v4_extraction.extract_capture_candidates",
        return_value=extraction,
    ), patch(
        "services.v4_reconciliation.reconcile_candidates",
        return_value=[{"action": "new", "confidence": 0.9, "reason": "no match"}],
    ) as mock_reconcile:
        response = client.post(
            "/api/v4/capture",
            json={"content": "Need to draft the rollout plan"},
        )

    assert response.status_code == 201
    data = response.get_json()
    mock_reconcile.assert_called_once()
    assert [s["suggestion_type"] for s in data["suggestions"]] == ["create_task"]


def test_thread_attached_progress_update_decision_creates_activity_update(client, app):
    """Scenario 7 (SQ-06): reconciliation progress_update decisions are no longer
    dropped for thread-attached captures."""
    project = _create_entity(client, "project", "HITL Pilot", "Pilot rollout")

    extraction = {
        "intent": "task_signal",
        "intent_confidence": 0.9,
        "entities": [
            {
                "type": "project",
                "title": "HITL Pilot",
                "content": "Shipped parser fix",
                "confidence": 0.9,
                "evidence": "Shipped parser fix for the pilot",
            }
        ],
    }
    decisions = [
        {
            "action": "progress_update",
            "target_id": project["id"],
            "update_text": "Shipped parser fix for the pilot",
            "confidence": 0.92,
            "reason": "progress on HITL Pilot",
        }
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post(
            "/api/v4/capture",
            json={"content": "Shipped parser fix for the pilot.", "thread_id": project["id"]},
        )

    assert response.status_code == 201
    data = response.get_json()
    au_changes = [c for c in data["applied_changes"] if c["type"] == "activity_update_added"]
    assert len(au_changes) == 1
    assert au_changes[0]["target_entity_id"] == project["id"]

    updates = client.get(f"/api/v4/entities/{project['id']}/activity_updates").get_json()["data"]
    assert len(updates) == 1
    assert updates[0]["content"] == "Shipped parser fix for the pilot"


def test_stream_capture_routes_update_intent_same_as_single_shot(client, app):
    """Scenario 8: the SSE path shares the intent-routing branch."""
    task = _create_entity(client, "task", "Ship parser fix")
    au_extraction = {"status": "done", "confidence": 0.9, "follow_up_at": None, "tasks": []}

    with patch(
        "services.v4_extraction.extract_capture_candidates",
        return_value=UPDATE_EXTRACTION,
    ), patch(
        "services.v4_extraction.extract_dates_and_tasks_from_update",
        return_value=au_extraction,
    ), patch(
        "services.v4_reconciliation.reconcile_candidates"
    ) as mock_reconcile:
        response = client.post(
            "/api/v4/capture?stream=true",
            json={
                "content": "Talked to the design partners. We can close this task now.",
                "thread_id": task["id"],
            },
        )
        response_data = response.data

    assert response.status_code == 200
    mock_reconcile.assert_not_called()
    events = _parse_capture_sse_events(response_data)
    assert events[-1][0] == "done"
    done = events[-1][1]

    au_changes = [c for c in done["applied_changes"] if c["type"] == "activity_update_added"]
    assert len(au_changes) == 1
    status_changes = [
        c for c in done["applied_changes"]
        if c["type"] == "entity_updated" and c.get("changes", {}).get("status") == "done"
    ]
    assert len(status_changes) == 1

    with app.app_context():
        entity = db.session.get(Entity, task["id"])
        assert entity.status == "done"


def test_update_unresolved_suggestion_resolves_to_existing_target(client, app):
    """Resolving an update_unresolved suggestion applies the stored extraction."""
    task = _create_entity(client, "task", "Ship parser fix")
    au_extraction = {"status": "done", "confidence": 0.9, "follow_up_at": None, "tasks": []}

    with patch(
        "services.v4_extraction.extract_capture_candidates",
        return_value=UPDATE_EXTRACTION,
    ), patch(
        "services.v4_extraction.extract_dates_and_tasks_from_update",
        return_value=au_extraction,
    ):
        capture = client.post(
            "/api/v4/capture",
            json={"content": "We can close this out now."},
        ).get_json()

    assert [s["suggestion_type"] for s in capture["suggestions"]] == ["update_unresolved"]
    suggestion_id = capture["suggestions"][0]["id"]

    response = client.post(
        f"/api/v4/suggestions/{suggestion_id}/resolve-to-existing",
        json={"target_id": task["id"]},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["suggestion"]["status"] == "accepted"
    assert data["linked_entity"]["id"] == task["id"]

    with app.app_context():
        entity = db.session.get(Entity, task["id"])
        assert entity.status == "done"
        suggestion = db.session.get(AiSuggestion, suggestion_id)
        assert suggestion.status == "accepted"
        assert suggestion.payload.get("resolved_to_existing_id") == task["id"]

    updates = client.get(f"/api/v4/entities/{task['id']}/activity_updates").get_json()["data"]
    assert len(updates) == 1


def test_update_intent_low_confidence_uses_full_pipeline(client, app):
    """Below the 0.7 intent-confidence floor the old path still runs."""
    extraction = {
        "intent": "update",
        "intent_confidence": 0.5,
        "entities": [],
    }

    with patch(
        "services.v4_extraction.extract_capture_candidates",
        return_value=extraction,
    ), patch(
        "services.v4_extraction.extract_dates_and_tasks_from_update"
    ) as mock_au_extract:
        response = client.post(
            "/api/v4/capture",
            json={"content": "Some vague progress happened maybe."},
        )

    assert response.status_code == 201
    mock_au_extract.assert_not_called()
    data = response.get_json()
    assert all(s["suggestion_type"] != "update_unresolved" for s in data["suggestions"])


def test_update_intent_long_content_uses_full_pipeline(client, app):
    """Long content (meeting notes) stays on full reconciliation even with update intent."""
    long_content = "Long meeting notes about many things. " * 60

    with patch(
        "services.v4_extraction.extract_capture_candidates",
        return_value=UPDATE_EXTRACTION,
    ), patch(
        "services.v4_extraction.extract_dates_and_tasks_from_update"
    ) as mock_au_extract:
        response = client.post("/api/v4/capture", json={"content": long_content})

    assert response.status_code == 201
    mock_au_extract.assert_not_called()
