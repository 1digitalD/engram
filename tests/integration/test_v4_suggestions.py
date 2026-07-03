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
                "title": "Follow up with Henry later",
                "content": "Keep an eye on this",
                "due_at": None,
                "follow_up_at": None,
                "assigned_to": "Henry",
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


def test_accept_create_new_entity_suggestion_from_activity_update_links_to_target_entity(client, app):
    project = client.post("/api/v4/entities", json={"type": "project", "title": "Launch plan"}).get_json()["data"]
    activity_update = client.post(
        f"/api/v4/entities/{project['id']}/activity_updates",
        json={"content": "Need a follow-up task for launch QA."},
    ).get_json()["data"]

    suggestion_id = _create_suggestion(
        app,
        activity_update["id"],
        "create_task",
        {
            "type": "task",
            "title": "Follow up on launch QA",
            "content": "Confirm launch QA checklist is complete",
            "target_entity_id": project["id"],
            "relationship_type": "derived_from",
            "evidence": "follow-up task for launch QA",
        },
        operation_type="create_new_entity",
    )

    response = client.post(f"/api/v4/suggestions/{suggestion_id}/accept")

    assert response.status_code == 200
    data = response.get_json()
    assert data["suggestion"]["status"] == "accepted"
    assert data["created_entity"]["type"] == "task"
    assert data["relationship"]["source_entity_id"] == data["created_entity"]["id"]
    assert data["relationship"]["target_entity_id"] == project["id"]
    assert data["relationship"]["relationship_type"] == "derived_from"

    with app.app_context():
        EntityLink.query.filter_by(
            source_entity_id=data["created_entity"]["id"],
            target_entity_id=project["id"],
            relationship_type="derived_from",
        ).one()


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


