"""Integration tests for meeting prep via /ask and person detail (UC-8)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from extensions import db
from services import v4_ask


MIGRATION_010 = (
    Path(__file__).resolve().parents[2] / "scripts" / "migrations" / "010_followup_markers.sql"
)

NOW = datetime(2026, 7, 8, 15, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def apply_migration_010(app):
    assert MIGRATION_010.exists()
    with app.app_context():
        db.session.execute(db.text(MIGRATION_010.read_text()))
        db.session.commit()


def _create_entity(client, entity_type, title, **extra):
    payload = {"type": entity_type, "title": title, **extra}
    response = client.post("/api/v4/entities", json=payload)
    assert response.status_code == 201
    return response.get_json()["data"]


def _link(client, source_id, target_id, relationship_type):
    response = client.post(
        f"/api/v4/entities/{source_id}/relationships",
        json={"target_entity_id": target_id, "relationship_type": relationship_type},
    )
    assert response.status_code == 201
    return response.get_json()["data"]


def _create_marker(client, **payload):
    response = client.post("/api/v4/markers", json=payload)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def _set_operator(app, person_id):
    from models import AppSetting

    with app.app_context():
        setting = db.session.get(AppSetting, "operator_person_id")
        if setting is None:
            setting = AppSetting(key="operator_person_id", value=person_id)
            db.session.add(setting)
        else:
            setting.value = person_id
        db.session.commit()


def _seed_mutual_commitments(client, app):
    operator = _create_entity(client, "person", "Danish")
    maria = _create_entity(client, "person", "Maria")
    _set_operator(app, operator["id"])

    they_owe_task = _create_entity(
        client,
        "task",
        "Send revised contract",
        status="waiting",
        follow_up_at=(NOW - timedelta(days=2)).isoformat(),
    )
    you_owe_task = _create_entity(
        client,
        "task",
        "Share hiring plan draft",
        status="open",
        due_at=(NOW + timedelta(days=3)).isoformat(),
    )
    unrelated = _create_entity(client, "task", "Internal budget review", status="open")

    _link(client, they_owe_task["id"], maria["id"], "assigned_to")
    _link(client, you_owe_task["id"], operator["id"], "assigned_to")
    _link(client, you_owe_task["id"], maria["id"], "mentions")
    _link(client, unrelated["id"], operator["id"], "assigned_to")

    discuss_task = _create_entity(client, "task", "Platform migration")
    discuss = _create_marker(
        client,
        entity_id=discuss_task["id"],
        kind="discuss",
        person_entity_id=maria["id"],
        note="Discuss rollout timeline in next 1:1",
    )

    return {
        "operator": operator,
        "maria": maria,
        "they_owe_task": they_owe_task,
        "you_owe_task": you_owe_task,
        "unrelated": unrelated,
        "discuss": discuss,
    }


def test_uc8_ask_prep_me_includes_discuss_markers_and_mutual_commitments(client, app):
    v4_ask._clear_cache()
    seeded = _seed_mutual_commitments(client, app)

    response = client.post(
        "/api/v4/ask",
        json={"question": "Prep me for Maria"},
    )
    assert response.status_code == 200
    data = response.get_json()

    assert data["confidence"] == "high"
    assert "prep" in data
    prep = data["prep"]
    assert prep["person"]["id"] == seeded["maria"]["id"]

    discuss_ids = [marker["id"] for marker in prep["discuss_markers"]]
    assert seeded["discuss"]["id"] in discuss_ids
    assert prep["discuss_markers"][0]["note"] == "Discuss rollout timeline in next 1:1"

    they_ids = {item["id"] for item in prep["mutual_commitments"]["they_owe"]}
    you_ids = {item["id"] for item in prep["mutual_commitments"]["you_owe"]}
    assert seeded["they_owe_task"]["id"] in they_ids
    assert seeded["you_owe_task"]["id"] in you_ids
    assert seeded["unrelated"]["id"] not in you_ids

    assert data["citations"]
    cited_ids = {item["entity_id"] for item in data["citations"]}
    assert seeded["they_owe_task"]["id"] in cited_ids
    assert seeded["discuss"]["entity_id"] in cited_ids or discuss_ids


def test_person_detail_meeting_prep_includes_discuss_markers_and_mutual_commitments(client, app):
    seeded = _seed_mutual_commitments(client, app)

    response = client.get(f"/api/v4/entities/{seeded['maria']['id']}/detail")
    assert response.status_code == 200
    prep = response.get_json()["meeting_prep"]

    discuss_ids = [marker["id"] for marker in prep["discuss_markers"]]
    assert seeded["discuss"]["id"] in discuss_ids

    they_ids = {item["id"] for item in prep["mutual_commitments"]["they_owe"]}
    you_ids = {item["id"] for item in prep["mutual_commitments"]["you_owe"]}
    assert seeded["they_owe_task"]["id"] in they_ids
    assert seeded["you_owe_task"]["id"] in you_ids


def test_ask_prep_unknown_person_returns_low_confidence(client):
    v4_ask._clear_cache()
    response = client.post(
        "/api/v4/ask",
        json={"question": "Prep me for Nobody Here"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["confidence"] == "low"
    assert "couldn't find a person" in data["answer"].lower()
    assert "prep" not in data
