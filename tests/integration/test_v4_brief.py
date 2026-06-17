"""Tests for the ranked daily brief (LLM mocked)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from extensions import db
from models import AppSetting
from services import v4_brief


def _entity(client, entity_type, title, **extra):
    return client.post("/api/v4/entities", json={"type": entity_type, "title": title, **extra}).get_json()["data"]


def _link(client, source_id, target_id, relationship_type):
    response = client.post(
        f"/api/v4/entities/{source_id}/relationships",
        json={"target_entity_id": target_id, "relationship_type": relationship_type},
    )
    assert response.status_code == 201


def _clear_brief_cache():
    v4_brief._BRIEF_CACHE["brief"] = None
    v4_brief._BRIEF_CACHE["generated_at"] = None


def test_brief_generates_validates_and_caches(client, app):
    _clear_brief_cache()
    project = _entity(client, "project", "Agent Platform")
    task = _entity(client, "task", "Ship CS1 contract review")

    fake_model_output = {
        "narrative": "Two things need decisions today.",
        "items": [
            {"entity_id": task["id"], "title": "Ship CS1 contract review", "why_now": "Due and blocking CS2.", "urgency": 5},
            {"entity_id": project["id"], "title": "Agent Platform", "why_now": "Roadmap decision pending.", "urgency": 9},
            {"entity_id": "hallucinated-id", "title": "Ghost", "why_now": "n/a", "urgency": 3},
        ],
    }

    with patch("services.v4_brief.generate_brief", wraps=None) as gen:
        from services import v4_brief
        with app.app_context():
            validated = v4_brief._validate_brief(fake_model_output)

    assert validated["narrative"] == "Two things need decisions today."
    assert [i["entity_id"] for i in validated["items"]] == [task["id"], project["id"]]
    # urgency clamped to 1..5
    assert validated["items"][1]["urgency"] == 5
    assert validated["items"][0]["entity_type"] == "task"


def test_brief_endpoint_serves_cache_and_regenerates_on_force(client, app):
    _clear_brief_cache()
    cached = {
        "narrative": "Cached brief.",
        "items": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "test",
    }
    v4_brief._BRIEF_CACHE["brief"] = cached
    v4_brief._BRIEF_CACHE["generated_at"] = cached["generated_at"]

    response = client.get("/api/v4/brief").get_json()
    assert response["from_cache"] is True
    assert response["brief"]["narrative"] == "Cached brief."

    fresh = dict(cached, narrative="Fresh brief.", generated_at=datetime.now(timezone.utc).isoformat())
    with patch("services.v4_brief.generate_brief", return_value=fresh):
        response = client.get("/api/v4/brief?force=1").get_json()
    assert response["from_cache"] is False
    assert response["brief"]["narrative"] == "Fresh brief."

    # Forced result was cached in-process, not persisted in app_settings.
    response = client.get("/api/v4/brief").get_json()
    assert response["from_cache"] is True
    assert response["brief"]["narrative"] == "Fresh brief."
    with app.app_context():
        assert db.session.get(AppSetting, "daily_brief") is None


def test_brief_endpoint_without_model_returns_empty(client, app):
    _clear_brief_cache()
    # TESTING mode disables generation and there is no cache or signal.
    with app.app_context():
        setting = db.session.get(AppSetting, "daily_brief")
        if setting is not None:
            db.session.delete(setting)
            db.session.commit()
    response = client.get("/api/v4/brief").get_json()
    assert response["brief"] is None


def test_brief_endpoint_without_model_falls_back_to_runtime_heuristics(client, app):
    _clear_brief_cache()
    now = datetime.now(timezone.utc)
    overdue = _entity(client, "task", "Ship launch note", due_at=(now - timedelta(days=1)).isoformat())
    akash = _entity(client, "person", "Akash")
    quiet_task = _entity(
        client,
        "task",
        "Review dashboard draft",
        follow_up_at=(now - timedelta(days=4)).isoformat(),
        status="open",
    )
    _link(client, quiet_task["id"], akash["id"], "assigned_to")

    response = client.get("/api/v4/brief").get_json()

    assert response["from_cache"] is False
    assert response["brief"]["model"] == "heuristic"
    assert response["brief"]["narrative"]
    item_ids = [item["entity_id"] for item in response["brief"]["items"]]
    assert overdue["id"] in item_ids
    assert quiet_task["id"] in item_ids
    quiet_item = next(item for item in response["brief"]["items"] if item["entity_id"] == quiet_task["id"])
    assert "no update" in quiet_item["why_now"].lower()

    cached_response = client.get("/api/v4/brief").get_json()
    assert cached_response["from_cache"] is True
    assert cached_response["brief"]["model"] == "heuristic"


def test_brief_snapshot_includes_runtime_coordination_signals(client, app):
    _clear_brief_cache()
    now = datetime.now(timezone.utc)
    akash = _entity(client, "person", "Akash")
    blocked = _entity(client, "task", "Prep rollout decision", status="blocked")
    blocker = _entity(client, "task", "Security approval", status="open")
    quiet_task = _entity(
        client,
        "task",
        "Review dashboard draft",
        follow_up_at=(now - timedelta(days=5)).isoformat(),
        status="open",
    )
    _link(client, blocked["id"], akash["id"], "assigned_to")
    _link(client, quiet_task["id"], akash["id"], "assigned_to")
    _link(client, blocker["id"], blocked["id"], "blocks")

    with app.app_context():
        snapshot = v4_brief._snapshot()

    assert "today" in snapshot
    assert "coordination_radar" in snapshot
    assert any(item["id"] == quiet_task["id"] for item in snapshot["today"]["delegations_quiet"])
    assert any(item["entity"]["id"] == blocked["id"] for item in snapshot["today"]["dependency_interventions"])
    assert any(item["entity_id"] == akash["id"] for item in snapshot["coordination_radar"]["people"])
