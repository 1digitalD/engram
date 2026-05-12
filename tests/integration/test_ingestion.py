"""Integration tests for the full AI pipeline — capture flow, job processing, events.

Tests the end-to-end flow: entity creation → job enqueue → job processing → events.
All OpenAI calls are mocked.
"""

import time
import threading
from unittest.mock import patch, MagicMock

import pytest

from extensions import db
from models import Entity, Job, EntityChunk, EntityEvent
from services.job_worker import (
    register_handler,
    process_job,
    get_next_job,
    start_worker,
    stop_worker,
    is_worker_running,
    _HANDLERS,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _clear_handlers():
    _HANDLERS.clear()


def _reset_worker():
    """Fully reset worker state for clean test isolation."""
    import services.job_worker as jw
    jw._stop_event.set()
    if jw._worker_thread is not None:
        jw._worker_thread.join(timeout=2)
    jw._worker_thread = None
    jw._worker_app = None
    jw._stop_event = threading.Event()


def _create_entity(entity_type="note", title="Test", content="Hello world"):
    entity = Entity(
        type=entity_type,
        title=title,
        content=content,
        properties={},
        ai_meta={},
        ai_status="pending",
    )
    db.session.add(entity)
    db.session.commit()
    return entity


# ─── Full Pipeline: Capture → Classify → Embed ──────────────────────────────

class TestFullPipelineCapture:
    """Test the full capture flow: entity created, jobs enqueued, processed."""

    def setup_method(self):
        _clear_handlers()
        # Re-register AI pipeline handlers after clearing
        from services.ai_pipeline import register_handlers
        register_handlers()

    def teardown_method(self):
        if is_worker_running():
            stop_worker()

    @patch("services.extractor.extract")
    @patch("services.ai_pipeline._generate_embedding")
    def test_capture_async_flow(self, mock_embed, mock_extract, app):
        """Entity returned before AI runs; classify + embed jobs processed."""
        from services.ai_pipeline import (
            enqueue_classify, enqueue_embed,
            run_classify, run_embed,
        )
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="Test note",
            para_bucket="INBOX",
            confidence=0.90,
            reasoning="Test",
        )
        mock_embed.return_value = [0.1] * 1536

        with app.app_context():
            # Step 1: Create entity (simulates fast capture)
            entity = _create_entity(
                content="Meeting notes: discussed project timeline and budget."
            )
            assert entity.ai_status == "pending"

            # Step 2: Enqueue AI jobs (async — caller returns immediately)
            j1 = enqueue_classify(entity.id)
            j2 = enqueue_embed(entity.id)

            assert j1.status == "pending"
            assert j2.status == "pending"

            # Step 3: Process classify job
            classify_job = get_next_job()
            assert classify_job is not None
            assert classify_job.job_type == "classify"
            process_job(classify_job)

            db.session.refresh(entity)
            assert entity.ai_status == "done"

            # Verify entity_event written
            events = EntityEvent.query.filter_by(
                entity_id=entity.id, event_type="ai_classified"
            ).all()
            assert len(events) == 1
            assert events[0].actor == "agent:classify"

            # Step 4: Process embed job
            embed_job = get_next_job()
            assert embed_job is not None
            assert embed_job.job_type == "embed"
            process_job(embed_job)

            chunks = EntityChunk.query.filter_by(entity_id=entity.id).all()
            assert len(chunks) >= 1

    @patch("services.extractor.extract")
    def test_classify_event_logged_with_actor(self, mock_extract, app):
        """run_classify must write entity_event with actor='agent:classify'."""
        from services.ai_pipeline import enqueue_classify, run_classify
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="Test",
            para_bucket="INBOX",
            confidence=0.85,
            reasoning="Test reasoning",
        )

        with app.app_context():
            entity = _create_entity(content="Test content")
            job = enqueue_classify(entity.id)
            process_job(job)

            events = EntityEvent.query.filter_by(
                entity_id=entity.id,
                event_type="ai_classified",
                actor="agent:classify",
            ).all()
            assert len(events) == 1
            assert events[0].confidence == 0.85

    @patch("services.extractor.extract")
    def test_confidence_gate_092_new_entity(self, mock_extract, app):
        """Confidence >= 0.92: new project auto-created + entity_event."""
        from services.ai_pipeline import enqueue_classify, run_classify
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="Working on Rocket project",
            para_bucket="PROJECTS",
            confidence=0.95,
            suggested_project="Rocket",
            reasoning="Clear project mention with high confidence",
        )

        with app.app_context():
            entity = _create_entity(content="Working on Rocket project")
            job = enqueue_classify(entity.id)
            process_job(job)

            # New project entity should be created
            projects = Entity.query.filter_by(type="project", title="Rocket").all()
            assert len(projects) >= 1

            # Entity event for the classification
            events = EntityEvent.query.filter_by(
                entity_id=entity.id, event_type="ai_classified"
            ).all()
            assert len(events) == 1

    @patch("services.extractor.extract")
    def test_confidence_70_91_existing_linked_not_created(self, mock_extract, app):
        """Confidence 0.70-0.91: suggestion stored in ai_meta, no new entity."""
        from services.ai_pipeline import enqueue_classify, run_classify
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="Maybe related to something",
            para_bucket="PROJECTS",
            confidence=0.80,
            suggested_project="Maybe Project",
            reasoning="Uncertain project mention",
        )

        with app.app_context():
            entity = _create_entity(content="Test content")
            initial_projects = Entity.query.filter_by(type="project").count()

            job = enqueue_classify(entity.id)
            process_job(job)

            # No new project created
            final_projects = Entity.query.filter_by(type="project").count()
            assert final_projects == initial_projects

            # Suggestion stored in ai_meta
            db.session.refresh(entity)
            ai_meta = entity.ai_meta or {}
            assert "suggestions" in ai_meta or "classification" in ai_meta

    @patch("services.extractor.extract")
    def test_confidence_below_70_ai_meta_only(self, mock_extract, app):
        """Confidence < 0.70: stored in ai_meta only, no mutations."""
        from services.ai_pipeline import enqueue_classify, run_classify
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="Unclear content",
            para_bucket="INBOX",
            confidence=0.50,
            reasoning="Very uncertain classification",
        )

        with app.app_context():
            entity = _create_entity(content="Random gibberish xyz")
            initial_count = Entity.query.count()

            job = enqueue_classify(entity.id)
            process_job(job)

            # No new entities created
            assert Entity.query.count() == initial_count

            # ai_meta updated with the result
            db.session.refresh(entity)
            assert entity.ai_meta is not None

    @patch("services.extractor.extract")
    def test_classify_extraction_failure_retries(self, mock_extract, app):
        """run_classify with extraction failure: entity.ai_status='failed', job retried."""
        from services.ai_pipeline import enqueue_classify, run_classify

        mock_extract.side_effect = RuntimeError("OpenAI API timeout")

        with app.app_context():
            entity = _create_entity(content="Test content")
            job = enqueue_classify(entity.id)
            process_job(job)

            db.session.refresh(entity)
            assert entity.ai_status == "failed"

            db.session.refresh(job)
            assert job.status == "failed"
            assert job.attempts == 1
            assert job.run_after is not None  # Scheduled for retry

    @patch("services.ai_pipeline._generate_embedding")
    def test_embed_stores_chunks_with_model(self, mock_embed, app):
        """Embedding job stores chunks with correct embedding model."""
        from services.ai_pipeline import enqueue_embed, run_embed

        mock_embed.return_value = [0.05] * 1536

        with app.app_context():
            entity = _create_entity(content="Important meeting notes. " * 20)
            job = enqueue_embed(entity.id)
            process_job(job)

            chunks = EntityChunk.query.filter_by(entity_id=entity.id).all()
            assert len(chunks) >= 1
            for chunk in chunks:
                assert chunk.embedding_model == "text-embedding-3-small"
                assert chunk.embedding is not None
                assert len(chunk.embedding) == 1536


