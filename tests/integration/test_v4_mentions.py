"""Tests for the inline @/[[ mention picker: search endpoint and explicit
mention links created from captured content."""

from models import Entity, EntityLink


def _create_entity(client, entity_type, title):
    response = client.post("/api/v4/entities", json={"type": entity_type, "title": title})
    assert response.status_code == 201
    return response.get_json()["data"]


def test_mentions_search_groups_by_type(client):
    _create_entity(client, "person", "Akash Mehta")
    _create_entity(client, "task", "Akash review")
    _create_entity(client, "project", "Akash Migration")

    response = client.get("/api/v4/entities/mentions", query_string={"q": "Akash"})
    assert response.status_code == 200
    data = response.get_json()
    assert set(data["results"].keys()) == {"person", "task", "project"}
    assert data["results"]["person"][0]["title"] == "Akash Mehta"
    assert data["results"]["person"][0]["path"] == f"/people/{data['results']['person'][0]['id']}"


def test_mentions_search_empty_query_returns_recent(client):
    _create_entity(client, "task", "Recent task")

    response = client.get("/api/v4/entities/mentions")
    assert response.status_code == 200
    data = response.get_json()
    assert "task" in data["results"]


def test_mentions_search_respects_types_filter(client):
    _create_entity(client, "person", "Filtered Person")
    _create_entity(client, "task", "Filtered Task")

    response = client.get("/api/v4/entities/mentions", query_string={"q": "Filtered", "types": "person"})
    data = response.get_json()
    assert set(data["results"].keys()) == {"person"}


def test_capture_creates_mentions_link_for_explicit_picker_reference(client, app):
    project = _create_entity(client, "project", "Agent Platform")

    response = client.post(
        "/api/v4/capture",
        json={"content": f"Following up on [Agent Platform](/projects/{project['id']}) before Friday."},
    )
    assert response.status_code == 201
    data = response.get_json()
    note_id = data["source_note"]["id"]
    assert any(
        c["type"] == "relationship_added" and c["target_entity_id"] == project["id"]
        for c in data["applied_changes"]
    )

    with app.app_context():
        link = EntityLink.query.filter_by(
            source_entity_id=note_id,
            target_entity_id=project["id"],
            relationship_type="mentions",
        ).first()
        assert link is not None
        assert link.source == "user"
        assert link.confidence == 1.0


def test_activity_update_creates_mentions_link_for_explicit_picker_reference(client, app):
    task = _create_entity(client, "task", "Ship the feature")
    person = _create_entity(client, "person", "Priya")

    response = client.post(
        f"/api/v4/entities/{task['id']}/activity_updates",
        json={"content": f"Synced with [Priya]({'/people/' + person['id']}) on this."},
    )
    assert response.status_code == 201
    data = response.get_json()
    note_id = data["data"]["id"]

    with app.app_context():
        link = EntityLink.query.filter_by(
            source_entity_id=note_id,
            target_entity_id=person["id"],
            relationship_type="mentions",
        ).first()
        assert link is not None


def test_capture_ignores_mention_to_unknown_id(client):
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.post(
        "/api/v4/capture",
        json={"content": f"See [Ghost](/tasks/{fake_id}) for details."},
    )
    assert response.status_code == 201
    data = response.get_json()
    assert not any(c["type"] == "relationship_added" for c in data["applied_changes"])
