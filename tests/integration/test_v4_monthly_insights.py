"""Integration tests for monthly portfolio health insights."""

from datetime import datetime, timedelta, timezone

from extensions import db
from models import AppSetting, Entity


def _create_entity(client, entity_type, title, **extra):
    payload = {"type": entity_type, "title": title, "content": f"{title} content", **extra}
    response = client.post("/api/v4/entities", json=payload)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def _link(client, source_id, target_id, relationship_type):
    response = client.post(
        f"/api/v4/entities/{source_id}/relationships",
        json={"target_entity_id": target_id, "relationship_type": relationship_type},
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def _rewind_entity(app, entity_id, *, days):
    with app.app_context():
        ts = datetime.now(timezone.utc) - timedelta(days=days)
        db.session.execute(db.text("ALTER TABLE entities DISABLE TRIGGER entities_updated_at"))
        try:
            db.session.execute(
                db.text(
                    "UPDATE entities SET created_at = :ts, updated_at = :ts WHERE id = :id"
                ),
                {"ts": ts, "id": entity_id},
            )
        finally:
            db.session.execute(db.text("ALTER TABLE entities ENABLE TRIGGER entities_updated_at"))
        db.session.commit()


def _archive_entity(app, entity_id):
    with app.app_context():
        entity = db.session.get(Entity, entity_id)
        entity.lifecycle = "archived"
        db.session.commit()


def test_tc53_monthly_endpoint_caches_and_workboard_places_briefing(client, app):
    person = _create_entity(client, "person", "Dana")
    teammate = _create_entity(client, "person", "Priya")
    space = _create_entity(
        client,
        "project",
        "Acme renewal",
        due_at=(datetime.now(timezone.utc) + timedelta(days=9)).isoformat(),
    )
    task = _create_entity(
        client,
        "task",
        "Draft renewal plan",
        due_at=(datetime.now(timezone.utc) + timedelta(days=4)).isoformat(),
    )
    _link(client, task["id"], teammate["id"], "assigned_to")
    _link(client, task["id"], space["id"], "parent")
    _rewind_entity(app, person["id"], days=24)
    _rewind_entity(app, space["id"], days=24)
    _rewind_entity(app, task["id"], days=24)

    theme = _create_entity(
        client,
        "theme",
        "EU expansion",
        due_at=(datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
    )
    _rewind_entity(app, theme["id"], days=28)

    archived_space = _create_entity(client, "project", "Archived backlog")
    orphaned = _create_entity(client, "task", "Untangle old task")
    _link(client, orphaned["id"], archived_space["id"], "parent")
    _archive_entity(app, archived_space["id"])

    first = client.get("/api/v4/insights/monthly")
    assert first.status_code == 200
    first_body = first.get_json()
    assert first_body["from_cache"] is False
    assert {section["key"] for section in first_body["briefing"]["sections"]} == {
        "quiet_people",
        "at_risk_spaces",
        "idle_themes",
        "unowned_work",
    }

    second = client.get("/api/v4/insights/monthly")
    assert second.status_code == 200
    second_body = second.get_json()
    assert second_body["from_cache"] is True

    with app.app_context():
        setting = db.session.get(AppSetting, "monthly_health_briefing")
        assert setting is not None
        assert setting.value["briefing"]["sections"]

    workboard = client.get("/api/v4/workboard", query_string={"group": "space"})
    assert workboard.status_code == 200
    monthly_health = workboard.get_json()["meta"]["monthly_health"]
    assert monthly_health["from_cache"] is True
    assert monthly_health["briefing"] == second_body["briefing"]


def test_tc53_monthly_endpoint_returns_explicit_message_when_empty(client):
    response = client.get("/api/v4/insights/monthly")
    assert response.status_code == 200
    body = response.get_json()
    assert body["briefing"]["sections"] == []
    assert body["briefing"]["message"]
