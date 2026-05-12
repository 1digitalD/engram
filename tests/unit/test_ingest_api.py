"""Unit tests for api/ingest.py."""
import pytest
from unittest.mock import patch


class TestIngestAPI:
    def test_ingest_no_content(self, client):
        resp = client.post("/api/v1/ingest", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_ingest_with_content(self, client):
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

        with patch("services.extractor.extract", return_value=mock_ext):
            with patch("services.extractor.extract_inline_tasks"):
                resp = client.post("/api/v1/ingest", json={
                    "content": "Test ingestion content",
                    "source": "api",
                })
                assert resp.status_code == 201
                data = resp.get_json()
                assert "note" in data

    def test_ingest_with_media_url(self, client):
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

        with patch("services.extractor.extract", return_value=mock_ext):
            with patch("services.extractor.extract_inline_tasks"):
                with patch("services.ingestion.extract_from_url", return_value="URL content"):
                    resp = client.post("/api/v1/ingest", json={
                        "content": "Test",
                        "media_url": "https://example.com",
                        "media_type": "url",
                    })
                    assert resp.status_code == 201

    def test_ingest_error_handling(self, client):
        with patch("services.ingestion.run_ingestion", side_effect=Exception("Test error")):
            resp = client.post("/api/v1/ingest", json={
                "content": "Test content",
            })
            assert resp.status_code == 500
            data = resp.get_json()
            assert "error" in data

    def test_ingest_returns_400_on_service_error(self, client):
        with patch("services.ingestion.run_ingestion", return_value={"error": "no content"}):
            resp = client.post("/api/v1/ingest", json={
                "content": "Test content",
            })
            assert resp.status_code == 400
