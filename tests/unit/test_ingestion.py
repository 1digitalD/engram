"""Unit tests for services/ingestion.py — v2 Entity model.

Note: services/ingestion.py uses Python 3.10+ type syntax (object | None).
These tests are skipped on Python < 3.10.
"""
import sys
import pytest

if sys.version_info < (3, 10):
    pytest.skip("services/ingestion.py requires Python 3.10+", allow_module_level=True)

import base64
from unittest.mock import patch, MagicMock

from extensions import db
from models import Entity, EntityTag, EntityLink, Tag


class TestExtractFromPDF:
    def test_extract_from_pdf_success(self):
        from services.ingestion import extract_from_pdf
        with patch("pymupdf4llm.to_markdown", return_value="# Test PDF"):
            with patch("pymupdf.open"):
                result = extract_from_pdf(b"fake pdf bytes")
                assert result == "# Test PDF"

    def test_extract_from_pdf_failure(self):
        from services.ingestion import extract_from_pdf
        with patch("pymupdf.open", side_effect=Exception("bad")):
            result = extract_from_pdf(b"fake pdf bytes")
            assert result == ""


class TestExtractFromURL:
    def test_extract_from_url_success(self):
        from services.ingestion import extract_from_url
        with patch("trafilatura.fetch_url", return_value="<html>test</html>"):
            with patch("trafilatura.extract", return_value="Extracted text"):
                result = extract_from_url("https://example.com")
                assert result == "Extracted text"

    def test_extract_from_url_failure(self):
        from services.ingestion import extract_from_url
        with patch("trafilatura.fetch_url", side_effect=Exception("bad")):
            result = extract_from_url("https://example.com")
            assert result == ""

    def test_extract_from_url_no_content(self):
        from services.ingestion import extract_from_url
        with patch("trafilatura.fetch_url", return_value=None):
            result = extract_from_url("https://example.com")
            assert result == ""


class TestFetchMediaBytes:
    def test_fetch_media_bytes_success(self):
        from services.ingestion import fetch_media_bytes
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"binary data"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = fetch_media_bytes("https://example.com/file.pdf")
            assert result == b"binary data"

    def test_fetch_media_bytes_failure(self):
        from services.ingestion import fetch_media_bytes
        with patch("urllib.request.urlopen", side_effect=Exception("bad")):
            result = fetch_media_bytes("https://example.com/file.pdf")
            assert result == b""


class TestNormalize:
    def test_normalize_basic(self):
        from services.ingestion import _normalize
        assert _normalize("Hello World!") == "hello world"

    def test_normalize_empty(self):
        from services.ingestion import _normalize
        assert _normalize("") == ""


class TestResolveEntity:
    def test_resolve_exact_match(self):
        from services.ingestion import _resolve_entity
        existing = [MagicMock(title="Test Project")]
        result = _resolve_entity("Test Project", existing)
        assert result is existing[0]

    def test_resolve_normalized_match(self):
        from services.ingestion import _resolve_entity
        existing = [MagicMock(title="Test Project!")]
        result = _resolve_entity("test project", existing)
        assert result is existing[0]

    def test_resolve_no_match(self):
        from services.ingestion import _resolve_entity
        existing = [MagicMock(title="Something Else")]
        result = _resolve_entity("Test Project", existing)
        assert result is None

    def test_resolve_empty_name(self):
        from services.ingestion import _resolve_entity
        result = _resolve_entity("", [MagicMock()])
        assert result is None

    def test_resolve_empty_existing(self):
        from services.ingestion import _resolve_entity
        result = _resolve_entity("Test", [])
        assert result is None

    def test_resolve_none_title(self):
        from services.ingestion import _resolve_entity
        existing = [MagicMock(title=None)]
        result = _resolve_entity("Test", existing)
        assert result is None


