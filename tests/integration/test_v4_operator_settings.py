"""Tests for the v4 operator identity settings endpoints."""

from extensions import db
from models import AppSetting, Entity


def _create_person(client, name):
    payload = {"type": "person", "title": name, "content": f"{name} content"}
    response = client.post("/api/v4/entities", json=payload)
    assert response.status_code == 201
    return response.get_json()["data"]


def _set_owner_person_id(app, person_id):
    with app.app_context():
        setting = db.session.get(AppSetting, "owner_person_id")
        if setting is None:
            setting = AppSetting(key="owner_person_id", value=person_id)
            db.session.add(setting)
        else:
            setting.value = person_id
        db.session.commit()


def test_get_operator_unconfigured_no_owner(client):
    response = client.get("/api/v4/settings/operator")
    assert response.status_code == 200
    data = response.get_json()
    assert data["operator_person_id"] is None
    assert data["configured"] is False


def test_get_operator_backfills_from_owner_person_id(client, app):
    danish = _create_person(client, "Danish")
    _set_owner_person_id(app, danish["id"])

    response = client.get("/api/v4/settings/operator")
    assert response.status_code == 200
    data = response.get_json()
    assert data["operator_person_id"] == danish["id"]
    assert data["configured"] is False

    # Backfill is read-only: the operator setting is not persisted yet.
    with app.app_context():
        assert db.session.get(AppSetting, "operator_person_id") is None


def test_put_operator_persists_operator_person_id(client, app):
    danish = _create_person(client, "Danish")

    response = client.put(
        "/api/v4/settings/operator", json={"operator_person_id": danish["id"]}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["operator_person_id"] == danish["id"]
    assert data["configured"] is True

    with app.app_context():
        setting = db.session.get(AppSetting, "operator_person_id")
        assert setting is not None
        assert setting.value == danish["id"]

    response = client.get("/api/v4/settings/operator")
    assert response.status_code == 200
    data = response.get_json()
    assert data["operator_person_id"] == danish["id"]
    assert data["configured"] is True


def test_get_operator_prefers_persisted_operator_over_owner(client, app):
    danish = _create_person(client, "Danish")
    akash = _create_person(client, "Akash")
    _set_owner_person_id(app, danish["id"])

    response = client.put(
        "/api/v4/settings/operator", json={"operator_person_id": akash["id"]}
    )
    assert response.status_code == 200

    response = client.get("/api/v4/settings/operator")
    assert response.status_code == 200
    data = response.get_json()
    assert data["operator_person_id"] == akash["id"]
    assert data["configured"] is True

    with app.app_context():
        assert db.session.get(AppSetting, "owner_person_id") is not None


def test_put_operator_invalid_person_id(client):
    response = client.put("/api/v4/settings/operator", json={})
    assert response.status_code == 400
    assert "operator_person_id" in response.get_json()["error"].lower()


def test_put_operator_nonexistent_person_id(client):
    response = client.put(
        "/api/v4/settings/operator",
        json={"operator_person_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 400
    assert "person" in response.get_json()["error"].lower()


def test_put_operator_non_person_entity(client):
    project = client.post("/api/v4/entities", json={"type": "project", "title": "P"})
    assert project.status_code == 201
    project_id = project.get_json()["data"]["id"]

    response = client.put(
        "/api/v4/settings/operator", json={"operator_person_id": project_id}
    )
    assert response.status_code == 400
    assert "person" in response.get_json()["error"].lower()
