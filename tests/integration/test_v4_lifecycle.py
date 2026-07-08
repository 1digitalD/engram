"""Phase 3 lifecycle verbs: amend, archive, delete, redact (TC-34..36, EC-22, EC-23)."""

from pathlib import Path
from unittest.mock import patch

import pytest
from extensions import db
from models import AppSetting, Entity, EntityChunk, EntityEvent, EntityLink


MIGRATION_009 = (
    Path(__file__).resolve().parents[2] / "scripts" / "migrations" / "009_redacted_lifecycle.sql"
)

REDACTED_LABEL = "cites a redacted entry"


@pytest.fixture(scope="module", autouse=True)
def apply_migration_009(app):
    assert MIGRATION_009.exists()
    with app.app_context():
        db.session.execute(db.text(MIGRATION_009.read_text()))
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


def _set_operator(app, person_id):
    with app.app_context():
        setting = db.session.get(AppSetting, "operator_person_id")
        if setting is None:
            setting = AppSetting(key="operator_person_id", value=person_id)
            db.session.add(setting)
        else:
            setting.value = person_id
        db.session.commit()


def _add_chunk(app, entity_id, text, embedding):
    with app.app_context():
        db.session.add(
            EntityChunk(
                entity_id=entity_id,
                chunk_index=0,
                chunk_text=text,
                embedding=embedding,
                embedding_model="test",
            )
        )
        db.session.commit()


def test_migration_009_applies_cleanly(app):
    with app.app_context():
        row = db.session.execute(
            db.text(
                "SELECT pg_get_constraintdef(oid) AS defn "
                "FROM pg_constraint WHERE conname = 'chk_entities_lifecycle'"
            )
        ).one()
        assert "redacted" in row.defn


def test_tc34_amend_activity_update_records_old_and_new_content(client, app):
    task = _create_entity(client, "task", "Ship feature")
    created = client.post(
        f"/api/v4/entities/{task['id']}/activity_updates",
        json={"content": "Initial progress update."},
    )
    assert created.status_code == 201
    note_id = created.get_json()["data"]["id"]

    amended = client.patch(
        f"/api/v4/entities/{note_id}",
        json={"content": "Corrected progress update."},
    )
    assert amended.status_code == 200

    with app.app_context():
        events = (
            EntityEvent.query.filter_by(entity_id=note_id, event_type="updated")
            .order_by(EntityEvent.created_at.desc())
            .all()
        )
        assert events
        amend_event = events[0]
        assert amend_event.reason == "amended"
        assert amend_event.old_value["content"] == "Initial progress update."
        assert amend_event.new_value["content"] == "Corrected progress update."


def test_tc35_archive_is_reversible_and_excluded_from_workboard(client, app):
    operator = _create_entity(client, "person", "Operator")
    space = _create_entity(client, "project", "Lifecycle space")
    task = _create_entity(client, "task", "Archivable task")

    _set_operator(app, operator["id"])
    _link(client, task["id"], operator["id"], "assigned_to")
    _link(client, task["id"], space["id"], "parent")

    before = client.get("/api/v4/workboard", query_string={"group": "space"})
    assert task["id"] in {
        item["id"]
        for group in before.get_json()["data"]["groups"]
        for item in group["items"]
    }

    archived = client.patch(
        f"/api/v4/entities/{task['id']}",
        json={"lifecycle": "archived"},
    )
    assert archived.status_code == 200
    assert archived.get_json()["data"]["lifecycle"] == "archived"

    excluded = client.get("/api/v4/workboard", query_string={"group": "space"})
    assert task["id"] not in {
        item["id"]
        for group in excluded.get_json()["data"]["groups"]
        for item in group["items"]
    }

    with app.app_context():
        archive_event = EntityEvent.query.filter_by(
            entity_id=task["id"], event_type="archived"
        ).one()
        assert archive_event.old_value["lifecycle"] == "active"
        assert archive_event.new_value["lifecycle"] == "archived"

    restored = client.patch(
        f"/api/v4/entities/{task['id']}",
        json={"lifecycle": "active"},
    )
    assert restored.status_code == 200
    assert restored.get_json()["data"]["lifecycle"] == "active"

    note = _create_entity(client, "note", "Delete me", content="Sensitive body")
    deleted = client.delete(f"/api/v4/entities/{note['id']}")
    assert deleted.status_code == 200
    assert deleted.get_json()["data"]["lifecycle"] == "deleted"

    with app.app_context():
        tombstone = EntityEvent.query.filter_by(
            entity_id=note["id"], event_type="deleted"
        ).one()
        assert tombstone.old_value["lifecycle"] == "active"
        assert tombstone.new_value["lifecycle"] == "deleted"


