"""Integration tests for v6 theme creation and promotion."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2

from extensions import db
from models import Decision, Entity, EntityEvent, EntityLink


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "migrations" / "011_theme_type.sql"
)


def _create_entity(client, entity_type, title, **extra):
    payload = {"type": entity_type, "title": title, "content": f"{title} content"}
    payload.update(extra)
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


def _db_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        raise RuntimeError("TEST_DATABASE_URL not set")
    return url


def test_migration_011_applies_to_test_db():
    sql = MIGRATION_PATH.read_text()
    with psycopg2.connect(_db_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def test_tc50_theme_type_is_accepted_and_excluded_from_workboard(client):
    theme = _create_entity(client, "theme", "Hiring pipeline")

    response = client.get("/api/v4/workboard", query_string={"group": "space"})
    assert response.status_code == 200
    body = response.get_json()

    assert theme["type"] == "theme"
    assert body["meta"]["total"] == 0
    assert body["data"]["groups"] == []


def test_tc51_promote_theme_to_project_preserves_links_events_and_decisions(client, app):
    theme = _create_entity(
        client,
        "theme",
        "Pricing refresh",
        tags=["weekly", "strategy"],
    )
    note = _create_entity(client, "note", "Pricing transcript")
    person = _create_entity(client, "person", "Maria")
    _link(client, note["id"], theme["id"], "mentions")
    _link(client, theme["id"], person["id"], "related")

    decision_response = client.post(
        "/api/v4/decisions",
        json={
            "thread_id": theme["id"],
            "statement": "Ship usage-based pricing experiment",
            "decided_by": "user",
            "source_note_id": note["id"],
        },
    )
    assert decision_response.status_code == 201, decision_response.get_json()

    before_detail = client.get(f"/api/v4/entities/{theme['id']}/detail")
    assert before_detail.status_code == 200
    assert before_detail.get_json()["decisions_count"] == 1

    promote = client.post(f"/api/v4/entities/{theme['id']}/promote")
    assert promote.status_code == 200, promote.get_json()
    body = promote.get_json()["data"]
    assert body["id"] == theme["id"]
    assert body["type"] == "project"
    assert body["status"] == "active"

    after_detail = client.get(f"/api/v4/entities/{theme['id']}/detail")
    assert after_detail.status_code == 200
    assert after_detail.get_json()["entity"]["type"] == "project"
    assert after_detail.get_json()["decisions_count"] == 1

    with app.app_context():
        entity = db.session.get(Entity, theme["id"])
        assert entity.type == "project"
        assert EntityLink.query.filter_by(target_entity_id=theme["id"]).count() == 1
        assert EntityLink.query.filter_by(source_entity_id=theme["id"]).count() == 1
        assert Decision.query.filter_by(thread_id=theme["id"]).count() == 1

        promoted_events = EntityEvent.query.filter_by(
            entity_id=theme["id"],
            event_type="promoted",
        ).all()
        assert len(promoted_events) == 1
        assert promoted_events[0].old_value["type"] == "theme"
        assert promoted_events[0].new_value["type"] == "project"


def test_tc51_promote_rejects_non_theme_and_project_to_theme(client):
    project = _create_entity(client, "project", "Existing space")
    task = _create_entity(client, "task", "Follow up")

    not_theme = client.post(f"/api/v4/entities/{task['id']}/promote")
    assert not_theme.status_code == 400
    assert "theme" in not_theme.get_json()["error"]

    rejected = client.post(
        f"/api/v4/entities/{project['id']}/promote",
        json={"type": "theme"},
    )
    assert rejected.status_code == 400
    assert "one-way" in rejected.get_json()["error"]


def test_ec24_promote_theme_conflict_returns_merge_or_rename_options(client):
    _create_entity(client, "project", "Apollo")
    theme = _create_entity(client, "theme", "Apollo")

    response = client.post(f"/api/v4/entities/{theme['id']}/promote")
    assert response.status_code == 409
    body = response.get_json()
    assert "conflict" in body
    assert body["conflict"]["options"] == ["merge_into", "rename"]


def test_tc52_convert_endpoint_is_retired(client):
    theme = _create_entity(client, "theme", "Weekly digest")

    response = client.post(f"/api/v4/entities/{theme['id']}/convert", json={"type": "project"})
    assert response.status_code == 410
    assert "promote" in response.get_json()["error"]
