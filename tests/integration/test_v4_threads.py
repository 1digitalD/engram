"""Integration tests for GET /api/v4/threads."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from extensions import db
from models import EntityChunk


def _create_entity(client, entity_type, title, **extra):
    payload = {
        "type": entity_type,
        "title": title,
        "content": f"{title} content",
        **extra,
    }
    response = client.post("/api/v4/entities", json=payload)
    assert response.status_code == 201
    return response.get_json()["data"]


def _link(client, source_id, target_id, relationship_type):
    response = client.post(
        f"/api/v4/entities/{source_id}/relationships",
        json={"target_entity_id": target_id, "relationship_type": relationship_type},
    )
    assert response.status_code == 201


def test_threads_returns_active_people_and_projects(client, app):
    akash = _create_entity(client, "person", "Akash")
    blocked_task = _create_entity(client, "task", "Blocked dashboard work", status="blocked")
    _link(client, blocked_task["id"], akash["id"], "assigned_to")

    project = _create_entity(client, "project", "Launch readiness")
    overdue_task = _create_entity(
        client,
        "task",
        "Send rollout update",
        status="open",
        due_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    )
    _link(client, overdue_task["id"], project["id"], "parent")

    response = client.get("/api/v4/threads")
    assert response.status_code == 200
    payload = response.get_json()
    assert "threads" in payload

    by_id = {thread["id"]: thread for thread in payload["threads"]}
    assert akash["id"] in by_id
    assert project["id"] in by_id
    assert by_id[akash["id"]]["type"] == "person"
    assert by_id[project["id"]]["type"] == "project"
    assert by_id[akash["id"]]["name"] == "Akash"
    assert by_id[project["id"]]["name"] == "Launch readiness"
    assert isinstance(by_id[akash["id"]]["key_items"], list)
    assert len(by_id[akash["id"]]["key_items"]) >= 1


def test_threads_ranked_by_attention(client, app):
    quiet_person = _create_entity(client, "person", "Quiet Person")
    quiet_task = _create_entity(client, "task", "Low priority follow-up", status="open")
    _link(client, quiet_task["id"], quiet_person["id"], "assigned_to")

    hot_person = _create_entity(client, "person", "Hot Person")
    hot_task = _create_entity(
        client,
        "task",
        "Urgent blocked work",
        status="blocked",
        due_at=(datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        properties={"priority": "urgent"},
    )
    _link(client, hot_task["id"], hot_person["id"], "assigned_to")

    response = client.get("/api/v4/threads", query_string={"limit": 10})
    assert response.status_code == 200
    threads = response.get_json()["threads"]
    ids = [thread["id"] for thread in threads]
    assert hot_person["id"] in ids
    assert quiet_person["id"] in ids
    assert ids.index(hot_person["id"]) < ids.index(quiet_person["id"])
    assert threads[0]["attention_score"] >= threads[-1]["attention_score"]


def test_threads_includes_last_context(client, app):
    person = _create_entity(client, "person", "Henry")
    task = _create_entity(client, "task", "Loop in Finance", status="open")
    _link(client, task["id"], person["id"], "assigned_to")

    note_response = client.post(
        f"/api/v4/entities/{task['id']}/activity_updates",
        json={"content": "Loop in Finance before the next 1:1"},
    )
    assert note_response.status_code == 201

    response = client.get("/api/v4/threads")
    assert response.status_code == 200
    thread = next(item for item in response.get_json()["threads"] if item["id"] == person["id"])
    assert thread["last_context"]
    assert "Loop in Finance" in thread["last_context"]
    assert thread["last_activity_at"]


def test_threads_topic_clustering_optional(client, app):
    note_a = _create_entity(client, "note", "Orphan topic A", content="Shared rollout planning notes")
    note_b = _create_entity(client, "note", "Orphan topic B", content="Shared rollout planning follow-up")

    vector = [1.0] + [0.0] * 1535
    with app.app_context():
        for note in (note_a, note_b):
            db.session.add(
                EntityChunk(
                    entity_id=note["id"],
                    chunk_index=0,
                    chunk_text=note["content"],
                    embedding=vector,
                    embedding_model="test",
                )
            )
        db.session.commit()

    with patch("api.v4_entities._topic_threads") as mock_topics:
        mock_topics.return_value = [{
            "id": "topic:test",
            "type": "topic",
            "name": "Shared rollout",
            "attention_score": 12,
            "attention_reasons": [],
            "last_activity_at": datetime.now(timezone.utc).isoformat(),
            "last_context": "Shared rollout planning notes",
            "key_items": [],
        }]
        response = client.get("/api/v4/threads")
        assert response.status_code == 200
        payload = response.get_json()
        assert isinstance(payload["threads"], list)

    response = client.get("/api/v4/threads")
    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload["threads"], list)
    assert all(thread["type"] in {"person", "project", "topic"} for thread in payload["threads"])
