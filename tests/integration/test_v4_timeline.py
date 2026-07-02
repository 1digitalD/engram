"""Integration tests for /api/v4/timeline."""

import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import psycopg2
import pytest


def _create_entity(client, entity_type, title, **extra):
    payload = {"type": entity_type, "title": title, "content": f"{title} content"}
    payload.update(extra)
    response = client.post("/api/v4/entities", json=payload)
    assert response.status_code == 201
    return response.get_json()["data"]["id"]


def _link(client, source_id, target_id, relationship_type):
    response = client.post(
        f"/api/v4/entities/{source_id}/relationships",
        json={"target_entity_id": target_id, "relationship_type": relationship_type},
    )
    assert response.status_code == 201
    return response.get_json()["data"]["id"]


def _db_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        raise RuntimeError("TEST_DATABASE_URL not set")
    return url


def _raw_execute(sql, params=None):
    with psycopg2.connect(_db_url()) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql, params)


def _timeline(client, **params):
    response = client.get("/api/v4/timeline", query_string=params)
    assert response.status_code == 200
    return response.get_json()


def test_timeline_returns_events_desc(client):
    project_id = _create_entity(client, "project", "Timeline project")
    task_id = _create_entity(client, "task", "Timeline task")
    _link(client, task_id, project_id, "parent")

    response = client.patch(f"/api/v4/entities/{task_id}", json={"status": "in_progress"})
    assert response.status_code == 200

    data = _timeline(client)
    events = data["events"]
    assert len(events) >= 1

    occurred = [event["occurred_at"] for event in events]
    assert occurred == sorted(occurred, reverse=True)


def test_timeline_filters_by_thread(client):
    project_id = _create_entity(client, "project", "Thread filter project")
    task_id = _create_entity(client, "task", "Thread filter task")
    other_project_id = _create_entity(client, "project", "Other project")
    other_task_id = _create_entity(client, "task", "Other task")

    _link(client, task_id, project_id, "parent")
    _link(client, other_task_id, other_project_id, "parent")

    response = client.patch(f"/api/v4/entities/{task_id}", json={"status": "in_progress"})
    assert response.status_code == 200
    response = client.patch(f"/api/v4/entities/{other_task_id}", json={"status": "in_progress"})
    assert response.status_code == 200

    data = _timeline(client, thread_id=project_id)
    events = data["events"]
    assert len(events) >= 1
    assert all(event["thread_id"] == project_id for event in events)

    entity_ids = {event["entity_id"] for event in events}
    assert task_id in entity_ids
    assert other_task_id not in entity_ids


def test_timeline_filtered_by_actor(client):
    project_id = _create_entity(client, "project", "Actor filter project")
    task_id = _create_entity(client, "task", "Actor filter task")
    _link(client, task_id, project_id, "parent")

    response = client.patch(f"/api/v4/entities/{task_id}", json={"status": "in_progress"})
    assert response.status_code == 200

    data = _timeline(client, actor="user")
    events = data["events"]
    assert len(events) >= 1
    assert all(event["actor"] == "user" for event in events)

    missing = _timeline(client, actor="agent:nonexistent")
    assert missing["events"] == []


def test_timeline_actor_prefix_filter_matches_agent_family(client, app):
    task_id = _create_entity(client, "task", "Agent family task")

    with app.app_context():
        from extensions import db
        from models import EntityEvent

        db.session.add(
            EntityEvent(
                entity_id=task_id,
                event_type="ai_processed",
                actor="agent:v4-review",
                new_value={"title": "Agent family task"},
            )
        )
        db.session.commit()

    exact = _timeline(client, actor="agent:v4-review")
    assert len(exact["events"]) >= 1

    prefix = _timeline(client, actor="agent:")
    assert len(prefix["events"]) >= 1
    assert all(event["actor"].startswith("agent:") for event in prefix["events"])


def test_timeline_pagination(client):
    project_id = _create_entity(client, "project", "Pagination project")
    for index in range(5):
        task_id = _create_entity(client, "task", f"Pagination task {index}")
        _link(client, task_id, project_id, "parent")

    data = _timeline(client, limit=3)
    assert len(data["events"]) == 3
    assert data["next_offset"] == 3

    data2 = _timeline(client, limit=3, offset=data["next_offset"])
    assert len(data2["events"]) >= 1

    first_ids = {event["id"] for event in data["events"]}
    second_ids = {event["id"] for event in data2["events"]}
    assert not first_ids & second_ids


def test_timeline_includes_narration(client):
    _create_entity(client, "task", "Narration task")

    data = _timeline(client)
    events = data["events"]
    assert len(events) >= 1
    for event in events:
        assert "narration" in event
        assert isinstance(event["narration"], str)
        assert event["narration"].strip() != ""


@pytest.mark.slow
def test_timeline_performance_1000_events(client, app):
    """A query spanning 1000 events should return in under 500ms."""

    project_id = f"project-{uuid.uuid4()}"
    base_time = datetime.now(timezone.utc) - timedelta(days=7)

    with app.app_context():
        _raw_execute(
            """
            INSERT INTO entities (id, type, title, status, lifecycle, created_at, updated_at)
            VALUES (%s, 'project', 'Perf project', 'active', 'active', now(), now())
            """,
            (project_id,),
        )

    event_values = []
    for index in range(1000):
        event_id = f"event-{index:05d}-{uuid.uuid4()}"
        occurred_at = base_time + timedelta(minutes=index)
        event_values.append((event_id, project_id, "updated", "user", occurred_at))

    with psycopg2.connect(_db_url()) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO entity_events (id, entity_id, event_type, actor, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                event_values,
            )

    start = time.perf_counter()
    data = _timeline(client, limit=50)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert len(data["events"]) == 50
    assert data["next_offset"] == 50
    assert elapsed_ms < 500, f"timeline query took {elapsed_ms:.1f}ms, expected <500ms"
