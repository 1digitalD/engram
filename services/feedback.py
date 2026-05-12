"""Feedback service — confidence calibration + correction signals.

Provides:
- record_feedback: Users mark AI classifications as correct/incorrect
- get_feedback: Query stored feedback records
- get_accuracy_stats: Compute accuracy metrics overall and by bucket
- calibrate_confidence: Adjust confidence based on feedback history
- get_correction_signals: Extract patterns from incorrect classifications

All feedback is stored as entity_events with event_type='ai_correction'.
"""

import logging
from collections import defaultdict

from extensions import db
from models import EntityEvent

logger = logging.getLogger(__name__)

VALID_VERDICTS = {"correct", "incorrect"}
MIN_SAMPLES_FOR_CALIBRATION = 3  # Minimum feedback records needed for calibration
CONFIDENCE_BIN_WIDTH = 0.2  # Confidence ranges: 0.0-0.2, 0.2-0.4, etc.


def record_feedback(entity_id, verdict, reason=None):
    """Record user feedback on an AI classification.

    Args:
        entity_id: UUID of the entity whose classification is being judged.
        verdict: 'correct' or 'incorrect'.
        reason: Optional explanation from the user.

    Returns:
        The created EntityEvent record.

    Raises:
        ValueError: If verdict is invalid or no classification exists.
    """
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"Invalid verdict '{verdict}'. Must be one of: {VALID_VERDICTS}")

    # Find the most recent ai_classified event for this entity
    classification = (
        EntityEvent.query.filter_by(
            entity_id=entity_id,
            event_type="ai_classified",
        )
        .order_by(EntityEvent.created_at.desc())
        .first()
    )

    if classification is None:
        raise ValueError(
            f"No AI classification found for entity {entity_id}. "
            "Cannot record feedback without a prior classification."
        )

    # Extract classification metadata
    new_value = classification.new_value or {}
    original_confidence = classification.confidence
    para_bucket = new_value.get("para_bucket")

    # Create the correction event
    feedback = EntityEvent(
        entity_id=entity_id,
        event_type="ai_correction",
        actor="user",
        old_value={
            "classification_id": classification.id,
        },
        new_value={
            "verdict": verdict,
            "reason": reason,
            "original_confidence": original_confidence,
            "para_bucket": para_bucket,
        },
        confidence=original_confidence,
        reason=reason,
    )

    db.session.add(feedback)
    db.session.commit()

    logger.info(
        "Feedback recorded for entity %s: verdict=%s confidence=%.2f",
        entity_id,
        verdict,
        original_confidence,
    )

    return feedback


