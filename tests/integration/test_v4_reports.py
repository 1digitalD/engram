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
