"""Integration tests for v4 distillation reports (TC-10..13, TC-17)."""

import uuid
from pathlib import Path
from unittest.mock import patch

from extensions import db
from models import AiSuggestion, DistillationReport, Entity, Job
from services.job_worker import get_handler, process_job


def test_migration_006_applies_cleanly(app):
    """TC-10 pre-req: migration script is idempotent and creates the expected objects."""
    migration_path = Path(__file__).resolve().parents[2] / "scripts" / "migrations" / "006_distillation_reports.sql"
    assert migration_path.exists()

    with app.app_context():
        db.session.execute(db.text(migration_path.read_text()))
        db.session.commit()

        has_table = db.session.execute(
            db.text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'distillation_reports')"
            )
        ).scalar()
        assert has_table is True

        has_column = db.session.execute(
            db.text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'ai_suggestions' AND column_name = 'report_id')"
            )
        ).scalar()
        assert has_column is True


def test_pipeline_groups_candidates_into_one_report(client, app, mock_embed):
    """TC-10/TC-11/TC-12/TC-13 end-to-end: one capture → one report with stable sections."""
    project = client.post(
        "/api/v4/entities", json={"type": "project", "title": "Rollout"}
    ).get_json()["data"]
    person = client.post(
        "/api/v4/entities", json={"type": "person", "title": "Henry"}
    ).get_json()["data"]

    content = f"Sync notes — rollout and Henry. Write docs. Follow up later. {uuid.uuid4()}"
    extraction = {
        "title": "Sync notes",
        "summary": "Rollout sync",
        "intent": "task_signal",
        "intent_confidence": 0.9,
        "tags": [{"name": "meeting", "confidence": 0.9}],
        "links": [
            {
                "target_type": "project",
                "title": "Rollout",
                "relationship_type": "related",
                "confidence": 0.9,
                "evidence": "rollout",
            },
            {
                "target_type": "person",
                "title": "Henry",
                "relationship_type": "mentions",
                "confidence": 0.6,
                "evidence": "Henry",
            },
        ],
        "entities": [
            {
                "type": "task",
                "title": "Write docs",
                "assigned_to": "Danish",
                "confidence": 0.91,
                "evidence": "Write docs",
            },
            {
                "type": "task",
                "title": "Follow up later",
                "confidence": 0.85,
                "evidence": "Follow up later",
            },
        ],
    }
    decisions = [
        {
            "action": "link",
            "target_id": project["id"],
            "relationship_type": "related",
            "confidence": 0.9,
            "reason": "existing project",
        },
        {
            "action": "link",
            "target_id": person["id"],
            "relationship_type": "mentions",
            "confidence": 0.6,
            "reason": "person mention",
        },
        {
            "action": "new",
            "relationship_type": "derived_from",
            "confidence": 0.91,
            "reason": "concrete task",
        },
        {
            "action": "new",
            "relationship_type": "derived_from",
            "confidence": 0.85,
            "reason": "needs owner",
        },
    ]

    with patch("services.v4_extraction.extract_capture_candidates", return_value=extraction), patch(
        "services.v4_reconciliation.reconcile_candidates", return_value=decisions
    ):
        response = client.post("/api/v4/capture", json={"content": content, "mode": "auto"})

    assert response.status_code == 201
    data = response.get_json()
    note_id = data["source_note"]["id"]

    with app.app_context():
        job = Job.query.filter_by(job_type="assemble_report", entity_id=note_id).one()
        assert get_handler("assemble_report") is not None
        process_job(job)
        assert job.status == "done"

        report = DistillationReport.query.filter_by(source_note_id=note_id).one()
        assert report.status == "pending"

        pending = AiSuggestion.query.filter_by(source_entity_id=note_id, status="pending").all()
        assert len(pending) == 3  # two tasks + one person link suggestion
        assert all(s.report_id == report.id for s in pending)

        narrative = report.narrative
        section_names = [s["name"] for s in narrative["sections"]]
        assert section_names == [
            "routing_summary",
            "applied_annotations",
            "proposed_commitments",
            "decisions",
            "questions",
            "leftovers",
        ]

        assert len(narrative["sections"][0]["items"]) == 1
        assert any(i["kind"] == "tag_added" for i in narrative["sections"][1]["items"])
        assert any(i["kind"] == "relationship_added" for i in narrative["sections"][1]["items"])

        commitments = narrative["sections"][2]["items"]
        assert len(commitments) == 1
        assert commitments[0]["title"] == "Write docs"

        questions = narrative["sections"][4]["items"]
        assert len(questions) == 1
        assert questions[0]["kind"] == "attribution"
        assert questions[0]["owner"] is None

        leftovers = narrative["sections"][5]["items"]
        assert len(leftovers) == 1
        assert leftovers[0]["operation_type"] == "link_existing"

        stats = report.stats
        assert stats["total"] == 3
        assert stats["proposed"] == 1
        assert stats["questions"] == 1
        assert stats["leftovers"] == 1


