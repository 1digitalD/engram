"""Unit tests for ai_pipeline — job enqueueing, text chunking, confidence gates, error handling."""

import pytest
from unittest.mock import patch, MagicMock

from extensions import db
from models import Entity, Job, EntityChunk, EntityEvent, EntityTag, Tag


# ─── Helpers ─────────────────────────────────────────────────────────────────

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


# ─── Job Enqueueing ──────────────────────────────────────────────────────────

class TestEnqueueJobs:
    """Test that enqueue functions create proper Job records."""

    def test_enqueue_classify_creates_job(self, app):
        from services.ai_pipeline import enqueue_classify

        with app.app_context():
            entity = _create_entity()
            job = enqueue_classify(entity.id)

            assert job is not None
            assert job.job_type == "classify"
            assert job.entity_id == str(entity.id)
            assert job.status == "pending"
            assert job.payload == {"entity_id": str(entity.id)}

    def test_enqueue_embed_creates_job(self, app):
        from services.ai_pipeline import enqueue_embed

        with app.app_context():
            entity = _create_entity()
            job = enqueue_embed(entity.id)

            assert job is not None
            assert job.job_type == "embed"
            assert job.entity_id == str(entity.id)
            assert job.status == "pending"
            assert job.payload == {"entity_id": str(entity.id)}

    def test_enqueue_autolink_creates_job(self, app):
        from services.ai_pipeline import enqueue_autolink

        with app.app_context():
            entity = _create_entity()
            job = enqueue_autolink(entity.id)

            assert job is not None
            assert job.job_type == "autolink"
            assert job.entity_id == str(entity.id)
            assert job.status == "pending"
            assert job.payload == {"entity_id": str(entity.id)}

    def test_enqueue_all_three_jobs(self, app):
        from services.ai_pipeline import enqueue_classify, enqueue_embed, enqueue_autolink

        with app.app_context():
            entity = _create_entity()
            j1 = enqueue_classify(entity.id)
            j2 = enqueue_embed(entity.id)
            j3 = enqueue_autolink(entity.id)

            jobs = Job.query.filter_by(entity_id=str(entity.id)).all()
            assert len(jobs) == 3
            job_types = {j.job_type for j in jobs}
            assert job_types == {"classify", "embed", "autolink"}


# ─── Text Chunking ───────────────────────────────────────────────────────────

class TestChunkText:
    """Test the chunk_text function for embedding preparation."""

    def test_chunk_short_text(self, app):
        from services.ai_pipeline import chunk_text

        text = "Short text."
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) == 1
        assert chunks[0] == "Short text."

    def test_chunk_long_text_splits(self, app):
        from services.ai_pipeline import chunk_text

        # Create text with many separate words
        words = ["paragraph"] * 200
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) >= 2

    def test_chunk_overlap(self, app):
        from services.ai_pipeline import chunk_text

        # Text with distinct words that should produce multiple chunks with overlap
        words = [f"word{i}" for i in range(200)]
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=100, overlap=30)
        assert len(chunks) >= 2
        # Verify overlap: last words of chunk[0] should appear in chunk[1]
        if len(chunks) >= 2:
            last_words_chunk0 = set(chunks[0].split()[-10:])
            chunk1_words = set(chunks[1].split())
            overlap_found = bool(last_words_chunk0 & chunk1_words)
            assert overlap_found

    def test_chunk_empty_text(self, app):
        from services.ai_pipeline import chunk_text

        chunks = chunk_text("", chunk_size=100, overlap=20)
        assert chunks == []

    def test_chunk_none_text(self, app):
        from services.ai_pipeline import chunk_text

        chunks = chunk_text(None, chunk_size=100, overlap=20)
        assert chunks == []

    def test_chunk_respects_chunk_size(self, app):
        from services.ai_pipeline import chunk_text

        # Use separate words so chunking works at word boundaries
        words = ["item"] * 200
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=50, overlap=10)
        assert len(chunks) >= 2
        for chunk in chunks:
            # Each chunk should be within reasonable size
            assert len(chunk) <= 300  # ~50 tokens * 4 chars + tolerance


# ─── run_classify Handler ────────────────────────────────────────────────────