# ─── Background Worker Integration ──────────────────────────────────────────

class TestBackgroundWorkerPipeline:
    """Test that the background worker processes AI pipeline jobs correctly."""

    def setup_method(self):
        _clear_handlers()
        _reset_worker()
        # Re-register AI pipeline handlers after clearing
        from services.ai_pipeline import register_handlers
        register_handlers()

    def teardown_method(self):
        stop_worker()

    @patch("services.extractor.extract")
    @patch("services.ai_pipeline._generate_embedding")
    def test_worker_processes_classify_and_embed(self, mock_embed, mock_extract, app):
        """Background worker picks up and processes classify + embed jobs."""
        from services.ai_pipeline import (
            enqueue_classify, enqueue_embed,
        )
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="Test",
            para_bucket="INBOX",
            confidence=0.90,
            reasoning="Test",
        )
        mock_embed.return_value = [0.1] * 1536

        with app.app_context():
            entity = _create_entity(content="Test content for worker")
            enqueue_classify(entity.id)
            enqueue_embed(entity.id)

            pending = Job.query.filter_by(status="pending").count()
            assert pending == 2

            # Start worker
            start_worker(app=app, poll_interval=0.3)
            time.sleep(3)
            stop_worker()

            db.session.refresh(entity)
            assert entity.ai_status == "done"

            done_jobs = Job.query.filter_by(status="done").count()
            assert done_jobs == 2
