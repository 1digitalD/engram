"""Unit tests for services/ingestion.py.

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
from models import Note, Project, Area, Person, Tag, BucketType


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
        existing = [MagicMock(name="Test Project")]
        existing[0].name = "Test Project"
        result = _resolve_entity("Test Project", existing)
        assert result is existing[0]

    def test_resolve_normalized_match(self):
        from services.ingestion import _resolve_entity
        existing = [MagicMock(name="Test Project!")]
        existing[0].name = "Test Project!"
        result = _resolve_entity("test project", existing)
        assert result is existing[0]

    def test_resolve_no_match(self):
        from services.ingestion import _resolve_entity
        existing = [MagicMock(name="Something Else")]
        existing[0].name = "Something Else"
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


class TestRunIngestion:
    def test_ingestion_no_content_error(self, app):
        from services.ingestion import run_ingestion
        with app.app_context():
            result = run_ingestion(content="")
            assert "error" in result

    def test_ingestion_confident_creates_note(self, app):
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
                with patch("services.extractor.extract_inline_tasks"):
                    result = run_ingestion(content="Test content", source="test")
                    assert "note" in result
                    assert result["confident"] is True
                    assert result["extraction"]["confidence"] == 0.9

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
                with patch("services.extractor.extract_inline_tasks"):
                    result = run_ingestion(content="Test content", source="test")
                    assert result["confident"] is False
                    note = db.session.get(Note, result["note"]["id"])
                    assert note.bucket == BucketType.INBOX

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
                with patch("services.extractor.extract_inline_tasks"):
                    result = run_ingestion(content="Test content about New Project", source="test")
                    assert result["project"] is not None
                    assert result["project"]["name"] == "New Project"

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
                with patch("services.extractor.extract_inline_tasks"):
                    result = run_ingestion(content="Test content about Health", source="test")
                    assert result["area"] is not None
                    assert result["area"]["name"] == "Health"

    def test_ingestion_resolves_existing_project(self, app):
        from services.ingestion import run_ingestion
        from services.extractor import ExtractionResult

        with app.app_context():
            project = Project(name="Existing Project", description="Test")
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
                with patch("services.extractor.extract_inline_tasks"):
                    result = run_ingestion(content="Test content", source="test")
                    assert result["project"]["id"] == project.id
                    assert Project.query.count() == 1

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
                with patch("services.extractor.extract_inline_tasks"):
                    result = run_ingestion(content="Test content", source="test")
                    note = db.session.get(Note, result["note"]["id"])
                    assert len(note.tags) == 2

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
                with patch("services.extractor.extract_inline_tasks"):
                    with patch("services.ingestion.extract_from_pdf", return_value="PDF content"):
                        result = run_ingestion(
                            content="Test",
                            media_base64=pdf_b64,
                            media_type="pdf",
                            source="test",
                        )
                        assert "note" in result

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
                with patch("services.extractor.extract_inline_tasks"):
                    with patch("services.ingestion.extract_from_url", return_value="URL content"):
                        result = run_ingestion(
                            content="Test",
                            media_url="https://example.com",
                            media_type="url",
                            source="test",
                        )
                        assert "note" in result

    def test_ingestion_invalid_bucket_defaults_to_inbox(self, app):
        from services.ingestion import run_ingestion
        from services.extractor import ExtractionResult

        mock_ext = ExtractionResult(
            confidence=0.9,
            para_bucket="UNKNOWN_BUCKET",
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
                with patch("services.extractor.extract_inline_tasks"):
                    result = run_ingestion(content="Test content", source="test")
                    note = db.session.get(Note, result["note"]["id"])
                    assert note.bucket == BucketType.INBOX
