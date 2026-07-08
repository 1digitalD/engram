from datetime import datetime, timedelta, timezone

from extensions import db
from models import AppSetting, Entity, EntityLink


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
    return response.get_json()["data"]


def _set_operator(app, person_id):
    with app.app_context():
        setting = db.session.get(AppSetting, "operator_person_id")
        if setting is None:
            setting = AppSetting(key="operator_person_id", value=person_id)
            db.session.add(setting)
        else:
            setting.value = person_id
        db.session.commit()


def _rewind_entity(app, entity_id, *, days):
    with app.app_context():
        entity = db.session.get(Entity, entity_id)
        ts = datetime.now(timezone.utc) - timedelta(days=days)
        entity.created_at = ts
        entity.updated_at = ts
        db.session.commit()


def _set_entity_properties(app, entity_id, properties):
    with app.app_context():
        entity = db.session.get(Entity, entity_id)
        entity.properties = properties
        db.session.commit()


def _task_ids(payload):
    return {
        item["id"]
        for group in payload["data"]["groups"]
        for item in group["items"]
    }


def _group_map(payload):
    return {group["key"]: group for group in payload["data"]["groups"]}


def test_tc20_and_tc21_workboard_returns_grouped_portfolio_and_state_filters(client, app):
    operator = _create_entity(client, "person", "Operator")
    sam = _create_entity(client, "person", "Sam")
    space = _create_entity(
        client,
        "project",
        "Apollo",
        due_at=(datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
    )
    mine = _create_entity(
        client,
        "task",
        "Close contract",
        due_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    )
    waiting = _create_entity(
        client,
        "task",
        "Security questionnaire",
        due_at=(datetime.now(timezone.utc) + timedelta(days=4)).isoformat(),
    )
    blocker = _create_entity(client, "task", "External approval")

    _set_operator(app, operator["id"])
    _link(client, mine["id"], operator["id"], "assigned_to")
    _link(client, waiting["id"], sam["id"], "assigned_to")
    _link(client, mine["id"], space["id"], "parent")
    _link(client, waiting["id"], space["id"], "parent")
    _link(client, blocker["id"], waiting["id"], "blocks")
    _rewind_entity(app, mine["id"], days=11)
    _rewind_entity(app, waiting["id"], days=12)
    _rewind_entity(app, blocker["id"], days=1)
    _rewind_entity(app, space["id"], days=15)

    by_space = client.get("/api/v4/workboard", query_string={"group": "space"})
    assert by_space.status_code == 200
    by_space_payload = by_space.get_json()
    assert by_space_payload["meta"]["group"] == "space"
    assert by_space_payload["meta"]["counts"]["mine"] == 1
    assert by_space_payload["meta"]["counts"]["waiting_on"] == 1
    assert by_space_payload["meta"]["counts"]["overdue"] == 1
    assert by_space_payload["meta"]["counts"]["blocked"] == 1
    assert _task_ids(by_space_payload) == {mine["id"], waiting["id"]}

    by_person = client.get("/api/v4/workboard", query_string={"group": "person"})
    assert by_person.status_code == 200
    by_person_payload = by_person.get_json()
    assert by_person_payload["meta"]["group"] == "person"
    assert _task_ids(by_person_payload) == {mine["id"], waiting["id"]}

    overdue_only = client.get(
        "/api/v4/workboard",
        query_string={"group": "space", "state": "overdue"},
    )
    assert overdue_only.status_code == 200
    assert _task_ids(overdue_only.get_json()) == {mine["id"]}

    waiting_only = client.get(
        "/api/v4/workboard",
        query_string={"group": "space", "state": "waiting_on"},
    )
    assert waiting_only.status_code == 200
    assert _task_ids(waiting_only.get_json()) == {waiting["id"]}


def test_tc22_at_risk_flags_include_reason_and_receipts(client, app):
    operator = _create_entity(client, "person", "Operator")
    space = _create_entity(
        client,
        "project",
        "Renewal",
        due_at=(datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
    )
    task = _create_entity(
        client,
        "task",
        "Send revised deck",
        due_at=(datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
    )

    _set_operator(app, operator["id"])
    _link(client, task["id"], operator["id"], "assigned_to")
    _link(client, task["id"], space["id"], "parent")
    _rewind_entity(app, task["id"], days=12)
    _rewind_entity(app, space["id"], days=16)

    response = client.get("/api/v4/workboard", query_string={"group": "space"})
    assert response.status_code == 200
    payload = response.get_json()
    group = payload["data"]["groups"][0]
    item = group["items"][0]

    assert item["states"]["at_risk"] is True
    assert item["at_risk"]["reason"]
    assert item["at_risk"]["receipts"]
    assert group["at_risk"]["flag"] is True
    assert group["at_risk"]["reason"]
    assert group["at_risk"]["receipts"]


def test_tc23_hysteresis_clears_only_after_two_day_improvement(client, app):
    operator = _create_entity(client, "person", "Operator")
    space = _create_entity(
        client,
        "project",
        "Launch",
        due_at=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    )
    sticky = _create_entity(
        client,
        "task",
        "Sticky risk",
        due_at=(datetime.now(timezone.utc) + timedelta(days=8)).isoformat(),
        properties={"workboard": {"at_risk": True}},
    )
    cleared = _create_entity(
        client,
        "task",
        "Cleared risk",
        due_at=(datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        properties={"workboard": {"at_risk": True}},
    )

    _set_operator(app, operator["id"])
    for task in (sticky, cleared):
        _link(client, task["id"], operator["id"], "assigned_to")
        _link(client, task["id"], space["id"], "parent")
    _rewind_entity(app, sticky["id"], days=9)
    _rewind_entity(app, cleared["id"], days=7)

    response = client.get("/api/v4/workboard", query_string={"group": "space"})
    assert response.status_code == 200
    items = {
        item["id"]: item
        for group in response.get_json()["data"]["groups"]
        for item in group["items"]
    }

    assert items[sticky["id"]]["states"]["at_risk"] is True
    assert items[cleared["id"]]["states"]["at_risk"] is False


def test_tc24_space_threshold_override_changes_staleness(client, app):
    operator = _create_entity(client, "person", "Operator")
    default_space = _create_entity(client, "project", "Default space")
    custom_space = _create_entity(
        client,
        "project",
        "Custom space",
        properties={"thresholds": {"stale_days": 14}},
    )
    default_task = _create_entity(client, "task", "Default stale task")
    custom_task = _create_entity(client, "task", "Custom fresh task")

    _set_operator(app, operator["id"])
    for task, space in ((default_task, default_space), (custom_task, custom_space)):
        _link(client, task["id"], operator["id"], "assigned_to")
        _link(client, task["id"], space["id"], "parent")
        _rewind_entity(app, task["id"], days=11)

    response = client.get("/api/v4/workboard", query_string={"group": "space"})
    assert response.status_code == 200
    groups = _group_map(response.get_json())

    default_item = groups[default_space["id"]]["items"][0]
    custom_item = groups[custom_space["id"]]["items"][0]

    assert default_item["states"]["stale"] is True
    assert custom_item["states"]["stale"] is False