def test_tc36_redact_note_tombstones_content_removes_chunks_and_breaks_citations(client, app):
    note = _create_entity(
        client,
        "note",
        "Secret standup",
        content="Customer account numbers were discussed here.",
    )
    _add_chunk(app, note["id"], "Customer account numbers were discussed here.", [1.0] + [0.0] * 1535)

    redacted = client.post(f"/api/v4/entities/{note['id']}/redact")
    assert redacted.status_code == 200
    data = redacted.get_json()["data"]
    assert data["lifecycle"] == "redacted"
    assert data["content"] == "[Content redacted]"
    assert data["title"] == "[Redacted note]"

    with app.app_context():
        assert EntityChunk.query.filter_by(entity_id=note["id"]).count() == 0
        event = EntityEvent.query.filter_by(entity_id=note["id"], event_type="redacted").one()
        assert event.old_value is None
        assert event.new_value["lifecycle"] == "redacted"

    with patch("services.embeddings._embed_texts", return_value=[[1.0] + [0.0] * 1535]):
        search = client.get("/api/v4/search?q=account+numbers&mode=semantic")
    assert search.status_code == 200
    assert all(row["entity"]["id"] != note["id"] for row in search.get_json()["results"])

    task = _create_entity(client, "task", "Follow up on accounts")
    _link(client, task["id"], note["id"], "derived_from")
    detail = client.get(f"/api/v4/entities/{task['id']}/detail")
    assert detail.status_code == 200
    source_items = next(
        section for section in detail.get_json()["sections"] if section["key"] == "source_notes"
    )["items"]
    assert len(source_items) == 1
    assert source_items[0]["citation_state"] == "redacted"
    assert source_items[0]["citation_label"] == REDACTED_LABEL


def test_ec22_redacted_source_note_keeps_commitment_and_shows_redacted_receipt(client, app):
    note = _create_entity(
        client,
        "note",
        "Accepted commitment source",
        content="Priya will deliver the migration plan by Friday.",
    )
    commitment = _create_entity(
        client,
        "task",
        "Deliver migration plan",
        content="From accepted report",
        status="open",
    )
    _link(client, commitment["id"], note["id"], "derived_from")

    redacted = client.post(f"/api/v4/entities/{note['id']}/redact")
    assert redacted.status_code == 200

    got_commitment = client.get(f"/api/v4/entities/{commitment['id']}")
    assert got_commitment.status_code == 200
    body = got_commitment.get_json()["data"]
    assert body["title"] == "Deliver migration plan"
    assert body["content"] == "From accepted report"
    assert body["status"] == "open"

    detail = client.get(f"/api/v4/entities/{commitment['id']}/detail")
    source_items = next(
        section for section in detail.get_json()["sections"] if section["key"] == "source_notes"
    )["items"]
    assert source_items[0]["entity"]["lifecycle"] == "redacted"
    assert source_items[0]["citation_label"] == REDACTED_LABEL

    with app.app_context():
        assert db.session.get(Entity, commitment["id"]) is not None
        assert (
            EntityLink.query.filter_by(
                source_entity_id=commitment["id"],
                target_entity_id=note["id"],
                relationship_type="derived_from",
            ).count()
            == 1
        )


def test_ec23_delete_person_with_open_tasks_is_blocked(client, app):
    person = _create_entity(client, "person", "Owner with tasks")
    task = _create_entity(client, "task", "Open owned task", status="open")
    _link(client, task["id"], person["id"], "assigned_to")

    response = client.delete(f"/api/v4/entities/{person['id']}")
    assert response.status_code == 409
    assert "open assigned" in response.get_json()["error"].lower()

    with app.app_context():
        assert db.session.get(Entity, person["id"]).lifecycle == "active"


def test_redact_rejects_non_notes(client):
    task = _create_entity(client, "task", "Not a note")
    response = client.post(f"/api/v4/entities/{task['id']}/redact")
    assert response.status_code == 400
    assert "note" in response.get_json()["error"].lower()