def test_dismiss_suggestion_stores_reason(client, app):
    note_id = _create_note(app)
    suggestion_id = _create_suggestion(
        app,
        note_id,
        "create_task",
        {
            "type": "task",
            "title": "Not my task",
            "source_entity_id": note_id,
            "evidence": "follow up",
        },
    )

    response = client.post(
        f"/api/v4/suggestions/{suggestion_id}/dismiss",
        json={"dismiss_reason": "not mine"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["status"] == "dismissed"
    assert data["payload"]["dismiss_reason"] == "not mine"

    list_response = client.get("/api/v4/suggestions?status=all")
    row = next((r for r in list_response.get_json()["data"] if r["id"] == suggestion_id), None)
    assert row["payload"]["dismiss_reason"] == "not mine"


def test_dismiss_suggestion_rejects_invalid_reason(client, app):
    note_id = _create_note(app)
    suggestion_id = _create_suggestion(
        app,
        note_id,
        "create_task",
        {
            "type": "task",
            "title": "Task",
            "source_entity_id": note_id,
        },
    )

    response = client.post(
        f"/api/v4/suggestions/{suggestion_id}/dismiss",
        json={"dismiss_reason": "bogus"},
    )

    assert response.status_code == 400
    with app.app_context():
        assert db.session.get(AiSuggestion, suggestion_id).status == "pending"


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


def test_resolve_suggestion_to_existing_links_instead_of_creating(client, app):
    """The 'this already exists' review action: link source note to the
    near-match instead of creating a duplicate entity."""
    from extensions import db
    from models import AiSuggestion, Entity, EntityLink

    existing = client.post(
        "/api/v4/entities", json={"type": "project", "title": "Define Agent Platform roadmap"}
    ).get_json()["data"]
    note = client.post(
        "/api/v4/capture", json={"content": "roadmap planning thoughts"}
    ).get_json()["source_note"]

    with app.app_context():
        suggestion = AiSuggestion(
            source_entity_id=note["id"],
            suggestion_type="create_project",
            operation_type="create_entity",
            payload={
                "type": "project",
                "title": "Plan agent platform roadmap",
                "relationship_type": "related",
                "near_match": {"entity_id": existing["id"], "title": existing["title"], "score": 0.82},
            },
            confidence=0.9,
        )
        db.session.add(suggestion)
        db.session.commit()
        suggestion_id = suggestion.id

    response = client.post(f"/api/v4/suggestions/{suggestion_id}/resolve-to-existing", json={})
    assert response.status_code == 200
    body = response.get_json()
    assert body["suggestion"]["status"] == "accepted"
    assert body["suggestion"]["payload"]["resolved_to_existing_id"] == existing["id"]
    assert body["linked_entity"]["id"] == existing["id"]
    assert body["relationship"] is not None

    with app.app_context():
        # No duplicate project was created
        assert Entity.query.filter_by(type="project").count() == 1
        assert EntityLink.query.filter_by(
            source_entity_id=note["id"], target_entity_id=existing["id"]
        ).count() == 1


def test_resolve_to_existing_requires_near_match_or_target(client, app):
    from extensions import db
    from models import AiSuggestion

    note = client.post("/api/v4/capture", json={"content": "note"}).get_json()["source_note"]
    with app.app_context():
        suggestion = AiSuggestion(
            source_entity_id=note["id"],
            suggestion_type="create_task",
            operation_type="create_entity",
            payload={"type": "task", "title": "Some task"},
        )
        db.session.add(suggestion)
        db.session.commit()
        suggestion_id = suggestion.id

    response = client.post(f"/api/v4/suggestions/{suggestion_id}/resolve-to-existing", json={})
    assert response.status_code == 400


def _fake_embed_with_vectors():
    vectors = {
        "follow up with henry": [1.0] + [0.0] * 1535,
        "follow up with henry on rollout status": [1.0] + [0.0] * 1535,
        "schedule team offsite": [0.0, 1.0] + [0.0] * 1534,
    }

    def _embed(texts):
        return [vectors.get((t or "").lower().strip(), [0.0] * 1536) for t in texts]

    return _embed


def test_semantic_duplicate_suppresses_reworded_duplicate(client, app, monkeypatch):
    """SQ-10: a reworded duplicate of a recently dismissed suggestion is not recreated."""
    from datetime import datetime, timezone
    from api import v4_entities
    import services.v4_reconciliation

    monkeypatch.setattr(
        services.v4_reconciliation, "_embed_texts", _fake_embed_with_vectors()
    )

    note_id = _create_note(app, "Semantic dup source")
    with app.app_context():
        note = db.session.get(Entity, note_id)
        original = v4_entities._create_suggestion(
            note,
            "create_task",
            "create_entity",
            {"type": "task", "title": "Follow up with Henry", "source_entity_id": note_id},
            confidence=0.9,
        )
        db.session.commit()
        original.status = "dismissed"
        original.resolved_at = datetime.now(timezone.utc)
        db.session.commit()

        duplicate = v4_entities._create_suggestion(
            note,
            "create_task",
            "create_entity",
            {
                "type": "task",
                "title": "Follow up with Henry on rollout status",
                "source_entity_id": note_id,
            },
            confidence=0.9,
        )
        assert duplicate is None
        assert (
            AiSuggestion.query.filter_by(source_entity_id=note_id, status="pending").count()
            == 0
        )


def test_semantic_duplicate_does_not_suppress_different_suggestion(client, app, monkeypatch):
    """SQ-10: a genuinely different suggestion about the same person is still proposed."""
    from datetime import datetime, timezone
    from api import v4_entities
    import services.v4_reconciliation

    monkeypatch.setattr(
        services.v4_reconciliation, "_embed_texts", _fake_embed_with_vectors()
    )

    note_id = _create_note(app, "Semantic non-dup source")
    with app.app_context():
        note = db.session.get(Entity, note_id)
        original = v4_entities._create_suggestion(
            note,
            "create_task",
            "create_entity",
            {"type": "task", "title": "Follow up with Henry", "source_entity_id": note_id},
            confidence=0.9,
        )
        db.session.commit()
        original.status = "dismissed"
        original.resolved_at = datetime.now(timezone.utc)
        db.session.commit()

        different = v4_entities._create_suggestion(
            note,
            "create_task",
            "create_entity",
            {"type": "task", "title": "Schedule team offsite", "source_entity_id": note_id},
            confidence=0.9,
        )
        assert different is not None
        assert different.status == "pending"


def test_exact_fingerprint_short_circuits_before_embedding(client, app, monkeypatch):
    """SQ-10: exact fingerprint match suppresses without running embedding comparison."""
    from datetime import datetime, timezone
    from api import v4_entities
    import services.v4_reconciliation

    calls = []

    def _counting_embed(texts):
        calls.append(texts)
        return [[0.0] * 1536 for _ in texts]

    monkeypatch.setattr(services.v4_reconciliation, "_embed_texts", _counting_embed)

    note_id = _create_note(app, "Exact dup source")
    payload = {"type": "task", "title": "Follow up with Henry", "source_entity_id": note_id}
    with app.app_context():
        note = db.session.get(Entity, note_id)
        original = v4_entities._create_suggestion(
            note, "create_task", "create_entity", payload, confidence=0.9
        )
        db.session.commit()
        original.status = "dismissed"
        original.resolved_at = datetime.now(timezone.utc)
        db.session.commit()

        duplicate = v4_entities._create_suggestion(
            note, "create_task", "create_entity", payload, confidence=0.9
        )
        assert duplicate is None
        assert not calls
