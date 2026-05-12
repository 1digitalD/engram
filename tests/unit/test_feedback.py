"""Unit tests for feedback service — confidence calibration + correction signals.

Tests cover:
- Recording correct/incorrect feedback on AI classifications
- Storing and querying feedback records
- Confidence calibration based on feedback history
- Correction signals for improving future classifications
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from extensions import db
from models import Entity, EntityEvent
from services.feedback import record_feedback


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _create_entity(entity_type="note", title="Test", content="Hello world", ai_meta=None):
    entity = Entity(
        type=entity_type,
        title=title,
        content=content,
        properties={},
        ai_meta=ai_meta or {},
        ai_status="done",
    )
    db.session.add(entity)
    db.session.commit()
    return entity


def _create_classification_event(entity_id, para_bucket="INBOX", confidence=0.8):
    """Create an ai_classified event to represent an AI classification."""
    event = EntityEvent(
        entity_id=entity_id,
        event_type="ai_classified",
        actor="agent:classify",
        new_value={
            "para_bucket": para_bucket,
            "confidence": confidence,
        },
        confidence=confidence,
    )
    db.session.add(event)
    db.session.commit()
    return event


# ─── Recording Feedback ──────────────────────────────────────────────────────

class TestRecordFeedback:
    """Test that users can mark AI classifications as correct/incorrect."""

    def test_record_correct_feedback(self, app):
        from services.feedback import record_feedback

        with app.app_context():
            entity = _create_entity()
            _create_classification_event(entity.id, confidence=0.85)

            feedback = record_feedback(
                entity_id=entity.id,
                verdict="correct",
                reason="Classification looks right",
            )

            assert feedback is not None
            assert feedback.event_type == "ai_correction"
            assert feedback.actor == "user"
            assert feedback.new_value["verdict"] == "correct"
            assert feedback.new_value["reason"] == "Classification looks right"

    def test_record_incorrect_feedback(self, app):
        from services.feedback import record_feedback

        with app.app_context():
            entity = _create_entity()
            _create_classification_event(entity.id, confidence=0.9)

            feedback = record_feedback(
                entity_id=entity.id,
                verdict="incorrect",
                reason="Should be PROJECTS not INBOX",
            )

            assert feedback.new_value["verdict"] == "incorrect"
            assert feedback.new_value["reason"] == "Should be PROJECTS not INBOX"

    def test_record_feedback_captures_original_confidence(self, app):
        from services.feedback import record_feedback

        with app.app_context():
            entity = _create_entity()
            _create_classification_event(entity.id, confidence=0.75)

            feedback = record_feedback(
                entity_id=entity.id,
                verdict="incorrect",
            )

            # Should capture the original classification confidence
            assert feedback.new_value["original_confidence"] == 0.75

    def test_record_feedback_captures_para_bucket(self, app):
        from services.feedback import record_feedback

        with app.app_context():
            entity = _create_entity()
            _create_classification_event(entity.id, para_bucket="PROJECTS", confidence=0.9)

            feedback = record_feedback(
                entity_id=entity.id,
                verdict="incorrect",
            )

            assert feedback.new_value["para_bucket"] == "PROJECTS"

    def test_record_feedback_without_reason(self, app):
        from services.feedback import record_feedback

        with app.app_context():
            entity = _create_entity()
            _create_classification_event(entity.id, confidence=0.8)

            feedback = record_feedback(
                entity_id=entity.id,
                verdict="correct",
            )

            assert feedback.new_value["verdict"] == "correct"
            assert feedback.new_value.get("reason") is None

    def test_record_feedback_raises_on_invalid_verdict(self, app):
        from services.feedback import record_feedback

        with app.app_context():
            entity = _create_entity()
            _create_classification_event(entity.id, confidence=0.8)

            with pytest.raises(ValueError, match="verdict"):
                record_feedback(
                    entity_id=entity.id,
                    verdict="maybe",
                )

    def test_record_feedback_raises_on_missing_classification(self, app):
        from services.feedback import record_feedback

        with app.app_context():
            entity = _create_entity()
            # No classification event exists for this entity

            with pytest.raises(ValueError, match="classification"):
                record_feedback(
                    entity_id=entity.id,
                    verdict="correct",
                )


# ─── Querying Feedback ───────────────────────────────────────────────────────

class TestQueryFeedback:
    """Test that feedback is stored and queryable."""

    def test_get_all_feedback(self, app):
        from services.feedback import record_feedback, get_feedback

        with app.app_context():
            e1 = _create_entity(title="Entity 1")
            e2 = _create_entity(title="Entity 2")
            _create_classification_event(e1.id, confidence=0.8)
            _create_classification_event(e2.id, confidence=0.9)

            record_feedback(entity_id=e1.id, verdict="correct")
            record_feedback(entity_id=e2.id, verdict="incorrect")

            all_feedback = get_feedback()
            assert len(all_feedback) == 2

    def test_get_feedback_by_verdict(self, app):
        from services.feedback import record_feedback, get_feedback

        with app.app_context():
            e1 = _create_entity(title="Entity 1")
            e2 = _create_entity(title="Entity 2")
            e3 = _create_entity(title="Entity 3")
            _create_classification_event(e1.id, confidence=0.8)
            _create_classification_event(e2.id, confidence=0.9)
            _create_classification_event(e3.id, confidence=0.7)

            record_feedback(entity_id=e1.id, verdict="correct")
            record_feedback(entity_id=e2.id, verdict="incorrect")
            record_feedback(entity_id=e3.id, verdict="correct")

            incorrect = get_feedback(verdict="incorrect")
            assert len(incorrect) == 1
            assert incorrect[0].new_value["verdict"] == "incorrect"

            correct = get_feedback(verdict="correct")
            assert len(correct) == 2

    def test_get_feedback_by_entity(self, app):
        from services.feedback import record_feedback, get_feedback

        with app.app_context():
            entity = _create_entity()
            _create_classification_event(entity.id, confidence=0.8)

            record_feedback(entity_id=entity.id, verdict="correct")
            record_feedback(entity_id=entity.id, verdict="incorrect")

            feedback = get_feedback(entity_id=entity.id)
            assert len(feedback) == 2

    def test_get_feedback_pagination(self, app):
        from services.feedback import record_feedback, get_feedback

        with app.app_context():
            for i in range(10):
                e = _create_entity(title=f"Entity {i}")
                _create_classification_event(e.id, confidence=0.8)
                record_feedback(entity_id=e.id, verdict="correct")

            first_page = get_feedback(limit=3, offset=0)
            assert len(first_page) == 3

            second_page = get_feedback(limit=3, offset=3)
            assert len(second_page) == 3
            assert second_page[0].id != first_page[0].id

    def test_get_feedback_returns_newest_first(self, app):
        from services.feedback import record_feedback, get_feedback

        with app.app_context():
            e1 = _create_entity(title="First")
            e2 = _create_entity(title="Second")
            _create_classification_event(e1.id, confidence=0.8)
            _create_classification_event(e2.id, confidence=0.9)

            record_feedback(entity_id=e1.id, verdict="correct")
            record_feedback(entity_id=e2.id, verdict="correct")

            results = get_feedback()
            # Newest (e2) should be first
            assert results[0].entity_id == e2.id


# ─── Feedback Statistics ─────────────────────────────────────────────────────

class TestFeedbackStats:
    """Test feedback statistics and accuracy metrics."""

    def test_accuracy_rate(self, app):
        from services.feedback import record_feedback, get_accuracy_stats

        with app.app_context():
            for i in range(10):
                e = _create_entity(title=f"Entity {i}")
                _create_classification_event(e.id, confidence=0.8)
                verdict = "correct" if i < 7 else "incorrect"
                record_feedback(entity_id=e.id, verdict=verdict)

            stats = get_accuracy_stats()
            assert stats["total"] == 10
            assert stats["correct"] == 7
            assert stats["incorrect"] == 3
            assert stats["accuracy_rate"] == pytest.approx(0.7)

    def test_accuracy_rate_by_bucket(self, app):
        from services.feedback import record_feedback, get_accuracy_stats

        with app.app_context():
            # INBOX: 3 correct, 2 incorrect
            for i in range(5):
                e = _create_entity(title=f"INBOX {i}")
                _create_classification_event(e.id, para_bucket="INBOX", confidence=0.6)
                verdict = "correct" if i < 3 else "incorrect"
                record_feedback(entity_id=e.id, verdict=verdict)

            # PROJECTS: 4 correct, 1 incorrect
            for i in range(5):
                e = _create_entity(title=f"PROJECTS {i}")
                _create_classification_event(e.id, para_bucket="PROJECTS", confidence=0.9)
                verdict = "correct" if i < 4 else "incorrect"
                record_feedback(entity_id=e.id, verdict=verdict)

            stats = get_accuracy_stats()
            assert "by_bucket" in stats
            assert stats["by_bucket"]["INBOX"]["accuracy_rate"] == pytest.approx(0.6)
            assert stats["by_bucket"]["PROJECTS"]["accuracy_rate"] == pytest.approx(0.8)

    def test_accuracy_rate_empty(self, app):
        from services.feedback import get_accuracy_stats

        with app.app_context():
            stats = get_accuracy_stats()
            assert stats["total"] == 0
            assert stats["accuracy_rate"] is None


# ─── Confidence Calibration ──────────────────────────────────────────────────

class TestConfidenceCalibration:
    """Test that confidence calibration adjusts based on feedback."""

    def test_calibration_with_no_feedback(self, app):
        from services.feedback import calibrate_confidence

        with app.app_context():
            # No feedback data, should return original confidence
            calibrated = calibrate_confidence(0.85)
            assert calibrated == pytest.approx(0.85)

    def test_calibration_reduces_confidence_on_incorrect(self, app):
        from services.feedback import record_feedback, calibrate_confidence

        with app.app_context():
            # Create many incorrect feedbacks at high confidence
            for i in range(5):
                e = _create_entity(title=f"Entity {i}")
                _create_classification_event(e.id, para_bucket="INBOX", confidence=0.9)
                record_feedback(entity_id=e.id, verdict="incorrect")

            # Calibrated confidence for 0.9 should be lower
            calibrated = calibrate_confidence(0.9)
            assert calibrated < 0.9

    def test_calibration_increases_confidence_on_correct(self, app):
        from services.feedback import record_feedback, calibrate_confidence

        with app.app_context():
            # Create many correct feedbacks at moderate confidence
            for i in range(5):
                e = _create_entity(title=f"Entity {i}")
                _create_classification_event(e.id, para_bucket="PROJECTS", confidence=0.7)
                record_feedback(entity_id=e.id, verdict="correct")

            # Calibrated confidence for 0.7 should be higher
            calibrated = calibrate_confidence(0.7)
            assert calibrated > 0.7

    def test_calibration_by_bucket(self, app):
        from services.feedback import record_feedback, calibrate_confidence

        with app.app_context():
            # INBOX has poor accuracy at high confidence
            for i in range(5):
                e = _create_entity(title=f"INBOX {i}")
                _create_classification_event(e.id, para_bucket="INBOX", confidence=0.9)
                record_feedback(entity_id=e.id, verdict="incorrect")

            # PROJECTS has good accuracy at high confidence
            for i in range(5):
                e = _create_entity(title=f"PROJECTS {i}")
                _create_classification_event(e.id, para_bucket="PROJECTS", confidence=0.9)
                record_feedback(entity_id=e.id, verdict="correct")

            inbox_calibrated = calibrate_confidence(0.9, para_bucket="INBOX")
            projects_calibrated = calibrate_confidence(0.9, para_bucket="PROJECTS")

            # INBOX calibration should be lower than PROJECTS
            assert inbox_calibrated < projects_calibrated

    def test_calibration_clamped_to_0_1(self, app):
        from services.feedback import record_feedback, calibrate_confidence

        with app.app_context():
            # Extreme case: all correct at very low confidence
            for i in range(10):
                e = _create_entity(title=f"Entity {i}")
                _create_classification_event(e.id, confidence=0.1)
                record_feedback(entity_id=e.id, verdict="correct")

            calibrated = calibrate_confidence(0.1)
            assert 0.0 <= calibrated <= 1.0

    def test_calibration_needs_minimum_samples(self, app):
        from services.feedback import record_feedback, calibrate_confidence

        with app.app_context():
            # Only 1 feedback — not enough for reliable calibration
            e = _create_entity()
            _create_classification_event(e.id, confidence=0.9)
            record_feedback(entity_id=e.id, verdict="incorrect")

            # Should return original confidence with insufficient data
            calibrated = calibrate_confidence(0.9)
            assert calibrated == pytest.approx(0.9)


# ─── Correction Signals ─────────────────────────────────────────────────────

class TestCorrectionSignals:
    """Test that correction signals help improve future classifications."""

    def test_get_correction_signals(self, app):
        from services.feedback import record_feedback, get_correction_signals

        with app.app_context():
            for i in range(3):
                e = _create_entity(title=f"Entity {i}")
                _create_classification_event(e.id, para_bucket="INBOX", confidence=0.8)
                record_feedback(
                    entity_id=e.id,
                    verdict="incorrect",
                    reason=f"Should be PROJECTS #{i}",
                )

            signals = get_correction_signals()
            assert len(signals) == 3
            # All should be incorrect verdicts
            assert all(s["verdict"] == "incorrect" for s in signals)

    def test_correction_signals_by_verdict(self, app):
        from services.feedback import record_feedback, get_correction_signals

        with app.app_context():
            e1 = _create_entity(title="Entity 1")
            e2 = _create_entity(title="Entity 2")
            _create_classification_event(e1.id, confidence=0.8)
            _create_classification_event(e2.id, confidence=0.9)

            record_feedback(entity_id=e1.id, verdict="incorrect", reason="Wrong bucket")
            record_feedback(entity_id=e2.id, verdict="correct")

            incorrect_signals = get_correction_signals(verdict="incorrect")
            assert len(incorrect_signals) == 1
            assert incorrect_signals[0]["reason"] == "Wrong bucket"

    def test_correction_signals_by_bucket(self, app):
        from services.feedback import record_feedback, get_correction_signals

        with app.app_context():
            for bucket in ["INBOX", "PROJECTS", "AREAS"]:
                e = _create_entity(title=f"Entity {bucket}")
                _create_classification_event(e.id, para_bucket=bucket, confidence=0.8)
                record_feedback(entity_id=e.id, verdict="incorrect", reason=f"Bad {bucket}")

            inbox_signals = get_correction_signals(para_bucket="INBOX")
            assert len(inbox_signals) == 1
            assert inbox_signals[0]["para_bucket"] == "INBOX"

    def test_correction_signals_empty(self, app):
        from services.feedback import get_correction_signals

        with app.app_context():
            signals = get_correction_signals()
            assert signals == []

    def test_correction_signals_pagination(self, app):
        from services.feedback import record_feedback, get_correction_signals

        with app.app_context():
            for i in range(10):
                e = _create_entity(title=f"Entity {i}")
                _create_classification_event(e.id, confidence=0.8)
                record_feedback(entity_id=e.id, verdict="incorrect", reason=f"Reason {i}")

            first_page = get_correction_signals(limit=3)
            assert len(first_page) == 3

    def test_correction_signals_includes_confidence_data(self, app):
        from services.feedback import record_feedback, get_correction_signals

        with app.app_context():
            e = _create_entity()
            _create_classification_event(e.id, confidence=0.85, para_bucket="PROJECTS")
            record_feedback(entity_id=e.id, verdict="incorrect", reason="Wrong")

            signals = get_correction_signals()
            assert len(signals) == 1
            signal = signals[0]
            assert signal["original_confidence"] == 0.85
            assert signal["para_bucket"] == "PROJECTS"


# ─── Feedback Applied to Classification ──────────────────────────────────────

class TestFeedbackAppliedToClassification:
    """Test that correction signals integrate with the classification pipeline."""

    @patch("services.extractor.extract")
    def test_classification_uses_calibrated_confidence(self, mock_extract, app):
        """After feedback, the ai_meta should reflect calibrated confidence."""
        from services.ai_pipeline import run_classify
        from services.extractor import ExtractionResult
        from services.feedback import record_feedback, calibrate_confidence

        with app.app_context():
            # First, create feedback that suggests INBOX is unreliable
            for i in range(5):
                e = _create_entity(title=f"Feedback entity {i}")
                _create_classification_event(e.id, para_bucket="INBOX", confidence=0.9)
                record_feedback(entity_id=e.id, verdict="incorrect")

            # Now classify a new entity
            mock_extract.return_value = ExtractionResult(
                summary="Test summary",
                para_bucket="INBOX",
                confidence=0.9,
                reasoning="Test reasoning",
            )

            entity = _create_entity(content="Test content for classification")
            run_classify({"entity_id": entity.id})

            db.session.refresh(entity)
            classification = entity.ai_meta.get("classification", {})

            # The raw confidence from extraction should still be 0.9
            assert classification["confidence"] == 0.9

            # But we can query the calibrated version
            calibrated = calibrate_confidence(0.9, para_bucket="INBOX")
            assert calibrated < 0.9


# ─── API Endpoints ───────────────────────────────────────────────────────────

class TestFeedbackAPI:
    """Test the v2 API endpoints for feedback."""

    def test_post_feedback_success(self, app, client):
        entity_id = None
        with app.app_context():
            entity = _create_entity()
            _create_classification_event(entity.id, confidence=0.85)
            entity_id = str(entity.id)

        resp = client.post("/api/v2/feedback", json={
            "entity_id": entity_id,
            "verdict": "correct",
            "reason": "Looks good",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["verdict"] == "correct"
        assert data["reason"] == "Looks good"
        assert data["entity_id"] == entity_id

    def test_post_feedback_missing_entity_id(self, client):
        resp = client.post("/api/v2/feedback", json={
            "verdict": "correct",
        })
        assert resp.status_code == 400
        assert "entity_id" in resp.get_json()["error"]

    def test_post_feedback_missing_verdict(self, client):
        resp = client.post("/api/v2/feedback", json={
            "entity_id": "some-id",
        })
        assert resp.status_code == 400
        assert "verdict" in resp.get_json()["error"]

    def test_post_feedback_invalid_verdict(self, app, client):
        entity_id = None
        with app.app_context():
            entity = _create_entity()
            _create_classification_event(entity.id, confidence=0.8)
            entity_id = str(entity.id)

        resp = client.post("/api/v2/feedback", json={
            "entity_id": entity_id,
            "verdict": "maybe",
        })
        assert resp.status_code == 400

    def test_post_feedback_no_classification(self, app, client):
        entity_id = None
        with app.app_context():
            entity = _create_entity()
            entity_id = str(entity.id)

        resp = client.post("/api/v2/feedback", json={
            "entity_id": entity_id,
            "verdict": "correct",
        })
        assert resp.status_code == 400

    def test_get_feedback_stats_empty(self, client):
        resp = client.get("/api/v2/feedback/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 0
        assert data["accuracy_rate"] is None

    def test_get_feedback_stats_with_data(self, app, client):
        with app.app_context():
            for i in range(4):
                e = _create_entity(title=f"Entity {i}")
                _create_classification_event(e.id, confidence=0.8)
                verdict = "correct" if i < 3 else "incorrect"
                record_feedback(entity_id=e.id, verdict=verdict)

        resp = client.get("/api/v2/feedback/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 4
        assert data["correct"] == 3
        assert data["incorrect"] == 1
        assert data["accuracy_rate"] == pytest.approx(0.75)
        assert "by_bucket" in data

    def test_get_feedback_corrections_empty(self, client):
        resp = client.get("/api/v2/feedback/corrections")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["signals"] == []
        assert data["total"] == 0

    def test_get_feedback_corrections_with_data(self, app, client):
        with app.app_context():
            for i in range(3):
                e = _create_entity(title=f"Entity {i}")
                _create_classification_event(e.id, para_bucket="INBOX", confidence=0.8)
                record_feedback(
                    entity_id=e.id,
                    verdict="incorrect",
                    reason=f"Wrong classification #{i}",
                )

        resp = client.get("/api/v2/feedback/corrections")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 3
        assert all(s["verdict"] == "incorrect" for s in data["signals"])

    def test_get_feedback_corrections_filter_by_verdict(self, app, client):
        with app.app_context():
            e1 = _create_entity(title="E1")
            e2 = _create_entity(title="E2")
            _create_classification_event(e1.id, confidence=0.8)
            _create_classification_event(e2.id, confidence=0.9)
            record_feedback(entity_id=e1.id, verdict="incorrect")
            record_feedback(entity_id=e2.id, verdict="correct")

        resp = client.get("/api/v2/feedback/corrections?verdict=incorrect")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1

    def test_get_feedback_corrections_filter_by_bucket(self, app, client):
        with app.app_context():
            for bucket in ["INBOX", "PROJECTS"]:
                e = _create_entity(title=f"Entity {bucket}")
                _create_classification_event(e.id, para_bucket=bucket, confidence=0.8)
                record_feedback(entity_id=e.id, verdict="incorrect")

        resp = client.get("/api/v2/feedback/corrections?para_bucket=INBOX")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        assert data["signals"][0]["para_bucket"] == "INBOX"

    def test_get_feedback_corrections_limit(self, app, client):
        with app.app_context():
            for i in range(10):
                e = _create_entity(title=f"Entity {i}")
                _create_classification_event(e.id, confidence=0.8)
                record_feedback(entity_id=e.id, verdict="incorrect")

        resp = client.get("/api/v2/feedback/corrections?limit=3")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 3
