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


def test_threads_returns_active_people_and_projects(client):
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


def test_threads_total_count_and_summary_are_not_capped_by_default_limit(client):
    for index in range(25):
        project = _create_entity(client, "project", f"Launch readiness {index}")
        overdue_task = _create_entity(
            client,
            "task",
            f"Send rollout update {index}",
            status="open",
            due_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        )
        _link(client, overdue_task["id"], project["id"], "parent")

    threads_response = client.get("/api/v4/threads")
    assert threads_response.status_code == 200
    threads_payload = threads_response.get_json()
    assert len(threads_payload["threads"]) == 20
    assert threads_payload["total_count"] == 25

    expanded_response = client.get("/api/v4/threads?limit=200")
    assert expanded_response.status_code == 200
    expanded_payload = expanded_response.get_json()
    assert len(expanded_payload["threads"]) == 25
    assert expanded_payload["total_count"] == 25

    summary_response = client.get("/api/v4/summary")
    assert summary_response.status_code == 200
    summary = summary_response.get_json()
    assert summary["threads_count"] == 25


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
        assert payload["total_count"] >= 1


def test_threads_rejects_unsupported_rank(client):
    response = client.get("/api/v4/threads?rank=recent")
    assert response.status_code == 400
