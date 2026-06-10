"""Cycle 8 tests for v4 suggestion review."""

from extensions import db
from models import AiSuggestion, Entity, EntityEvent, EntityLink, Job


def _create_note(app, title="Source note"):
    with app.app_context():
        note = Entity(
            type="note",
            title=title,
            content="Captured source",
            status="active",
            lifecycle="active",
            source="test",
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        app.extensions["sqlalchemy"].session.add(note)
        app.extensions["sqlalchemy"].session.flush()
        note_id = note.id
        app.extensions["sqlalchemy"].session.commit()
        return note_id


def _create_suggestion(app, source_entity_id, suggestion_type, payload, operation_type="create_entity"):
    with app.app_context():
        suggestion = AiSuggestion(
            source_entity_id=source_entity_id,
            suggestion_type=suggestion_type,
            operation_type=operation_type,
            payload=payload,
            confidence=0.91,
            reason=payload.get("evidence"),
            status="pending",
        )
        app.extensions["sqlalchemy"].session.add(suggestion)
        app.extensions["sqlalchemy"].session.flush()
        suggestion_id = suggestion.id
        app.extensions["sqlalchemy"].session.commit()
        return suggestion_id


def test_list_v4_suggestions_returns_pending_items(client, app):
    note_id = _create_note(app)
    suggestion_id = _create_suggestion(
        app,
        note_id,
        "create_task",
        {
            "type": "task",
            "title": "Follow up",
            "content": "Follow up with Henry",
            "source_entity_id": note_id,
            "evidence": "follow up",
        },
    )

    response = client.get("/api/v4/suggestions")

    assert response.status_code == 200
    payload = response.get_json()
    data = payload["data"]
    assert [row["id"] for row in data] == [suggestion_id]
    assert data[0]["status"] == "pending"
    assert data[0]["payload"]["source_entity_id"] == note_id
    assert payload["meta"]["total"] == 1


def test_resolve_review_marks_note_resolved_and_clears_it_from_inbox(client, app):
    note_id = _create_note(app)
    suggestion_id = _create_suggestion(
        app,
        note_id,
        "create_task",
        {
            "type": "task",
            "title": "Optional follow up",
            "content": "No action needed",
            "source_entity_id": note_id,
            "evidence": "optional",
        },
    )

    with app.app_context():
        note = db.session.get(Entity, note_id)
        note.ai_status = "failed"
        db.session.commit()

    response = client.post(f"/api/v4/entities/{note_id}/review/resolve")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["meta"]["dismissed_suggestions"] == 1
    assert payload["data"]["ai"]["review_state"] == "resolved"
    assert payload["data"]["ai"]["review_resolution"] == "no_change_needed"

    inbox = client.get("/api/v4/inbox").get_json()
    assert note_id not in {item["id"] for item in inbox["needs_review"]}

    with app.app_context():
        assert db.session.get(AiSuggestion, suggestion_id).status == "dismissed"
        events = EntityEvent.query.filter_by(entity_id=note_id).all()
        assert any(event.event_type == "review_marked_resolved" for event in events)


def test_resolved_review_note_reenters_inbox_when_new_suggestion_is_created(client, app):
    note_id = _create_note(app)

    resolve_response = client.post(f"/api/v4/entities/{note_id}/review/resolve")
    assert resolve_response.status_code == 200

    ingest = client.post(
        f"/api/v4/entities/{note_id}/ingest_candidates",
        json={
            "title": "Follow-up note",
            "summary": "Needs a task suggestion",
            "intent": "task_signal",
            "intent_confidence": 0.95,
            "confidence": 0.95,
            "tags": [],
            "links": [],
            "entities": [{
                "type": "task",
                "title": "Follow up later",
                "content": "Keep an eye on this",
                "due_at": None,
                "follow_up_at": None,
                "assigned_to": None,
                "confidence": 0.61,
                "evidence": "follow up later",
            }],
        },
    )
    assert ingest.status_code == 200

    inbox = client.get("/api/v4/inbox").get_json()
    assert note_id in {item["id"] for item in inbox["needs_review"]}

    with app.app_context():
        note = db.session.get(Entity, note_id)
        assert (note.ai_meta or {}).get("review_state") != "resolved"
        assert AiSuggestion.query.filter_by(source_entity_id=note_id, status="pending").count() == 1


def test_accept_create_task_suggestion_creates_task_and_derived_from_link(client, app):
    note_id = _create_note(app)
    suggestion_id = _create_suggestion(
        app,
        note_id,
        "create_task",
        {
            "type": "task",
            "title": "Follow up with Henry",
            "content": "Ask Henry about rollout",
            "source_entity_id": note_id,
            "evidence": "Ask Henry",
            "properties": {"priority": "high"},
        },
    )

    response = client.post(f"/api/v4/suggestions/{suggestion_id}/accept")

    assert response.status_code == 200
    data = response.get_json()
    assert data["suggestion"]["status"] == "accepted"
    created = data["created_entity"]
    assert created["type"] == "task"
    assert created["title"] == "Follow up with Henry"
    assert created["properties"] == {"priority": "high"}

    with app.app_context():
        task = Entity.query.filter_by(type="task", title="Follow up with Henry").one()
        link = EntityLink.query.filter_by(
            source_entity_id=task.id,
            target_entity_id=note_id,
            relationship_type="derived_from",
        ).one()
        assert link.source == "ai_review"
        assert db.session.get(AiSuggestion, suggestion_id).status == "accepted"
        assert EntityEvent.query.filter_by(entity_id=task.id, event_type="created").count() == 1
        assert EntityEvent.query.filter_by(entity_id=task.id, event_type="relationship_added").count() == 1
        assert EntityEvent.query.filter_by(entity_id=note_id, event_type="suggestion_accepted").count() == 1


def test_accept_create_task_suggestion_applies_assigned_to_person_link(client, app):
    note_id = _create_note(app)
    suggestion_id = _create_suggestion(
        app,
        note_id,
        "create_task",
        {
            "type": "task",
            "title": "Follow up with Henry",
            "content": "Ask Henry about rollout",
            "assigned_to": "Henry",
            "source_entity_id": note_id,
            "evidence": "Henry owns this follow-up",
        },
    )

    response = client.post(f"/api/v4/suggestions/{suggestion_id}/accept")

    assert response.status_code == 200
    data = response.get_json()
    created = data["created_entity"]
    assert created["type"] == "task"
    assert created["title"] == "Follow up with Henry"

    with app.app_context():
        task = Entity.query.filter_by(type="task", title="Follow up with Henry").one()
        person = Entity.query.filter_by(type="person", title="Henry").one()
        EntityLink.query.filter_by(
            source_entity_id=task.id,
            target_entity_id=person.id,
            relationship_type="assigned_to",
        ).one()
        assert EntityEvent.query.filter_by(entity_id=person.id, event_type="created").count() == 1
        assert EntityEvent.query.filter_by(entity_id=task.id, event_type="relationship_added").count() >= 1
        reasons = [job.payload["reason"] for job in Job.query.filter_by(entity_id=task.id, job_type="embed").all()]
        assert "suggestion_accept_create" in reasons


def test_accept_link_existing_suggestion_creates_entity_link(client, app):
    note_id = _create_note(app)
    with app.app_context():
        project = Entity(
            type="project",
            title="Memory Lookup",
            content="Project context",
            status="active",
            lifecycle="active",
            source="test",
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        db.session.add(project)
        db.session.flush()
        project_id = project.id
        db.session.commit()

    suggestion_id = _create_suggestion(
        app,
        note_id,
        "link_existing",
        {
            "source_entity_id": note_id,
            "target_entity_id": project_id,
            "target_type": "project",
            "title": "Memory Lookup",
            "relationship_type": "related",
            "evidence": "mentions Memory Lookup",
        },
        operation_type="link_existing",
    )

    response = client.post(f"/api/v4/suggestions/{suggestion_id}/accept")

    assert response.status_code == 200
    data = response.get_json()
    assert data["suggestion"]["status"] == "accepted"
    assert data["created_entity"] is None
    assert data["relationship"]["source_entity_id"] == note_id
    assert data["relationship"]["target_entity_id"] == project_id
    assert data["relationship"]["relationship_type"] == "related"
    assert data["relationship"]["source"] == "ai_review"

    with app.app_context():
        EntityLink.query.filter_by(
            source_entity_id=note_id,
            target_entity_id=project_id,
            relationship_type="related",
        ).one()
        assert db.session.get(AiSuggestion, suggestion_id).status == "accepted"
        assert Entity.query.filter_by(type="project", title="Memory Lookup").count() == 1
        assert EntityEvent.query.filter_by(entity_id=note_id, event_type="relationship_added").count() == 1
        assert EntityEvent.query.filter_by(entity_id=note_id, event_type="suggestion_accepted").count() == 1


def test_accept_update_entity_suggestion_updates_task_and_links_source_note(client, app):
    note_id = _create_note(app)
    with app.app_context():
        task = Entity(
            type="task",
            title="Follow up with Henry",
            content="Initial task",
            status="open",
            lifecycle="active",
            source="test",
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        db.session.add(task)
        db.session.flush()
        task_id = task.id
        db.session.commit()

    suggestion_id = _create_suggestion(
        app,
        note_id,
        "update_task",
        {
            "target_entity_id": task_id,
            "target_type": "task",
            "title": "Follow up with Henry",
            "fields": {
                "status": "blocked",
                "follow_up_at": "2026-06-10T09:00:00Z",
            },
            "relationship_type": "derived_from",
            "evidence": "blocked pending Henry response",
        },
        operation_type="update_entity",
    )

    response = client.post(f"/api/v4/suggestions/{suggestion_id}/accept")

    assert response.status_code == 200
    data = response.get_json()
    assert data["suggestion"]["status"] == "accepted"
    assert data["created_entity"]["id"] == task_id
    assert data["created_entity"]["status"] == "blocked"
    assert data["relationship"]["source_entity_id"] == task_id
    assert data["relationship"]["target_entity_id"] == note_id
    assert data["relationship"]["relationship_type"] == "derived_from"

    with app.app_context():
        updated_task = db.session.get(Entity, task_id)
        assert updated_task.status == "blocked"
        assert updated_task.follow_up_at is not None
        EntityLink.query.filter_by(
            source_entity_id=task_id,
            target_entity_id=note_id,
            relationship_type="derived_from",
        ).one()
        assert db.session.get(AiSuggestion, suggestion_id).status == "accepted"
        assert EntityEvent.query.filter_by(entity_id=task_id, event_type="updated").count() == 1
        assert EntityEvent.query.filter_by(entity_id=task_id, event_type="status_changed").count() == 1
        assert EntityEvent.query.filter_by(entity_id=task_id, event_type="relationship_added").count() == 1
        assert EntityEvent.query.filter_by(entity_id=note_id, event_type="suggestion_accepted").count() == 1


def test_accept_update_entity_suggestion_sets_priority(client, app):
    note_id = _create_note(app)
    with app.app_context():
        task = Entity(
            type="task",
            title="Fix prod outage",
            content="Initial task",
            status="open",
            lifecycle="active",
            source="test",
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        db.session.add(task)
        db.session.flush()
        task_id = task.id
        db.session.commit()

    suggestion_id = _create_suggestion(
        app,
        note_id,
        "update_task",
        {
            "target_entity_id": task_id,
            "target_type": "task",
            "title": "Fix prod outage",
            "fields": {"priority": "urgent"},
            "relationship_type": "derived_from",
            "evidence": "this is now urgent",
        },
        operation_type="update_entity",
    )

    response = client.post(f"/api/v4/suggestions/{suggestion_id}/accept")

    assert response.status_code == 200
    data = response.get_json()
    assert data["created_entity"]["properties"]["priority"] == "urgent"

    with app.app_context():
        updated_task = db.session.get(Entity, task_id)
        assert updated_task.properties["priority"] == "urgent"
        assert EntityEvent.query.filter_by(entity_id=task_id, event_type="updated").count() == 1


def test_accept_update_entity_suggestion_rejects_invalid_priority(client, app):
    note_id = _create_note(app)
    with app.app_context():
        task = Entity(
            type="task",
            title="Fix prod outage",
            content="Initial task",
            status="open",
            lifecycle="active",
            source="test",
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        db.session.add(task)
        db.session.flush()
        task_id = task.id
        db.session.commit()

    suggestion_id = _create_suggestion(
        app,
        note_id,
        "update_task",
        {
            "target_entity_id": task_id,
            "target_type": "task",
            "title": "Fix prod outage",
            "fields": {"priority": "extreme"},
            "relationship_type": "derived_from",
            "evidence": "this is now urgent",
        },
        operation_type="update_entity",
    )

    response = client.post(f"/api/v4/suggestions/{suggestion_id}/accept")

    assert response.status_code == 400

    with app.app_context():
        updated_task = db.session.get(Entity, task_id)
        assert updated_task.properties.get("priority") is None


def test_accept_create_person_project_area_resource_suggestions(client, app):
    note_id = _create_note(app)
    cases = [
        ("person", "Henry", "mentions"),
        ("project", "Memory Lookup", "related"),
        ("area", "Agent Platform", "related"),
        ("resource", "Rollout checklist", "references"),
    ]

    for entity_type, title, relationship_type in cases:
        suggestion_id = _create_suggestion(
            app,
            note_id,
            f"create_{entity_type}",
            {
                "type": entity_type,
                "title": title,
                "content": f"{title} content",
                "source_entity_id": note_id,
                "evidence": title,
            },
        )

        response = client.post(f"/api/v4/suggestions/{suggestion_id}/accept")

        assert response.status_code == 200
        created = response.get_json()["created_entity"]
        assert created["type"] == entity_type
        assert created["title"] == title

    with app.app_context():
        for entity_type, title, relationship_type in cases:
            entity = Entity.query.filter_by(type=entity_type, title=title).one()
            EntityLink.query.filter_by(
                source_entity_id=note_id,
                target_entity_id=entity.id,
                relationship_type=relationship_type,
            ).one()
        assert AiSuggestion.query.filter(AiSuggestion.status != "accepted").count() == 0


def test_dismiss_suggestion_does_not_mutate_entities(client, app):
    note_id = _create_note(app)
    suggestion_id = _create_suggestion(
        app,
        note_id,
        "create_project",
        {
            "type": "project",
            "title": "Do not create",
            "source_entity_id": note_id,
            "evidence": "maybe project",
        },
    )

    response = client.post(f"/api/v4/suggestions/{suggestion_id}/dismiss")

    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "dismissed"
    with app.app_context():
        assert Entity.query.filter_by(type="project").count() == 0
        assert EntityLink.query.count() == 0
        assert db.session.get(AiSuggestion, suggestion_id).status == "dismissed"
        assert EntityEvent.query.filter_by(entity_id=note_id, event_type="suggestion_dismissed").count() == 1


def test_reconcile_suggestions_expires_stale_link_existing_suggestion(client, app):
    note_id = _create_note(app)
    with app.app_context():
        project = Entity(
            type="project",
            title="Memory Lookup",
            content="Project context",
            status="active",
            lifecycle="active",
            source="test",
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        db.session.add(project)
        db.session.flush()
        project_id = project.id
        db.session.add(EntityLink(
            source_entity_id=note_id,
            target_entity_id=project_id,
            relationship_type="related",
            source="test",
        ))
        db.session.commit()

    suggestion_id = _create_suggestion(
        app,
        note_id,
        "link_existing",
        {
            "source_entity_id": note_id,
            "target_entity_id": project_id,
            "target_type": "project",
            "title": "Memory Lookup",
            "relationship_type": "related",
            "evidence": "mentions Memory Lookup",
        },
        operation_type="link_existing",
    )

    response = client.post("/api/v4/suggestions/reconcile")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["meta"]["expired"] == 1
    assert payload["data"][0]["id"] == suggestion_id
    assert payload["data"][0]["status"] == "expired"

    with app.app_context():
        assert db.session.get(AiSuggestion, suggestion_id).status == "expired"
        assert EntityEvent.query.filter_by(entity_id=note_id, event_type="suggestion_expired").count() == 1


def test_reconcile_suggestions_expires_stale_create_entity_suggestion(client, app):
    note_id = _create_note(app)
    with app.app_context():
        task = Entity(
            type="task",
            title="Follow up with Henry",
            content="Existing task",
            status="open",
            lifecycle="active",
            source="test",
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        db.session.add(task)
        db.session.flush()
        task_id = task.id
        db.session.add(EntityLink(
            source_entity_id=task_id,
            target_entity_id=note_id,
            relationship_type="derived_from",
            source="test",
        ))
        db.session.commit()

    suggestion_id = _create_suggestion(
        app,
        note_id,
        "create_task",
        {
            "type": "task",
            "title": "Follow up with Henry",
            "content": "Ask Henry about rollout",
            "source_entity_id": note_id,
            "relationship_type": "derived_from",
            "evidence": "Ask Henry",
        },
    )

    response = client.post("/api/v4/suggestions/reconcile")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["meta"]["expired"] == 1
    assert payload["data"][0]["id"] == suggestion_id

    with app.app_context():
        assert db.session.get(AiSuggestion, suggestion_id).status == "expired"


def test_accept_rejects_relationship_ids_inside_suggestion_properties(client, app):
    note_id = _create_note(app)
    suggestion_id = _create_suggestion(
        app,
        note_id,
        "create_task",
        {
            "type": "task",
            "title": "Bad task",
            "source_entity_id": note_id,
            "properties": {"project_id": "legacy"},
        },
    )

    response = client.post(f"/api/v4/suggestions/{suggestion_id}/accept")

    assert response.status_code == 400
    assert "relationship IDs" in response.get_json()["error"]
    with app.app_context():
        assert Entity.query.filter_by(type="task").count() == 0
        assert db.session.get(AiSuggestion, suggestion_id).status == "pending"


def test_accept_rejects_invalid_follow_up_at_without_mutation(client, app):
    note_id = _create_note(app)
    suggestion_id = _create_suggestion(
        app,
        note_id,
        "create_task",
        {
            "type": "task",
            "title": "Bad date task",
            "source_entity_id": note_id,
            "follow_up_at": "not-a-date",
        },
    )

    response = client.post(f"/api/v4/suggestions/{suggestion_id}/accept")

    assert response.status_code == 400
    assert "invalid datetime" in response.get_json()["error"]
    with app.app_context():
        assert Entity.query.filter_by(type="task", title="Bad date task").count() == 0
        assert db.session.get(AiSuggestion, suggestion_id).status == "pending"


def test_accept_update_entity_rejects_invalid_datetime_without_mutation(client, app):
    note_id = _create_note(app)
    with app.app_context():
        task = Entity(
            type="task",
            title="Check rollout",
            content="Initial task",
            status="open",
            lifecycle="active",
            source="test",
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        db.session.add(task)
        db.session.flush()
        task_id = task.id
        db.session.commit()

    suggestion_id = _create_suggestion(
        app,
        note_id,
        "update_task",
        {
            "target_entity_id": task_id,
            "target_type": "task",
            "title": "Check rollout",
            "fields": {"follow_up_at": "not-a-date"},
            "relationship_type": "derived_from",
        },
        operation_type="update_entity",
    )

    response = client.post(f"/api/v4/suggestions/{suggestion_id}/accept")

    assert response.status_code == 400
    assert "invalid datetime" in response.get_json()["error"]
    with app.app_context():
        task = db.session.get(Entity, task_id)
        assert task.status == "open"
        assert task.follow_up_at is None
        assert EntityLink.query.count() == 0
        assert db.session.get(AiSuggestion, suggestion_id).status == "pending"
