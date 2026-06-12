"""Tests for the ranked daily brief (LLM mocked)."""

from datetime import datetime, timezone
from unittest.mock import patch

from extensions import db
from models import AppSetting


def _entity(client, entity_type, title, **extra):
    return client.post("/api/v4/entities", json={"type": entity_type, "title": title, **extra}).get_json()["data"]


def test_brief_generates_validates_and_caches(client, app):
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
    cached = {
        "narrative": "Cached brief.",
        "items": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "test",
    }
    with app.app_context():
        db.session.add(AppSetting(key="daily_brief", value=cached))
        db.session.commit()

    response = client.get("/api/v4/brief").get_json()
    assert response["from_cache"] is True
    assert response["brief"]["narrative"] == "Cached brief."

    fresh = dict(cached, narrative="Fresh brief.", generated_at=datetime.now(timezone.utc).isoformat())
    with patch("services.v4_brief.generate_brief", return_value=fresh):
        response = client.get("/api/v4/brief?force=1").get_json()
    assert response["from_cache"] is False
    assert response["brief"]["narrative"] == "Fresh brief."

    # Forced result was persisted to the cache.
    response = client.get("/api/v4/brief").get_json()
    assert response["brief"]["narrative"] == "Fresh brief."


def test_brief_endpoint_without_model_returns_empty(client, app):
    # TESTING mode disables generation and there is no cache.
    with app.app_context():
        setting = db.session.get(AppSetting, "daily_brief")
        if setting is not None:
            db.session.delete(setting)
            db.session.commit()
    response = client.get("/api/v4/brief").get_json()
    assert response["brief"] is None
