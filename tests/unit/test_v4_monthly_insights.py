"""Unit tests for monthly portfolio health insights."""

from datetime import datetime, timedelta, timezone

from extensions import db
from models import AppSetting, Entity
from services.v4_monthly_insights import EMPTY_MONTHLY_HEALTH_MESSAGE


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


def _clear_monthly_cache(app):
    with app.app_context():
        setting = db.session.get(AppSetting, "monthly_health_briefing")
        if setting is not None:
            db.session.delete(setting)
            db.session.commit()


def test_tc53_monthly_signal_sections_cover_each_fixture_case(client, app):
    _clear_monthly_cache(app)

    owner = _create_entity(client, "person", "Dana")
    teammate = _create_entity(client, "person", "Priya")
    quiet_space = _create_entity(client, "project", "Legal refresh")
    quiet_task = _create_entity(client, "task", "Review legal packet")
    _link(client, quiet_task["id"], owner["id"], "assigned_to")
    _link(client, quiet_task["id"], quiet_space["id"], "parent")
    _rewind_entity(app, owner["id"], days=25)
    _rewind_entity(app, quiet_space["id"], days=25)
    _rewind_entity(app, quiet_task["id"], days=25)

    risk_space = _create_entity(
        client,
        "project",
        "Acme renewal",
        due_at=(datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
    )
    risk_task = _create_entity(
        client,
        "task",
        "Prepare renewal plan",
        due_at=(datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
    )
    _link(client, risk_task["id"], teammate["id"], "assigned_to")
    _link(client, risk_task["id"], risk_space["id"], "parent")
    _rewind_entity(app, risk_space["id"], days=20)
    _rewind_entity(app, risk_task["id"], days=20)

    theme = _create_entity(
        client,
        "theme",
        "EU expansion",
        due_at=(datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
    )
    _rewind_entity(app, theme["id"], days=30)

    unowned = _create_entity(client, "task", "Close open loop")
    archived_space = _create_entity(client, "project", "Old space")
    orphaned = _create_entity(client, "task", "Tidy old backlog")
    _link(client, orphaned["id"], archived_space["id"], "parent")
    _archive_entity(app, archived_space["id"])

    response = client.get("/api/v4/insights/monthly")
    assert response.status_code == 200
    briefing = response.get_json()["briefing"]

    sections = {section["key"]: section for section in briefing["sections"]}
    assert set(sections) == {
        "quiet_people",
        "at_risk_spaces",
        "idle_themes",
        "unowned_work",
    }
    assert sections["quiet_people"]["items"][0]["title"] == "Dana"
    assert sections["at_risk_spaces"]["items"][0]["title"] == "Acme renewal"
    assert sections["idle_themes"]["items"][0]["title"] == "EU expansion"
    assert {item["title"] for item in sections["unowned_work"]["items"]} == {
        "Close open loop",
        "Tidy old backlog",
    }


def test_tc53_monthly_omits_empty_sections_and_returns_explicit_message(client, app):
    _clear_monthly_cache(app)

    response = client.get("/api/v4/insights/monthly")
    assert response.status_code == 200
    briefing = response.get_json()["briefing"]
    assert briefing["sections"] == []
    assert briefing["message"] == EMPTY_MONTHLY_HEALTH_MESSAGE

    theme = _create_entity(
        client,
        "theme",
        "Roadmap horizon",
        due_at=(datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
    )
    _rewind_entity(app, theme["id"], days=30)
    _clear_monthly_cache(app)

    response = client.get("/api/v4/insights/monthly")
    assert response.status_code == 200
    briefing = response.get_json()["briefing"]
    assert [section["key"] for section in briefing["sections"]] == ["idle_themes"]
    assert briefing["message"] == ""