def test_migration_007_applies_cleanly(app):
    """TC-14 pre-req: change_batch_events migration is idempotent."""
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "migrations"
        / "007_change_batch_events.sql"
    )
    assert migration_path.exists()

    with app.app_context():
        db.session.execute(db.text(migration_path.read_text()))
        db.session.commit()

        has_column = db.session.execute(
            db.text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'entity_events' AND column_name = 'change_batch_id')"
            )
        ).scalar()
        assert has_column is True


def test_list_and_get_reports(client, app):
    """GET /reports lists pending reports; GET /reports/<id> returns narrative + suggestions."""
    note_id = _create_note(app)
    _create_suggestion(
        app,
        note_id,
        "create_task",
        {"type": "task", "title": "Listed task", "source_entity_id": note_id, "evidence": "list"},
    )
    report_id = _assemble_report_for_note(app, note_id)

    list_response = client.get("/api/v4/reports?status=pending")
    assert list_response.status_code == 200
    payload = list_response.get_json()
    assert payload["meta"]["total"] >= 1
    assert any(row["id"] == report_id for row in payload["data"])

    get_response = client.get(f"/api/v4/reports/{report_id}")
    assert get_response.status_code == 200
    payload = get_response.get_json()
    assert payload["data"]["id"] == report_id
    assert "sections" in payload["data"]["narrative"]
    assert len(payload["suggestions"]) == 1


