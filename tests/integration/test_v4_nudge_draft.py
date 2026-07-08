"""Integration tests for POST /commitments/<id>/nudge-draft (TC-44, UC-7)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from extensions import db
from models import Entity, EntityLink


NOW = datetime(2026, 7, 8, 15, 0, tzinfo=timezone.utc)


def _create_entity(client, entity_type, title, **extra):
    payload = {"type": entity_type, "title": title, **extra}
    response = client.post("/api/v4/entities", json=payload)
    assert response.status_code == 201
    return response.get_json()["data"]


def _seed_waiting_on_commitment(client):
    owner = _create_entity(client, "person", "Sam")
    task = _create_entity(
        client,
        "task",
        "Complete security questionnaire",
        status="waiting",
        follow_up_at=(NOW - timedelta(days=4)).isoformat(),
    )
    note = _create_entity(
        client,
        "note",
        "Standup notes",
        content="Sam will complete the security questionnaire by end of June.",
    )

    for source_id, target_id, relationship_type in (
        (task["id"], owner["id"], "assigned_to"),
        (task["id"], note["id"], "derived_from"),
    ):
        response = client.post(
            f"/api/v4/entities/{source_id}/links",
            json={"target_id": target_id, "relationship_type": relationship_type},
        )
        assert response.status_code == 201

    return task, owner, note


def test_tc44_nudge_draft_contains_original_ask_date_and_receipts(client):
    task, owner, _note = _seed_waiting_on_commitment(client)

    response = client.post(f"/api/v4/commitments/{task['id']}/nudge-draft")
    assert response.status_code == 200
    data = response.get_json()["data"]

    assert data["commitment_id"] == task["id"]
    assert data["auto_sent"] is False
    assert "security questionnaire" in data["original_ask"].lower()
    assert data["committed_at"]
    assert len(data["receipts"]) >= 2
    assert any(r.get("label") == "original ask" for r in data["receipts"])
    assert any(r.get("label") == "committed date" for r in data["receipts"])
    assert data["draft"]
    assert owner["title"] in data["draft"] or "Sam" in data["draft"]


def test_nudge_draft_never_auto_sends_or_mutates_commitment(client, app):
    task, _owner, _note = _seed_waiting_on_commitment(client)

    before_links = client.get(f"/api/v4/entities/{task['id']}/relationships")
    assert before_links.status_code == 200
    before_count = len(before_links.get_json().get("data") or [])

    response = client.post(f"/api/v4/commitments/{task['id']}/nudge-draft")
    assert response.status_code == 200
    assert response.get_json()["data"]["auto_sent"] is False

    after = client.get(f"/api/v4/entities/{task['id']}")
    assert after.status_code == 200
    assert after.get_json()["data"]["status"] == "waiting"

    after_links = client.get(f"/api/v4/entities/{task['id']}/relationships")
    assert len(after_links.get_json().get("data") or []) == before_count

    with app.app_context():
        activity_links = (
            db.session.query(EntityLink)
            .join(Entity, Entity.id == EntityLink.source_entity_id)
            .filter(
                EntityLink.target_entity_id == task["id"],
                EntityLink.relationship_type == "activity_update",
            )
            .count()
        )
        assert activity_links == 0


def test_nudge_draft_uses_mocked_llm_when_enabled(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ENGRAM_ALLOW_TEST_AI", "1")

    task, _owner, _note = _seed_waiting_on_commitment(client)

    with patch(
        "services.v4_nudge_draft.get_openai_client",
    ) as mock_client_factory:
        mock_client = mock_client_factory.return_value
        mock_client.chat.completions.create.return_value.choices = [
            type(
                "Choice",
                (),
                {
                    "message": type(
                        "Message",
                        (),
                        {
                            "content": '{"draft":"Hi Sam, quick nudge on the security questionnaire from 28 Jun."}'
                        },
                    )()
                },
            )()
        ]

        response = client.post(f"/api/v4/commitments/{task['id']}/nudge-draft")

    assert response.status_code == 200
    draft = response.get_json()["data"]["draft"]
    assert "security questionnaire" in draft.lower()
    assert mock_client.chat.completions.create.called


def test_nudge_draft_returns_404_for_missing_commitment(client):
    response = client.post("/api/v4/commitments/missing-task/nudge-draft")
    assert response.status_code == 404
