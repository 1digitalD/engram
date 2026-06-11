"""Cycle 14 tests for the v4 today cockpit endpoint."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm.attributes import flag_modified

from extensions import db
from models import AiSuggestion, Entity


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


def test_v4_summary_matches_today_and_inbox_counts(client, app):
    from services.v4_attention import today_attention_count

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    _create_entity(client, "task", "Overdue task", due_at=yesterday)
    _create_entity(client, "task", "Blocked task", status="blocked")
    _create_entity(client, "note", "Needs review note")

    response = client.get("/api/v4/summary")
    assert response.status_code == 200
    summary = response.get_json()

    today_response = client.get("/api/v4/today")
    assert today_response.status_code == 200
    today_data = today_response.get_json()

    inbox_response = client.get("/api/v4/inbox", query_string={"limit": 200})
    assert inbox_response.status_code == 200
    inbox_data = inbox_response.get_json()

    assert summary["today_count"] == today_attention_count(today_data)
    assert summary["today_count"] > 0
    assert summary["inbox_count"] == len(inbox_data["needs_review"])
    assert summary["suggestions_count"] == summary["inbox_count"]
    assert summary["last_reviewed_at"] == today_data["last_reviewed_at"]
    assert summary["reviewed_today"] == today_data["reviewed_today"]


def test_v4_today_returns_execution_sections(client, app):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    today = datetime.now(timezone.utc).isoformat()
    overdue_followup_task = _create_entity(client, "task", "Overdue follow-up", follow_up_at=yesterday)
    today_followup_task = _create_entity(client, "task", "Today follow-up", follow_up_at=today)
    upcoming_followup_task = _create_entity(
        client, "task", "Upcoming follow-up",
        follow_up_at=(datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
    )
    overdue_due_task = _create_entity(client, "task", "Overdue by due", due_at=yesterday)
    due_today_task = _create_entity(client, "task", "Due today", due_at=today)
    done_with_followup = _create_entity(client, "task", "Done w/ followup", follow_up_at=yesterday, status="done")
    waiting_task = _create_entity(client, "task", "Waiting task", status="waiting")
    blocked_task = _create_entity(client, "task", "Blocked task", status="blocked")
    project_without_tasks = _create_entity(client, "project", "Needs next task")
    project_with_task = _create_entity(client, "project", "Has task")
    open_task = _create_entity(client, "task", "Open project task")
    recent_note = _create_entity(client, "note", "Recent note")
    _link(client, open_task["id"], project_with_task["id"], "parent")

    with app.app_context():
        note = db.session.get(Entity, recent_note["id"])
        suggestion = AiSuggestion(
            source_entity_id=note.id,
            suggestion_type="create_task",
            operation_type="create_entity",
            payload={"title": "Suggested task", "type": "task", "source_entity_id": note.id},
            status="pending",
        )
        db.session.add(suggestion)
        db.session.commit()

    response = client.get("/api/v4/today")

    assert response.status_code == 200
    data = response.get_json()
    assert {item["id"] for item in data["overdue_follow_ups"]} == {overdue_followup_task["id"]}
    assert {item["id"] for item in data["follow_ups"]} == {today_followup_task["id"]}
    assert {item["id"] for item in data["upcoming_follow_ups"]} == {upcoming_followup_task["id"]}
    # done_with_followup should NOT appear in either follow-up bucket (status filter).
    assert done_with_followup["id"] not in {i["id"] for i in data["overdue_follow_ups"]}
    assert done_with_followup["id"] not in {i["id"] for i in data["follow_ups"]}
    assert {item["id"] for item in data["overdue"]} == {overdue_due_task["id"]}
    assert {item["id"] for item in data["due_today"]} == {due_today_task["id"]}
    assert {item["id"] for item in data["blocked_tasks"]} == {blocked_task["id"]}
    assert {item["id"] for item in data["waiting_tasks"]} == {waiting_task["id"]}
    blocked_attention = data["blocked_tasks"][0]["attention"]
    assert blocked_attention["level"] in {"medium", "high", "urgent"}
    assert any(reason["key"] == "status:blocked" for reason in blocked_attention["reasons"])
    assert {item["id"] for item in data["blocked_or_waiting_tasks"]} == {waiting_task["id"], blocked_task["id"]}
    assert [item["id"] for item in data["projects_without_open_tasks"]] == [project_without_tasks["id"]]
    assert data["projects_without_open_tasks"][0]["attention"]["reasons"][0]["key"] == "context:project_without_open_tasks"
    assert [item["id"] for item in data["recent_notes"]] == [recent_note["id"]]
    assert data["pending_suggestions"][0]["payload"]["title"] == "Suggested task"


def test_v4_today_task_inherits_project_priority(client, app):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    project = _create_entity(client, "project", "Launch readiness", properties={"priority": "urgent"})
    task_no_priority = _create_entity(client, "task", "Overdue without own priority", due_at=yesterday)
    task_own_priority = _create_entity(
        client, "task", "Overdue with own priority", due_at=yesterday, properties={"priority": "low"},
    )
    _link(client, task_no_priority["id"], project["id"], "parent")
    _link(client, task_own_priority["id"], project["id"], "parent")

    response = client.get("/api/v4/today")
    assert response.status_code == 200
    data = response.get_json()

    by_id = {item["id"]: item for item in data["overdue"]}

    inherited = by_id[task_no_priority["id"]]
    assert inherited["inherited_priority"] == "urgent"
    assert any(
        reason["key"] == "priority:urgent" and "from project" in reason["label"]
        for reason in inherited["attention"]["reasons"]
    )

    own = by_id[task_own_priority["id"]]
    assert "inherited_priority" not in own
    assert any(
        reason["key"] == "priority:low" and "from project" not in reason["label"]
        for reason in own["attention"]["reasons"]
    )


def test_v4_today_surfaces_unscheduled_tasks_by_impact_and_staleness(client, app):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    # Dated, low-priority overdue task.
    _create_entity(client, "task", "Routine overdue task", due_at=yesterday, properties={"priority": "low"})

    # Undated, high-priority task that's gone stale — should outrank the
    # dated low-priority task and appear in `unscheduled_attention_tasks`.
    stale_task = _create_entity(client, "task", "Stale high-priority task", properties={"priority": "high"})

    # Undated task with no priority, but blocks another active task — should
    # also surface via impact.
    blocker_task = _create_entity(client, "task", "Blocker task")
    blocked_task = _create_entity(client, "task", "Some other open task")
    _link(client, blocker_task["id"], blocked_task["id"], "blocks")

    # An undated, low-attention task with neither priority/staleness/impact —
    # should not surface.
    _create_entity(client, "task", "Quiet undated task")

    with app.app_context():
        from sqlalchemy import update
        db.session.execute(
            update(Entity)
            .where(Entity.id == stale_task["id"])
            .values(created_at=datetime.now(timezone.utc) - timedelta(days=21))
        )
        db.session.commit()

    response = client.get("/api/v4/today")
    assert response.status_code == 200
    data = response.get_json()

    by_id = {item["id"]: item for item in data["unscheduled_attention_tasks"]}
    assert stale_task["id"] in by_id
    assert blocker_task["id"] in by_id
    assert "Quiet undated task" not in {item["title"] for item in data["unscheduled_attention_tasks"]}

    stale_item = by_id[stale_task["id"]]
    assert any(r["key"] == "staleness" for r in stale_item["attention"]["reasons"])

    blocker_item = by_id[blocker_task["id"]]
    assert any(r["key"] == "impact:blocks" for r in blocker_item["attention"]["reasons"])


def test_v4_today_includes_upcoming_due_tasks(client, app):
    in_three_days = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    in_three_weeks = (datetime.now(timezone.utc) + timedelta(days=21)).isoformat()

    upcoming_due_task = _create_entity(client, "task", "Upcoming due task", due_at=in_three_days)
    far_future_task = _create_entity(client, "task", "Far future due task", due_at=in_three_weeks)

    response = client.get("/api/v4/today")
    assert response.status_code == 200
    data = response.get_json()

    upcoming_ids = {item["id"] for item in data["upcoming_due_tasks"]}
    assert upcoming_due_task["id"] in upcoming_ids
    assert far_future_task["id"] not in upcoming_ids
    # Tasks due later this week shouldn't also clutter overdue/due_today.
    assert upcoming_due_task["id"] not in {item["id"] for item in data["overdue"]}
    assert upcoming_due_task["id"] not in {item["id"] for item in data["due_today"]}


def test_v4_today_day_reviewed_flow(client, app):
    response = client.get("/api/v4/today")
    assert response.status_code == 200
    data = response.get_json()
    assert data["last_reviewed_at"] is None
    assert data["reviewed_today"] is False

    response = client.post("/api/v4/today/review")
    assert response.status_code == 200
    reviewed = response.get_json()
    assert reviewed["last_reviewed_at"] is not None
    assert reviewed["reviewed_today"] is True

    response = client.get("/api/v4/today")
    assert response.status_code == 200
    data = response.get_json()
    assert data["last_reviewed_at"] == reviewed["last_reviewed_at"]
    assert data["reviewed_today"] is True

    # Simulate a review from a previous day: still recorded, but no longer "today".
    with app.app_context():
        from models import AppSetting
        setting = db.session.get(AppSetting, "last_reviewed_at")
        setting.value = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        flag_modified(setting, "value")
        db.session.commit()

    response = client.get("/api/v4/today")
    assert response.status_code == 200
    data = response.get_json()
    assert data["last_reviewed_at"] is not None
    assert data["reviewed_today"] is False


def test_v4_today_surfaces_quiet_delegations(client, app):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    far_past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()

    akash = _create_entity(client, "person", "Akash")
    quiet_task = _create_entity(client, "task", "Design GTM trigger doc", follow_up_at=far_past)
    fresh_task = _create_entity(client, "task", "Write status update", follow_up_at=yesterday)
    not_due_task = _create_entity(
        client, "task", "Plan roadmap",
        follow_up_at=(datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
    )

    _link(client, quiet_task["id"], akash["id"], "assigned_to")
    _link(client, fresh_task["id"], akash["id"], "assigned_to")
    _link(client, not_due_task["id"], akash["id"], "assigned_to")

    response = client.post(
        f"/api/v4/entities/{fresh_task['id']}/activity_updates",
        json={"content": "Akash shared a draft today"},
    )
    assert response.status_code == 201

    response = client.get("/api/v4/today")
    assert response.status_code == 200
    data = response.get_json()

    quiet_ids = {item["id"] for item in data["delegations_quiet"]}
    assert quiet_task["id"] in quiet_ids
    assert fresh_task["id"] not in quiet_ids
    assert not_due_task["id"] not in quiet_ids

    quiet_item = next(item for item in data["delegations_quiet"] if item["id"] == quiet_task["id"])
    assert quiet_item["days_silent"] >= 9
    assert quiet_item["last_update"] is None


def test_v4_today_does_not_surface_delegations_to_owner(client, app):
    far_past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    dan = _create_entity(client, "person", "Dan")
    owner_task = _create_entity(client, "task", "Owner's own task", follow_up_at=far_past)
    _link(client, owner_task["id"], dan["id"], "assigned_to")

    response = client.get("/api/v4/today")
    assert response.status_code == 200
    data = response.get_json()
    assert owner_task["id"] not in {item["id"] for item in data["delegations_quiet"]}


def test_v4_today_surfaces_stale_and_archival_projects(client, app):
    fresh_project = _create_entity(client, "project", "Fresh project")
    stale_project = _create_entity(client, "project", "Stale project")
    archival_project = _create_entity(client, "project", "Ancient project")
    done_project = _create_entity(client, "project", "Done long ago", status="completed")

    with app.app_context():
        from sqlalchemy import update
        db.session.execute(
            update(Entity)
            .where(Entity.id == stale_project["id"])
            .values(created_at=datetime.now(timezone.utc) - timedelta(days=15))
        )
        db.session.execute(
            update(Entity)
            .where(Entity.id == archival_project["id"])
            .values(created_at=datetime.now(timezone.utc) - timedelta(days=31))
        )
        db.session.execute(
            update(Entity)
            .where(Entity.id == done_project["id"])
            .values(created_at=datetime.now(timezone.utc) - timedelta(days=60))
        )
        db.session.commit()
        db.session.expire_all()

    response = client.get("/api/v4/today")
    assert response.status_code == 200
    data = response.get_json()

    stale_ids = {item["id"] for item in data["stale_projects"]}
    archival_ids = {item["id"] for item in data["suggested_archival"]}

    assert stale_project["id"] in stale_ids
    assert archival_project["id"] not in stale_ids
    assert fresh_project["id"] not in stale_ids

    assert archival_project["id"] in archival_ids
    assert stale_project["id"] not in archival_ids
    assert done_project["id"] not in archival_ids
    assert fresh_project["id"] not in archival_ids

    stale_item = next(item for item in data["stale_projects"] if item["id"] == stale_project["id"])
    assert stale_item["stale_days"] >= 14

    archival_item = next(item for item in data["suggested_archival"] if item["id"] == archival_project["id"])
    assert archival_item["stale_days"] >= 30

    summary_response = client.get("/api/v4/summary")
    assert summary_response.status_code == 200
    summary = summary_response.get_json()
    assert summary["stale_projects_count"] == len(stale_ids) + len(archival_ids)


def test_v4_today_surfaces_new_since_yesterday_count(client, app):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    new_task = _create_entity(client, "task", "Newly overdue task", due_at=yesterday)
    old_task = _create_entity(client, "task", "Old overdue task", due_at=yesterday)

    with app.app_context():
        from sqlalchemy import update
        db.session.execute(
            update(Entity)
            .where(Entity.id == old_task["id"])
            .values(created_at=datetime.now(timezone.utc) - timedelta(days=3))
        )
        db.session.commit()
        db.session.expire_all()

    response = client.get("/api/v4/today")
    assert response.status_code == 200
    data = response.get_json()
    assert data["new_since_yesterday_count"] == 1

    overdue_ids = {item["id"] for item in data["overdue"]}
    assert new_task["id"] in overdue_ids
    assert old_task["id"] in overdue_ids

    summary_response = client.get("/api/v4/summary")
    assert summary_response.status_code == 200
    summary = summary_response.get_json()
    assert summary["new_since_yesterday_count"] == 1

    # After marking the day reviewed, only items created since the review count.
    review_response = client.post("/api/v4/today/review")
    assert review_response.status_code == 200

    response = client.get("/api/v4/today")
    assert response.status_code == 200
    data = response.get_json()
    assert data["new_since_yesterday_count"] == 0

    newer_task = _create_entity(client, "task", "Even newer overdue task", due_at=yesterday)

    response = client.get("/api/v4/today")
    assert response.status_code == 200
    data = response.get_json()
    assert data["new_since_yesterday_count"] == 1
    new_ids = {item["id"] for item in data["overdue"] if item["id"] == newer_task["id"]}
    assert newer_task["id"] in new_ids


def test_v4_person_detail_includes_current_load_with_last_heard(client, app):
    akash = _create_entity(client, "person", "Akash")
    open_task = _create_entity(client, "task", "Design GTM trigger doc", status="open")
    done_task = _create_entity(client, "task", "Already shipped", status="done")

    _link(client, open_task["id"], akash["id"], "assigned_to")
    _link(client, done_task["id"], akash["id"], "assigned_to")

    response = client.post(
        f"/api/v4/entities/{open_task['id']}/activity_updates",
        json={"content": "Akash shared the first draft"},
    )
    assert response.status_code == 201

    response = client.get(f"/api/v4/entities/{akash['id']}/detail")
    assert response.status_code == 200
    data = response.get_json()

    load_ids = {item["task"]["id"] for item in data["current_load"]}
    assert open_task["id"] in load_ids
    assert done_task["id"] not in load_ids

    open_item = next(item for item in data["current_load"] if item["task"]["id"] == open_task["id"])
    assert open_item["last_heard_at"] is not None
    assert "first draft" in open_item["last_heard_preview"]


def test_v4_inbox_separates_needs_review_from_recent(client, app):
    needs_pending = _create_entity(client, "note", "Needs review (pending)")
    processed = _create_entity(client, "note", "Already processed")
    with_suggestion = _create_entity(client, "note", "Has open suggestion")

    with app.app_context():
        note = db.session.get(Entity, processed["id"])
        note.ai_status = "done"
        db.session.add(AiSuggestion(
            source_entity_id=with_suggestion["id"],
            suggestion_type="create_task",
            operation_type="create_entity",
            payload={"title": "Suggested task"},
            status="pending",
        ))
        db.session.commit()

    response = client.get("/api/v4/inbox")
    assert response.status_code == 200
    data = response.get_json()

    needs_ids = {n["id"] for n in data["needs_review"]}
    recent_ids = {n["id"] for n in data["recent"]}

    assert needs_pending["id"] in needs_ids  # ai_status defaults to "pending"
    assert with_suggestion["id"] in needs_ids  # has pending AiSuggestion
    assert processed["id"] in recent_ids
    assert processed["id"] not in needs_ids

    # pending_suggestion_count annotation
    by_id = {n["id"]: n for n in data["needs_review"] + data["recent"]}
    assert by_id[with_suggestion["id"]]["pending_suggestion_count"] == 1
    assert by_id[with_suggestion["id"]]["attention"]["score"] > 0
    assert any(
        reason["key"] == "pending_suggestions"
        for reason in by_id[with_suggestion["id"]]["attention"]["reasons"]
    )
    assert by_id[processed["id"]]["pending_suggestion_count"] == 0
    assert "intent" in by_id[processed["id"]]["ai"]


def test_v4_inbox_prioritizes_review_and_recent_notes_by_intent(client, app):
    blocker = _create_entity(client, "note", "Blocked note")
    junk = _create_entity(client, "note", "Junk note")
    with_suggestion = _create_entity(client, "note", "Suggested note")
    reference = _create_entity(client, "note", "Reference note")
    generic = _create_entity(client, "note", "Generic note")

    with app.app_context():
        blocker_note = db.session.get(Entity, blocker["id"])
        blocker_note.ai_status = "pending"
        blocker_note.ai_meta = {"intent": "blocker", "intent_confidence": 0.8}

        junk_note = db.session.get(Entity, junk["id"])
        junk_note.ai_status = "pending"
        junk_note.ai_meta = {"intent": "junk", "intent_confidence": 0.7}

        suggested_note = db.session.get(Entity, with_suggestion["id"])
        suggested_note.ai_status = "done"
        suggested_note.ai_meta = {"intent": "delegation", "intent_confidence": 0.82}

        reference_note = db.session.get(Entity, reference["id"])
        reference_note.ai_status = "done"
        reference_note.ai_meta = {"intent": "reference", "intent_confidence": 0.75}

        generic_note = db.session.get(Entity, generic["id"])
        generic_note.ai_status = "done"
        generic_note.ai_meta = {"intent": "note", "intent_confidence": 0.6}

        db.session.add(AiSuggestion(
            source_entity_id=with_suggestion["id"],
            suggestion_type="create_task",
            operation_type="create_entity",
            payload={"title": "Delegated task"},
            status="pending",
        ))
        db.session.commit()

    response = client.get("/api/v4/inbox")

    assert response.status_code == 200
    data = response.get_json()
    assert [item["id"] for item in data["needs_review"]] == [
        with_suggestion["id"],
        blocker["id"],
        junk["id"],
    ]
    assert [item["id"] for item in data["recent"]] == [
        reference["id"],
        generic["id"],
    ]