def get_feedback(entity_id=None, verdict=None, limit=50, offset=0):
    """Query stored feedback records.

    Args:
        entity_id: Filter by specific entity.
        verdict: Filter by 'correct' or 'incorrect'.
        limit: Maximum number of results.
        offset: Number of results to skip.

    Returns:
        List of EntityEvent records (newest first).
    """
    query = EntityEvent.query.filter_by(event_type="ai_correction")

    if entity_id:
        query = query.filter_by(entity_id=entity_id)

    if verdict:
        # Filter by verdict stored in new_value JSON
        query = query.filter(EntityEvent.new_value["verdict"].as_string() == verdict)

    results = (
        query.order_by(EntityEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return results


def get_accuracy_stats():
    """Compute accuracy statistics from feedback.

    Returns:
        Dict with:
        - total: Total feedback count
        - correct: Number of correct verdicts
        - incorrect: Number of incorrect verdicts
        - accuracy_rate: correct / total (None if no feedback)
        - by_bucket: Accuracy breakdown by PARA bucket
    """
    all_feedback = get_feedback(limit=10000)

    total = len(all_feedback)
    if total == 0:
        return {
            "total": 0,
            "correct": 0,
            "incorrect": 0,
            "accuracy_rate": None,
            "by_bucket": {},
        }

    correct = sum(
        1 for f in all_feedback
        if (f.new_value or {}).get("verdict") == "correct"
    )
    incorrect = total - correct

    # Breakdown by PARA bucket
    bucket_stats = defaultdict(lambda: {"correct": 0, "total": 0})
    for f in all_feedback:
        nv = f.new_value or {}
        bucket = nv.get("para_bucket", "UNKNOWN")
        bucket_stats[bucket]["total"] += 1
        if nv.get("verdict") == "correct":
            bucket_stats[bucket]["correct"] += 1

    by_bucket = {}
    for bucket, stats in bucket_stats.items():
        by_bucket[bucket] = {
            "correct": stats["correct"],
            "total": stats["total"],
            "accuracy_rate": stats["correct"] / stats["total"] if stats["total"] > 0 else None,
        }

    return {
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "accuracy_rate": correct / total if total > 0 else None,
        "by_bucket": by_bucket,
    }


def _confidence_bin(confidence):
    """Map a confidence value to a bin label for grouping."""
    bin_index = int(confidence / CONFIDENCE_BIN_WIDTH)
    bin_index = max(0, min(bin_index, 4))  # Clamp to 0-4
    lower = bin_index * CONFIDENCE_BIN_WIDTH
    upper = (bin_index + 1) * CONFIDENCE_BIN_WIDTH
    return f"{lower:.1f}-{upper:.1f}"


def calibrate_confidence(original_confidence, para_bucket=None):
    """Calibrate a confidence score based on historical feedback.

    Uses accuracy rates from feedback history to adjust the raw confidence:
    - If feedback shows the system is overconfident in this range, reduce it.
    - If feedback shows the system is underconfident, increase it.
    - Returns original confidence if insufficient feedback data.

    Args:
        original_confidence: The raw confidence score from the classifier (0.0-1.0).
        para_bucket: Optional PARA bucket to filter feedback by.

    Returns:
        Calibrated confidence score (0.0-1.0).
    """
    all_feedback = get_feedback(limit=10000)

    if not all_feedback:
        return original_confidence

    # Filter to relevant feedback
    relevant = []
    for f in all_feedback:
        nv = f.new_value or {}
        if para_bucket and nv.get("para_bucket") != para_bucket:
            continue
        # Match by confidence bin
        fb_confidence = nv.get("original_confidence")
        if fb_confidence is not None:
            if _confidence_bin(fb_confidence) == _confidence_bin(original_confidence):
                relevant.append(f)

    if len(relevant) < MIN_SAMPLES_FOR_CALIBRATION:
        # Not enough data for reliable calibration
        return original_confidence

    # Compute accuracy rate in this confidence bin
    correct = sum(
        1 for f in relevant
        if (f.new_value or {}).get("verdict") == "correct"
    )
    accuracy_rate = correct / len(relevant)

    # Calibrate: blend original with accuracy-based adjustment
    # The idea: if accuracy_rate < original_confidence, the system is overconfident
    # If accuracy_rate > original_confidence, the system is underconfident
    # We pull the confidence toward the observed accuracy rate
    calibration_weight = min(len(relevant) / 20.0, 1.0)  # More data = more weight
    calibrated = (
        original_confidence * (1 - calibration_weight)
        + accuracy_rate * calibration_weight
    )

    # Clamp to [0, 1]
    return max(0.0, min(1.0, calibrated))


def get_correction_signals(verdict=None, para_bucket=None, limit=20):
    """Extract correction signals from feedback to improve future classifications.

    Returns detailed information about incorrect classifications so the system
    can learn patterns and adjust behavior.

    Args:
        verdict: Filter by 'correct' or 'incorrect'. Defaults to 'incorrect'.
        para_bucket: Filter by PARA bucket.
        limit: Maximum number of signals to return.

    Returns:
        List of dicts with correction signal data.
    """
    query = EntityEvent.query.filter_by(event_type="ai_correction")

    if verdict:
        query = query.filter(EntityEvent.new_value["verdict"].as_string() == verdict)
    else:
        # Default: show incorrect feedback (most actionable)
        query = query.filter(EntityEvent.new_value["verdict"].as_string() == "incorrect")

    if para_bucket:
        query = query.filter(EntityEvent.new_value["para_bucket"].as_string() == para_bucket)

    events = (
        query.order_by(EntityEvent.created_at.desc())
        .limit(limit)
        .all()
    )

    signals = []
    for event in events:
        nv = event.new_value or {}
        signals.append({
            "entity_id": event.entity_id,
            "verdict": nv.get("verdict"),
            "reason": nv.get("reason"),
            "original_confidence": nv.get("original_confidence"),
            "para_bucket": nv.get("para_bucket"),
            "created_at": event.created_at.isoformat() if event.created_at else None,
        })

    return signals