def test_resolve_report_creates_one_change_batch_and_applies_decisions(client, app):
    """TC-14: mixed accept/dismiss + accept_rest applies atomically as one ChangeBatch."""
    note_id = _create_note(app)
    s_accept = _create_suggestion(
        app,
        note_id,
        "create_task",
        {"type": "task", "title": "Accepted task", "source_entity_id": note_id, "evidence": "accepted"},
    )
    s_edit = _create_suggestion(
        app,
        note_id,
        "create_task",
        {"type": "task", "title": "Editable task", "source_entity_id": note_id, "evidence": "edit"},
    )
    s_dismiss = _create_suggestion(
        app,
        note_id,
        "create_task",
        {"type": "task", "title": "Dismissed task", "source_entity_id": note_id, "evidence": "dismiss"},
    )
    s_rest = _create_suggestion(
        app,
        note_id,
        "create_task",
        {"type": "task", "title": "Rest task", "source_entity_id": note_id, "evidence": "rest"},
    )

    report_id = _assemble_report_for_note(app, note_id)

    response = client.post(
        f"/api/v4/reports/{report_id}/resolve",
        json={
            "decisions": [
                {"suggestion_id": s_accept, "action": "accept"},
                {"suggestion_id": s_edit, "action": "edit", "edits": {"title": "Edited task"}},
                {"suggestion_id": s_dismiss, "action": "dismiss", "dismissal_reason": "not a task"},
            ],
            "accept_rest": True,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data"]["status"] == "reviewed"
    batch_id = payload["change_batch"]["id"]

    with app.app_context():
        from models import ChangeBatch, Entity, EntityEvent

        batch = db.session.get(ChangeBatch, batch_id)
        assert batch is not None
        assert batch.source_note_id == note_id

        batch_events = EntityEvent.query.filter_by(change_batch_id=batch_id).all()
        batch_event_types = {e.event_type for e in batch_events}
        assert "created" in batch_event_types
        assert "relationship_added" in batch_event_types
        assert "suggestion_accepted" in batch_event_types
        assert "suggestion_dismissed" in batch_event_types

        assert db.session.get(AiSuggestion, s_accept).status == "accepted"
        assert db.session.get(AiSuggestion, s_edit).status == "accepted"
        assert db.session.get(AiSuggestion, s_dismiss).status == "dismissed"
        assert db.session.get(AiSuggestion, s_rest).status == "accepted"

        created = Entity.query.filter(Entity.type == "task", Entity.lifecycle == "active").all()
        assert len(created) == 3
        titles = {e.title for e in created}
        assert titles == {"Accepted task", "Edited task", "Rest task"}


def test_resolve_report_rolls_back_on_failure(client, app):
    """TC-14: mid-apply failure rolls back the whole review atomically."""
    note_id = _create_note(app)
    s1 = _create_suggestion(
        app,
        note_id,
        "create_task",
        {"type": "task", "title": "First task", "source_entity_id": note_id, "evidence": "first"},
    )
    s2 = _create_suggestion(
        app,
        note_id,
        "create_task",
        {"type": "task", "title": "Second task", "source_entity_id": note_id, "evidence": "second"},
    )
    report_id = _assemble_report_for_note(app, note_id)

    with patch("api.v4.reports._resolve_create", side_effect=ValueError("injected failure")):
        response = client.post(
            f"/api/v4/reports/{report_id}/resolve",
            json={"decisions": [{"suggestion_id": s1, "action": "accept"}], "accept_rest": True},
        )

    assert response.status_code == 500
    with app.app_context():
        from models import ChangeBatch, Entity

        assert ChangeBatch.query.filter_by(source_note_id=note_id).count() == 0
        assert Entity.query.filter_by(type="task").count() == 0
        assert db.session.get(AiSuggestion, s1).status == "pending"
        assert db.session.get(AiSuggestion, s2).status == "pending"


def test_undo_report_review_reverts_applied_and_retains_dismissals(client, app):
    """TC-15: undo ChangeBatch reverts review; dismissals retained."""
    note_id = _create_note(app)
    s_accept = _create_suggestion(
        app,
        note_id,
        "create_task",
        {"type": "task", "title": "Will revert", "source_entity_id": note_id, "evidence": "revert"},
    )
    s_dismiss = _create_suggestion(
        app,
        note_id,
        "create_task",
        {"type": "task", "title": "Stay dismissed", "source_entity_id": note_id, "evidence": "dismiss"},
    )
    report_id = _assemble_report_for_note(app, note_id)

    resolve_response = client.post(
        f"/api/v4/reports/{report_id}/resolve",
        json={
            "decisions": [
                {"suggestion_id": s_accept, "action": "accept"},
                {"suggestion_id": s_dismiss, "action": "dismiss", "dismissal_reason": "not a task"},
            ]
        },
    )
    assert resolve_response.status_code == 200
    batch_id = resolve_response.get_json()["change_batch"]["id"]

    with app.app_context():
        from models import ChangeBatch, Entity

        entity = Entity.query.filter_by(type="task", title="Will revert").one()
        assert entity.lifecycle == "active"
        assert db.session.get(ChangeBatch, batch_id).undone_at is None

    undo_response = client.post(f"/api/v4/reports/{report_id}/undo")
    assert undo_response.status_code == 200
    payload = undo_response.get_json()
    assert payload["data"]["status"] == "pending"

    with app.app_context():
        from models import ChangeBatch, Entity, EntityEvent

        entity = Entity.query.filter_by(type="task", title="Will revert").one()
        assert entity.lifecycle == "deleted"

        assert db.session.get(AiSuggestion, s_accept).status == "pending"
        assert db.session.get(AiSuggestion, s_dismiss).status == "dismissed"

        batch = db.session.get(ChangeBatch, batch_id)
        assert batch.undone_at is not None

        reverted_count = EntityEvent.query.filter(
            EntityEvent.change_batch_id == batch_id,
            EntityEvent.event_type == "reverted",
        ).count()
        assert reverted_count > 0


def test_resolve_report_with_later_leaves_partial(client, app):
    """TC-16: later leaves partial report; remaining items resolvable later."""
    note_id = _create_note(app)
    s_now = _create_suggestion(
        app,
        note_id,
        "create_task",
        {"type": "task", "title": "Do now", "source_entity_id": note_id, "evidence": "now"},
    )
    s_later = _create_suggestion(
        app,
        note_id,
        "create_task",
        {"type": "task", "title": "Do later", "source_entity_id": note_id, "evidence": "later"},
    )
    report_id = _assemble_report_for_note(app, note_id)

    partial_response = client.post(
        f"/api/v4/reports/{report_id}/resolve",
        json={
            "decisions": [
                {"suggestion_id": s_now, "action": "accept"},
                {"suggestion_id": s_later, "action": "later"},
            ]
        },
    )
    assert partial_response.status_code == 200
    assert partial_response.get_json()["data"]["status"] == "partial"

    with app.app_context():
        assert db.session.get(AiSuggestion, s_now).status == "accepted"
        assert db.session.get(AiSuggestion, s_later).status == "pending"

    final_response = client.post(
        f"/api/v4/reports/{report_id}/resolve",
        json={"decisions": [{"suggestion_id": s_later, "action": "accept"}]},
    )
    assert final_response.status_code == 200
    assert final_response.get_json()["data"]["status"] == "reviewed"

    with app.app_context():
        assert db.session.get(AiSuggestion, s_later).status == "accepted"


def test_accepting_older_report_does_not_resurrect_stale_values(client, app):
    """EC-07: reports for the same Space are independent; apply checks current state."""
    project = client.post(
        "/api/v4/entities", json={"type": "project", "title": "Rollout"}
    ).get_json()["data"]
    task = client.post(
        "/api/v4/entities",
        json={"type": "task", "title": "Track rollout", "status": "open"},
    ).get_json()["data"]
    client.post(
        "/api/v4/entities/links",
        json={
            "source_id": task["id"],
            "target_id": project["id"],
            "relationship_type": "parent",
        },
    )

    note1_id = _create_note(app, title="First capture")
    note2_id = _create_note(app, title="Second capture")

    s1 = _create_suggestion(
        app,
        note1_id,
        "update_task",
        {
            "target_entity_id": task["id"],
            "target_type": "task",
            "fields": {"status": "done"},
            "evidence": "first capture says done",
        },
        operation_type="update_entity",
    )
    s2 = _create_suggestion(
        app,
        note2_id,
        "update_task",
        {
            "target_entity_id": task["id"],
            "target_type": "task",
            "fields": {"status": "done"},
            "evidence": "second capture says done",
        },
        operation_type="update_entity",
    )

    report1_id = _assemble_report_for_note(app, note1_id)
    report2_id = _assemble_report_for_note(app, note2_id)

    # Accept newer report first.
    r2 = client.post(
        f"/api/v4/reports/{report2_id}/resolve",
        json={"decisions": [{"suggestion_id": s2, "action": "accept"}]},
    )
    assert r2.status_code == 200

    # Accept older report; current state already matches, so it should be a no-op.
    r1 = client.post(
        f"/api/v4/reports/{report1_id}/resolve",
        json={"decisions": [{"suggestion_id": s1, "action": "accept"}]},
    )
    assert r1.status_code == 200

    with app.app_context():
        task_entity = db.session.get(Entity, task["id"])
        assert task_entity.status == "done"


def _create_note(app, title="Source note"):
    with app.app_context():
        note = Entity(
            type="note",
            title=title,
            content="Captured source",
            status="active",
            lifecycle="active",
            source="test",
            properties={},
            ai_meta={},
            ai_status="pending",
        )
        db.session.add(note)
        db.session.flush()
        note_id = note.id
        db.session.commit()
        return note_id


def _create_suggestion(app, source_entity_id, suggestion_type, payload, operation_type="create_entity"):
    with app.app_context():
        suggestion = AiSuggestion(
            source_entity_id=source_entity_id,
            suggestion_type=suggestion_type,
            operation_type=operation_type,
            payload=payload,
            confidence=0.91,
            reason=payload.get("evidence"),
            status="pending",
        )
        db.session.add(suggestion)
        db.session.flush()
        suggestion_id = suggestion.id
        db.session.commit()
        return suggestion_id


def _assemble_report_for_note(app, note_id):
    with app.app_context():
        from services.v4_report import assemble_report_for_note

        report = assemble_report_for_note(note_id)
        db.session.commit()
        return report.id