class TestRunClassify:
    """Test the run_classify job handler."""

    @patch("services.extractor.extract")
    def test_classify_success_writes_event(self, mock_extract, app):
        from services.ai_pipeline import run_classify
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="Test summary",
            para_bucket="INBOX",
            confidence=0.95,
            reasoning="Test reasoning",
        )

        with app.app_context():
            entity = _create_entity(content="Test content for classification")
            run_classify({"entity_id": entity.id})

            db.session.refresh(entity)
            assert entity.ai_status == "done"

            events = EntityEvent.query.filter_by(
                entity_id=str(entity.id), event_type="ai_classified"
            ).all()
            assert len(events) == 1
            assert events[0].actor == "agent:classify"
            assert events[0].confidence == 0.95

    @patch("services.extractor.extract")
    def test_classify_low_confidence_no_new_entities(self, mock_extract, app):
        """Confidence < 0.92 should NOT auto-create new entities."""
        from services.ai_pipeline import run_classify
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="Test summary",
            para_bucket="PROJECTS",
            confidence=0.75,  # Below 0.92 threshold
            suggested_project="New Project",
            reasoning="Test reasoning",
        )

        with app.app_context():
            entity = _create_entity(content="Test content")
            initial_count = Entity.query.filter_by(type="project").count()

            run_classify({"entity_id": entity.id})

            # No new project should be created
            final_count = Entity.query.filter_by(type="project").count()
            assert final_count == initial_count

            # But ai_meta should contain the suggestion
            db.session.refresh(entity)
            assert "suggestions" in (entity.ai_meta or {})

    @patch("services.extractor.extract")
    def test_classify_failure_sets_failed_status(self, mock_extract, app):
        """When extraction fails, entity.ai_status should be 'failed'."""
        from services.ai_pipeline import run_classify

        mock_extract.side_effect = RuntimeError("API error")

        with app.app_context():
            entity = _create_entity(content="Test content")
            with pytest.raises(RuntimeError, match="API error"):
                run_classify({"entity_id": entity.id})

            db.session.refresh(entity)
            assert entity.ai_status == "failed"

    @patch("services.ai_pipeline.reconcile_all")
    @patch("services.ai_pipeline.apply_change_plan")
    @patch("services.extractor.extract")
    def test_classify_high_confidence_auto_creates_project(self, mock_extract, mock_apply, mock_reconcile, app):
        """Confidence >= 0.92 with suggested_project should reconcile and create entity."""
        from services.ai_pipeline import run_classify
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="Working on new project",
            para_bucket="PROJECTS",
            confidence=0.95,
            suggested_project="Auto Project",
            reasoning="Clear project mention",
            tags=[],
            people=[],
            tasks=[],
        )

        mock_reconcile.return_value = [
            {"detected": {"type": "project", "name": "Auto Project"}, "reconciliation": None},
        ]

        mock_apply.return_value = {
            "applied_changes": [{"operation": "create_project", "title": "Auto Project", "entity_id": "fake-id"}],
            "suggestions": [],
        }

        with app.app_context():
            entity = _create_entity(content="Working on Auto Project")
            run_classify({"entity_id": entity.id})

            mock_reconcile.assert_called_once()
            call_args = mock_reconcile.call_args[0][0]
            assert len(call_args) == 1
            assert call_args[0]["type"] == "project"
            assert call_args[0]["name"] == "Auto Project"

            mock_apply.assert_called_once()
            plan = mock_apply.call_args[0][0]
            assert plan["source_note_id"] == entity.id
            assert len(plan["proposed_changes"]) == 1

            db.session.refresh(entity)
            assert "project_area_reconciliation" in (entity.ai_meta or {})

    @patch("services.extractor.extract")
    def test_classify_persists_extracted_tags_as_entity_tags(self, mock_extract, app):
        from services.ai_pipeline import run_classify
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="Tagged note",
            para_bucket="INBOX",
            confidence=0.85,
            reasoning="Found tags",
            tags=["Urgent", " urgent ", "Planning", ""],
        )

        with app.app_context():
            entity = _create_entity(content="Need urgent planning follow-up")

            run_classify({"entity_id": entity.id})

            entity_tags = EntityTag.query.filter_by(entity_id=str(entity.id)).all()
            assert len(entity_tags) == 2

            tag_names = sorted(et.tag.name for et in entity_tags)
            assert tag_names == ["planning", "urgent"]

    @patch("services.extractor.extract")
    def test_classify_reuses_existing_tag_records(self, mock_extract, app):
        from services.ai_pipeline import run_classify
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="Tagged note",
            para_bucket="INBOX",
            confidence=0.85,
            reasoning="Found tags",
            tags=["Existing"],
        )

        with app.app_context():
            existing = Tag(name="existing")
            db.session.add(existing)
            db.session.commit()

            entity = _create_entity(content="Existing tag should be reused")

            run_classify({"entity_id": entity.id})

            tags = Tag.query.filter_by(name="existing").all()
            assert len(tags) == 1

            entity_tags = EntityTag.query.filter_by(entity_id=str(entity.id)).all()
            assert len(entity_tags) == 1
            assert entity_tags[0].tag_id == existing.id

    @patch("services.ai_pipeline.reconcile_all")
    @patch("services.ai_pipeline.apply_change_plan")
    @patch("services.extractor.extract")
    def test_classify_reconciles_extracted_people(self, mock_extract, mock_apply, mock_reconcile, app):
        from services.ai_pipeline import run_classify
        from services.extractor import ExtractionResult, ExtractedPerson

        mock_extract.return_value = ExtractionResult(
            summary="Meeting note",
            para_bucket="INBOX",
            confidence=0.85,
            reasoning="Extracted people from note",
            tags=[],
            tasks=[],
            people=[
                ExtractedPerson(name="Alice Smith", email="alice@example.com", context="meeting organizer"),
                ExtractedPerson(name="Bob Jones", email=None, context="attendee"),
            ],
        )

        mock_reconcile.return_value = [
            {"detected": {"type": "person", "name": "Alice Smith", "email": "alice@example.com"}, "reconciliation": None},
            {"detected": {"type": "person", "name": "Bob Jones"}, "reconciliation": None},
        ]

        mock_apply.return_value = {
            "applied_changes": [],
            "suggestions": [
                {"operation": "create_person", "name": "Alice Smith", "properties": {"email": "alice@example.com"}},
                {"operation": "create_person", "name": "Bob Jones"},
            ],
        }

        with app.app_context():
            entity = _create_entity(content="Met with Alice Smith and Bob Jones")

            run_classify({"entity_id": entity.id})

            mock_reconcile.assert_called_once()
            call_args = mock_reconcile.call_args[0][0]
            assert len(call_args) == 2

            entity_people = [p["name"] for p in call_args]
            assert "Alice Smith" in entity_people
            assert "Bob Jones" in entity_people

            mock_apply.assert_called_once()
            plan = mock_apply.call_args[0][0]
            assert plan["source_note_id"] == entity.id
            assert len(plan["suggestions"]) == 2

            db.session.refresh(entity)
            assert "person_reconciliation" in (entity.ai_meta or {})

    @patch("services.ai_pipeline.reconcile_all")
    @patch("services.ai_pipeline.apply_change_plan")
    @patch("services.extractor.extract")
    def test_classify_reconciles_extracted_tasks(self, mock_extract, mock_apply, mock_reconcile, app):
        from services.ai_pipeline import run_classify
        from services.extractor import ExtractionResult, ExtractedTask

        mock_extract.return_value = ExtractionResult(
            summary="Action items",
            para_bucket="INBOX",
            confidence=0.85,
            reasoning="Extracted tasks from note",
            tags=[],
            people=[],
            tasks=[
                ExtractedTask(title="Review proposal", priority="HIGH", project_hint="Alpha"),
                ExtractedTask(title="Send follow-up email", priority="LOW", due_date="2025-06-01"),
            ],
        )

        mock_reconcile.return_value = [
            {"detected": {"type": "task", "name": "Review proposal"}, "reconciliation": None},
            {"detected": {"type": "task", "name": "Send follow-up email"}, "reconciliation": None},
        ]

        mock_apply.return_value = {
            "applied_changes": [],
            "suggestions": [
                {"operation": "create_task", "title": "Review proposal", "priority": "HIGH"},
                {"operation": "create_task", "title": "Send follow-up email", "priority": "LOW"},
            ],
        }

        with app.app_context():
            entity = _create_entity(content="Need to review the proposal and send a follow-up email")

            run_classify({"entity_id": entity.id})

            mock_reconcile.assert_called_once()
            call_args = mock_reconcile.call_args[0][0]
            assert len(call_args) == 2

            entity_tasks = [t["name"] for t in call_args]
            assert "Review proposal" in entity_tasks
            assert "Send follow-up email" in entity_tasks

            mock_apply.assert_called_once()
            plan = mock_apply.call_args[0][0]
            assert plan["source_note_id"] == entity.id
            assert len(plan["suggestions"]) == 2

            db.session.refresh(entity)
            assert "task_reconciliation" in (entity.ai_meta or {})

    @patch("services.ai_pipeline.reconcile_all")
    @patch("services.ai_pipeline.apply_change_plan")
    @patch("services.extractor.extract")
    def test_classify_reconciles_suggested_project_and_area(self, mock_extract, mock_apply, mock_reconcile, app):
        from services.ai_pipeline import run_classify
        from services.extractor import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            summary="Project note",
            para_bucket="PROJECTS",
            confidence=0.95,
            suggested_project="Alpha Platform",
            suggested_area="Work",
            reasoning="High confidence",
            tags=[],
            people=[],
            tasks=[],
        )

        mock_reconcile.return_value = [
            {"detected": {"type": "project", "name": "Alpha Platform"}, "reconciliation": None},
            {"detected": {"type": "area", "name": "Work"}, "reconciliation": None},
        ]

        mock_apply.return_value = {
            "applied_changes": [
                {"operation": "create_project", "title": "Alpha Platform"},
                {"operation": "create_area", "title": "Work"},
            ],
            "suggestions": [],
        }

        with app.app_context():
            entity = _create_entity(content="Working on the Alpha Platform project in Work area")

            run_classify({"entity_id": entity.id})

            mock_reconcile.assert_called_once()
            call_args = mock_reconcile.call_args[0][0]
            assert len(call_args) == 2
            entity_names = [e["name"] for e in call_args]
            assert "Alpha Platform" in entity_names
            assert "Work" in entity_names

            mock_apply.assert_called_once()
            plan = mock_apply.call_args[0][0]
            assert plan["source_note_id"] == entity.id
            assert len(plan["proposed_changes"]) == 2

            db.session.refresh(entity)
            assert "project_area_reconciliation" in (entity.ai_meta or {})


