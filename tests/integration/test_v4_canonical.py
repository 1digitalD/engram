"""Cycle 4 tests for v4 canonical markdown generation."""


def _create_entity(client, entity_type, title, **extra):
    payload = {"type": entity_type, "title": title}
    payload.update(extra)
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


def test_canonical_markdown_includes_entity_fields(client):
    task = _create_entity(
        client,
        "task",
        "Follow up with Henry",
        content="Ask for rollout stages.",
        status="open",
        follow_up_at="2026-05-20T10:00:00+00:00",
        source="manual",
        properties={"priority": "high"},
        tags=["memory", "rollout"],
    )

    response = client.get(f"/api/v4/entities/{task['id']}/canonical")

    assert response.status_code == 200
    markdown = response.get_json()["canonical"]
    assert "# Follow up with Henry" in markdown
    assert "Type: task" in markdown
    assert "Status: open" in markdown
    assert "Lifecycle: active" in markdown
    assert "Follow-up: 2026-05-20T10:00:00+00:00" in markdown
    assert "Priority: high" in markdown
    assert "## Content\nAsk for rollout stages." in markdown
    assert "## Tags\nmemory, rollout" in markdown
    assert "Source: manual" in markdown
    assert "Created:" in markdown
    assert "Updated:" in markdown


def test_canonical_markdown_includes_relationship_titles(client):
    task = _create_entity(client, "task", "Follow up with Henry")
    project = _create_entity(client, "project", "Memory Lookup Service")
    person = _create_entity(client, "person", "Henry Lucco")
    note = _create_entity(client, "note", "Talked to Henry about rollout")
    _link(client, task["id"], project["id"], "parent")
    _link(client, task["id"], person["id"], "assigned_to")
    _link(client, task["id"], note["id"], "derived_from")

    response = client.get(f"/api/v4/entities/{task['id']}/canonical")

    assert response.status_code == 200
    markdown = response.get_json()["canonical"]
    assert "- parent project: Memory Lookup Service" in markdown
    assert "- assigned_to person: Henry Lucco" in markdown
    assert "- derived_from note: Talked to Henry about rollout" in markdown


def test_canonical_markdown_is_generated_on_demand_not_persisted(client, app):
    note = _create_entity(client, "note", "Source note", content="Original")

    first = client.get(f"/api/v4/entities/{note['id']}/canonical").get_json()["canonical"]
    client.patch(f"/api/v4/entities/{note['id']}", json={"content": "Updated"})
    second = client.get(f"/api/v4/entities/{note['id']}/canonical").get_json()["canonical"]

    assert "Original" in first
    assert "Updated" in second
