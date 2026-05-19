"""Cycle 8 tests for v4 suggestion review."""

from extensions import db
from models import AiSuggestion, Entity, EntityEvent, EntityLink


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
    data = response.get_json()["data"]
    assert [row["id"] for row in data] == [suggestion_id]
    assert data[0]["status"] == "pending"
    assert data[0]["payload"]["source_entity_id"] == note_id


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
