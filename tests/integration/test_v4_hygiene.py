"""Tests for the nightly hygiene job."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from extensions import db
from models import AiSuggestion, EntityEvent, Job
from services.job_worker import get_handler
from services.v4_hygiene import HYGIENE_JOB_TYPE, run_hygiene, schedule_next_hygiene


def test_hygiene_expires_stale_suggestions_and_keeps_fresh(client, app):
    note = client.post("/api/v4/capture", json={"content": "hygiene note"}).get_json()["source_note"]

    with app.app_context():
        old = AiSuggestion(
            source_entity_id=note["id"],
            suggestion_type="create_task",
            operation_type="create_entity",
            payload={"type": "task", "title": "stale"},
        )
        fresh = AiSuggestion(
            source_entity_id=note["id"],
            suggestion_type="create_task",
            operation_type="create_entity",
            payload={"type": "task", "title": "fresh"},
        )
        db.session.add_all([old, fresh])
        db.session.flush()
        # Age the first one past the cutoff.
        old.created_at = datetime.now(timezone.utc) - timedelta(days=20)
        db.session.commit()
        old_id, fresh_id = old.id, fresh.id

        with patch("services.embeddings.backfill_embeddings", return_value=0):
            summary = run_hygiene()

        assert summary["expired_suggestions"] == 1
        assert db.session.get(AiSuggestion, old_id).status == "expired"
        assert db.session.get(AiSuggestion, fresh_id).status == "pending"
        assert EntityEvent.query.filter_by(
            entity_id=note["id"], event_type="suggestion_expired"
        ).count() == 1


def test_hygiene_reschedules_itself(client, app):
    with app.app_context():
        assert get_handler(HYGIENE_JOB_TYPE) is not None

        job = schedule_next_hygiene()
        assert job.status == "pending"
        assert job.run_after > datetime.now(timezone.utc) + timedelta(hours=23)

        # Idempotent: a second call doesn't enqueue a duplicate.
        again = schedule_next_hygiene()
        assert again.id == job.id
        assert Job.query.filter_by(job_type=HYGIENE_JOB_TYPE, status="pending").count() == 1


def test_hygiene_handler_runs_pass_and_reschedules(client, app):
    with app.app_context():
        with patch("services.v4_hygiene.run_hygiene", return_value={"embedded": 0, "expired_suggestions": 0}) as ran:
            get_handler(HYGIENE_JOB_TYPE)({"scheduled": True})
        assert ran.called
        assert Job.query.filter_by(job_type=HYGIENE_JOB_TYPE, status="pending").count() == 1