class TestRunIngestion:
    def test_ingestion_no_content_error(self, app):
        from services.ingestion import run_ingestion
        with app.app_context():
            result = run_ingestion(content="")
            assert "error" in result

    def test_ingestion_creates_entity(self, app):
        from services.ingestion import run_ingestion
        from services.extractor import ExtractionResult

        mock_ext = ExtractionResult(
            confidence=0.9,
            para_bucket="PROJECTS",
            suggested_project=None,
            suggested_area=None,
            tasks=[],
            people=[],
            tags=[],
            summary="Test",
            reasoning="Test",
        )

        with app.app_context():
            with patch("services.extractor.extract", return_value=mock_ext):
                result = run_ingestion(content="Test content", source="test")
                assert "entity" in result
                assert result["confident"] is True
                assert result["extraction"]["confidence"] == 0.9

                # Verify Entity record was created
                entity = db.session.get(Entity, result["entity"]["id"])
                assert entity is not None
                assert entity.type == "note"
                assert entity.content == "Test content"

    def test_ingestion_low_confidence_goes_to_inbox(self, app):
        from services.ingestion import run_ingestion
        from services.extractor import ExtractionResult

        mock_ext = ExtractionResult(
            confidence=0.5,
            para_bucket="PROJECTS",
            suggested_project=None,
            suggested_area=None,
            tasks=[],
            people=[],
            tags=[],
            summary="Test",
            reasoning="Test",
        )

        with app.app_context():
            with patch("services.extractor.extract", return_value=mock_ext):
                result = run_ingestion(content="Test content", source="test")
                assert result["confident"] is False
                entity = db.session.get(Entity, result["entity"]["id"])
                assert entity.properties.get("bucket") == "INBOX"

    def test_ingestion_creates_project(self, app):
        from services.ingestion import run_ingestion
        from services.extractor import ExtractionResult

        mock_ext = ExtractionResult(
            confidence=0.9,
            para_bucket="INBOX",
            suggested_project="New Project",
            suggested_area=None,
            tasks=[],
            people=[],
            tags=[],
            summary="Test",
            reasoning="Test",
        )

        with app.app_context():
            with patch("services.extractor.extract", return_value=mock_ext):
                result = run_ingestion(content="Test content about New Project", source="test")
                assert result["project"] is not None
                assert result["project"]["name"] == "New Project"

                # Verify project is an Entity with type='project'
                project = db.session.get(Entity, result["project"]["id"])
                assert project.type == "project"
                assert project.title == "New Project"

    def test_ingestion_creates_area(self, app):
        from services.ingestion import run_ingestion
        from services.extractor import ExtractionResult

        mock_ext = ExtractionResult(
            confidence=0.9,
            para_bucket="INBOX",
            suggested_project=None,
            suggested_area="Health",
            tasks=[],
            people=[],
            tags=[],
            summary="Test",
            reasoning="Test",
        )

        with app.app_context():
            with patch("services.extractor.extract", return_value=mock_ext):
                result = run_ingestion(content="Test content about Health", source="test")
                assert result["area"] is not None
                assert result["area"]["name"] == "Health"

                area = db.session.get(Entity, result["area"]["id"])
                assert area.type == "area"
                assert area.title == "Health"

    def test_ingestion_resolves_existing_project(self, app):
        from services.ingestion import run_ingestion
        from services.extractor import ExtractionResult

        with app.app_context():
            project = Entity(
                type="project",
                title="Existing Project",
                content="Test",
                properties={},
                lifecycle="active",
                ai_meta={},
                ai_status="pending",
            )
            db.session.add(project)
            db.session.commit()

            mock_ext = ExtractionResult(
                confidence=0.9,
                para_bucket="INBOX",
                suggested_project="Existing Project",
                suggested_area=None,
                tasks=[],
                people=[],
                tags=[],
                summary="Test",
                reasoning="Test",
            )

            with patch("services.extractor.extract", return_value=mock_ext):
                result = run_ingestion(content="Test content", source="test")
                assert result["project"]["id"] == project.id
                assert Entity.query.filter_by(type="project").count() == 1

    def test_ingestion_with_tags(self, app):
        from services.ingestion import run_ingestion
        from services.extractor import ExtractionResult

        mock_ext = ExtractionResult(
            confidence=0.9,
            para_bucket="PROJECTS",
            suggested_project=None,
            suggested_area=None,
            tasks=[],
            people=[],
            tags=["important", "review"],
            summary="Test",
            reasoning="Test",
        )

        with app.app_context():
            with patch("services.extractor.extract", return_value=mock_ext):
                result = run_ingestion(content="Test content", source="test")
                entity_id = result["entity"]["id"]

                # Verify tags attached via EntityTag
                entity_tags = EntityTag.query.filter_by(entity_id=entity_id).all()
                assert len(entity_tags) == 2

                tag_names = [et.tag.name for et in entity_tags]
                assert "important" in tag_names
                assert "review" in tag_names

    def test_ingestion_creates_links(self, app):
        from services.ingestion import run_ingestion
        from services.extractor import ExtractionResult

        mock_ext = ExtractionResult(
            confidence=0.9,
            para_bucket="INBOX",
            suggested_project="Linked Project",
            suggested_area=None,
            tasks=[],
            people=[],
            tags=[],
            summary="Test",
            reasoning="Test",
        )

        with app.app_context():
            with patch("services.extractor.extract", return_value=mock_ext):
                result = run_ingestion(content="Test content", source="test")
                entity_id = result["entity"]["id"]
                project_id = result["project"]["id"]

                # Verify link created between entity and project
                link = EntityLink.query.filter_by(
                    src_id=entity_id,
                    dst_id=project_id,
                    link_type="related",
                ).first()
                assert link is not None
                assert link.source == "ingestion"

    def test_ingestion_enqueues_jobs(self, app):
        from services.ingestion import run_ingestion
        from services.extractor import ExtractionResult
        from models import Job

        mock_ext = ExtractionResult(
            confidence=0.9,
            para_bucket="PROJECTS",
            suggested_project=None,
            suggested_area=None,
            tasks=[],
            people=[],
            tags=[],
            summary="Test",
            reasoning="Test",
        )

        with app.app_context():
            with patch("services.extractor.extract", return_value=mock_ext):
                result = run_ingestion(content="Test content", source="test")
                entity_id = result["entity"]["id"]

                # Verify embed and autolink jobs were enqueued
                jobs = Job.query.filter_by(entity_id=entity_id).all()
                job_types = [j.job_type for j in jobs]
                assert "embed" in job_types
                assert "autolink" in job_types

    def test_ingestion_creates_task_entities(self, app):
        from services.ingestion import run_ingestion
        from services.extractor import ExtractionResult, ExtractedTask

        mock_ext = ExtractionResult(
            confidence=0.9,
            para_bucket="PROJECTS",
            suggested_project=None,
            suggested_area=None,
            tasks=[
                ExtractedTask(title="Follow up with team", priority="HIGH"),
            ],
            people=[],
            tags=[],
            summary="Test",
            reasoning="Test",
        )

        with app.app_context():
            with patch("services.extractor.extract", return_value=mock_ext):
                result = run_ingestion(content="Test content", source="test")
                assert len(result["tasks"]) == 1

                # Verify task is an Entity with type='task'
                task = db.session.get(Entity, result["tasks"][0]["id"])
                assert task.type == "task"
                assert task.title == "Follow up with team"
                assert task.properties.get("priority") == "HIGH"

                # Verify task linked to parent note
                link = EntityLink.query.filter_by(
                    src_id=task.id,
                    dst_id=result["entity"]["id"],
                ).first()
                assert link is not None

    def test_ingestion_with_pdf_media(self, app):
        from services.ingestion import run_ingestion
        from services.extractor import ExtractionResult

        mock_ext = ExtractionResult(
            confidence=0.9,
            para_bucket="PROJECTS",
            suggested_project=None,
            suggested_area=None,
            tasks=[],
            people=[],
            tags=[],
            summary="Test",
            reasoning="Test",
        )

        pdf_b64 = base64.b64encode(b"fake pdf").decode()

        with app.app_context():
            with patch("services.extractor.extract", return_value=mock_ext):
                with patch("services.ingestion.extract_from_pdf", return_value="PDF content"):
                    result = run_ingestion(
                        content="Test",
                        media_base64=pdf_b64,
                        media_type="pdf",
                        source="test",
                    )
                    assert "entity" in result

    def test_ingestion_with_url_media(self, app):
        from services.ingestion import run_ingestion
        from services.extractor import ExtractionResult

        mock_ext = ExtractionResult(
            confidence=0.9,
            para_bucket="PROJECTS",
            suggested_project=None,
            suggested_area=None,
            tasks=[],
            people=[],
            tags=[],
            summary="Test",
            reasoning="Test",
        )

        with app.app_context():
            with patch("services.extractor.extract", return_value=mock_ext):
                with patch("services.ingestion.extract_from_url", return_value="URL content"):
                    result = run_ingestion(
                        content="Test",
                        media_url="https://example.com",
                        media_type="url",
                        source="test",
                    )
                    assert "entity" in result

    def test_ingestion_low_confidence_defaults_to_inbox(self, app):
        from services.ingestion import run_ingestion
        from services.extractor import ExtractionResult

        # Low confidence forces INBOX regardless of para_bucket
        mock_ext = ExtractionResult(
            confidence=0.5,
            para_bucket="PROJECTS",
            suggested_project=None,
            suggested_area=None,
            tasks=[],
            people=[],
            tags=[],
            summary="Test",
            reasoning="Test",
        )

        with app.app_context():
            with patch("services.extractor.extract", return_value=mock_ext):
                result = run_ingestion(content="Test content", source="test")
                entity = db.session.get(Entity, result["entity"]["id"])
                assert entity.properties.get("bucket") == "INBOX"
