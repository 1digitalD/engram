"""Phase 4 markers: CRUD, firing into Today, discuss prep payloads (TC-40..42, EC-15..17)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from extensions import db
from models import FollowupMarker
from services.v4_markers import prep_payload_for_person


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


def _create_marker(client, **payload):
    response = client.post("/api/v4/markers", json=payload)
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def test_migration_010_applies_cleanly(app):
    with app.app_context():
        row = db.session.execute(
            db.text(
                "SELECT to_regclass('public.followup_markers') AS table_name"
            )
        ).one()
        assert row.table_name == "followup_markers"


def test_marker_crud_round_trip(client):
    task = _create_entity(client, "task", "Ship feature")
    person = _create_entity(client, "person", "Sam")

    created = _create_marker(
        client,
        entity_id=task["id"],
        kind="nudge",
        due_at=(NOW - timedelta(hours=2)).isoformat(),
        note="Nudge Sam",
    )
    assert created["kind"] == "nudge"
    assert created["fired_at"] is None

    listed = client.get("/api/v4/markers", query_string={"entity_id": task["id"]})
    assert listed.status_code == 200
    assert len(listed.get_json()["data"]) == 1

    patched = client.patch(
        f"/api/v4/markers/{created['id']}",
        json={"note": "Nudge Sam again"},
    )
    assert patched.status_code == 200
    assert patched.get_json()["data"]["note"] == "Nudge Sam again"

    discuss = _create_marker(
        client,
        entity_id=task["id"],
        kind="discuss",
        person_entity_id=person["id"],
        note="Discuss migration path",
    )
    assert discuss["person_entity_id"] == person["id"]

    deleted = client.delete(f"/api/v4/markers/{discuss['id']}")
    assert deleted.status_code == 200


def test_tc40_due_nudge_marker_fires_into_today_once(client, app):
    task = _create_entity(client, "task", "Contract review")
    marker = _create_marker(
        client,
        entity_id=task["id"],
        kind="nudge",
        due_at=(NOW - timedelta(hours=1)).isoformat(),
        note="Send reminder",
    )

    first = client.get("/api/v4/today")
    assert first.status_code == 200
    first_payload = first.get_json()
    fired_ids = [item["id"] for item in first_payload["fired_markers"]]
    assert marker["id"] in fired_ids
    assert len([item for item in first_payload["fired_markers"] if item["id"] == marker["id"]]) == 1

    with app.app_context():
        stored = db.session.get(FollowupMarker, marker["id"])
        assert stored.fired_at is not None

    second = client.get("/api/v4/today")
    assert second.status_code == 200
    second_ids = [item["id"] for item in second.get_json()["fired_markers"]]
    assert marker["id"] in second_ids
    assert len(second_ids) == len(set(second_ids))


def test_tc41_discuss_marker_excluded_from_today_in_prep_payload(client, app):
    task = _create_entity(client, "task", "CMS migration")
    person = _create_entity(client, "person", "Priya")
    discuss = _create_marker(
        client,
        entity_id=task["id"],
        kind="discuss",
        person_entity_id=person["id"],
        note="Discuss in next 1:1",
    )

    today = client.get("/api/v4/today")
    assert today.status_code == 200
    today_ids = [item["id"] for item in today.get_json()["fired_markers"]]
    assert discuss["id"] not in today_ids

    with app.app_context():
        prep = prep_payload_for_person(person["id"])
    assert len(prep) == 1
    assert prep[0]["id"] == discuss["id"]
    assert prep[0]["note"] == "Discuss in next 1:1"


def test_tc42_ec15_marker_on_archived_entity_auto_resolved(client, app):
    task = _create_entity(client, "task", "Legacy cleanup")
    marker = _create_marker(
        client,
        entity_id=task["id"],
        kind="nudge",
        due_at=(NOW - timedelta(hours=1)).isoformat(),
    )

    archived = client.patch(f"/api/v4/entities/{task['id']}", json={"lifecycle": "archived"})
    assert archived.status_code == 200

    with app.app_context():
        stored = db.session.get(FollowupMarker, marker["id"])
        assert stored.resolved_at is not None
        assert stored.fired_at is None

    today = client.get("/api/v4/today")
    assert today.status_code == 200
    today_ids = [item["id"] for item in today.get_json()["fired_markers"]]
    assert marker["id"] not in today_ids


def test_ec16_past_due_marker_fires_on_next_cycle_once(client):
    task = _create_entity(client, "task", "Backdated follow-up")
    marker = _create_marker(
        client,
        entity_id=task["id"],
        kind="nudge",
        due_at=(NOW - timedelta(days=3)).isoformat(),
    )

    today = client.get("/api/v4/today")
    assert today.status_code == 200
    payload = today.get_json()
    assert marker["id"] in [item["id"] for item in payload["fired_markers"]]

    again = client.get("/api/v4/today")
    assert again.status_code == 200
    fired = again.get_json()["fired_markers"]
    assert len([item for item in fired if item["id"] == marker["id"]]) == 1


def test_ec17_two_markers_same_entity_same_day_fire_separately(client):
    task = _create_entity(client, "task", "Two reminders")
    due = (NOW - timedelta(hours=2)).isoformat()
    first = _create_marker(
        client,
        entity_id=task["id"],
        kind="nudge",
        due_at=due,
        note="First",
    )
    second = _create_marker(
        client,
        entity_id=task["id"],
        kind="nudge",
        due_at=due,
        note="Second",
    )

    today = client.get("/api/v4/today")
    assert today.status_code == 200
    fired = today.get_json()["fired_markers"]
    fired_for_task = [item for item in fired if item["entity_id"] == task["id"]]
    assert {item["id"] for item in fired_for_task} == {first["id"], second["id"]}
    assert len(fired_for_task) == 2