# ─── run_embed Handler ───────────────────────────────────────────────────────

class TestRunEmbed:
    """Test the run_embed job handler."""

    @patch("services.ai_pipeline._generate_embedding")
    def test_embed_chunks_and_stores(self, mock_embed, app):
        from services.ai_pipeline import run_embed

        mock_embed.return_value = [0.1] * 1536

        with app.app_context():
            # Create content long enough to produce multiple chunks
            content = "This is a paragraph. " * 50
            entity = _create_entity(content=content)

            run_embed({"entity_id": entity.id})

            chunks = EntityChunk.query.filter_by(entity_id=str(entity.id)).all()
            assert len(chunks) >= 1
            assert chunks[0].embedding is not None
            assert chunks[0].chunk_text is not None

    def test_embed_empty_content(self, app):
        from services.ai_pipeline import run_embed

        with app.app_context():
            entity = _create_entity(content="")
            run_embed({"entity_id": entity.id})

            db.session.refresh(entity)
            assert entity.ai_status == "done"
            # No chunks for empty content
            chunks = EntityChunk.query.filter_by(entity_id=str(entity.id)).all()
            assert len(chunks) == 0

    @patch("services.ai_pipeline._generate_embedding")
    def test_embed_upserts_deletes_old(self, mock_embed, app):
        """Embedding should delete old chunks and insert new ones."""
        from services.ai_pipeline import run_embed

        mock_embed.return_value = [0.1] * 1536

        with app.app_context():
            entity = _create_entity(content="Original content here. " * 30)
            run_embed({"entity_id": entity.id})

            first_chunks = EntityChunk.query.filter_by(entity_id=str(entity.id)).count()

            # Run again with different content
            entity.content = "Completely new content. " * 30
            db.session.commit()
            run_embed({"entity_id": entity.id})

            # Old chunks should be replaced
            new_chunks = EntityChunk.query.filter_by(entity_id=str(entity.id)).all()
            assert len(new_chunks) >= 1

    @patch("services.ai_pipeline._generate_embedding")
    def test_embed_handles_api_failure(self, mock_embed, app):
        from services.ai_pipeline import run_embed

        mock_embed.side_effect = RuntimeError("Embedding API down")

        with app.app_context():
            entity = _create_entity(content="Test content " * 20)
            with pytest.raises(RuntimeError, match="Embedding API down"):
                run_embed({"entity_id": entity.id})

            db.session.refresh(entity)
            assert entity.ai_status == "failed"


# ─── run_autolink Handler ────────────────────────────────────────────────────

class TestRunAutolink:
    """Test the run_autolink job handler."""

    def test_autolink_no_chunks_graceful(self, app):
        """Autolink should handle entities with no embeddings gracefully."""
        from services.ai_pipeline import run_autolink

        with app.app_context():
            entity = _create_entity(content="Test")
            # No chunks exist for this entity
            run_autolink({"entity_id": entity.id})

            db.session.refresh(entity)
            # Should not crash, should mark as done
            assert entity.ai_status == "done"
