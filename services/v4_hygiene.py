"""Nightly hygiene job: keep the world model healthy without anyone remembering.

Three guards, one self-re-enqueueing job:
  1. Backfill embedding chunks for active entities that have none — chunkless
     entities are invisible to the duplicate reconciler (this blindness is how
     prod accumulated duplicate project clusters).
  2. Expire pending AI suggestions older than SUGGESTION_MAX_AGE_DAYS — a
     stale review queue is noise that erodes trust.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from services.job_worker import register_handler

logger = logging.getLogger(__name__)

SUGGESTION_MAX_AGE_DAYS = 14
HYGIENE_INTERVAL_HOURS = 24
HYGIENE_JOB_TYPE = "hygiene"


def run_hygiene():
    """Execute one hygiene pass. Returns a summary dict."""
    from extensions import db
    from models import AiSuggestion, Entity
    from services.embeddings import backfill_embeddings

    summary = {"embedded": 0, "expired_suggestions": 0}

    try:
        summary["embedded"] = backfill_embeddings()
    except Exception as exc:
        logger.error("hygiene embedding backfill failed: %s", exc)

    cutoff = datetime.now(timezone.utc) - timedelta(days=SUGGESTION_MAX_AGE_DAYS)
    stale = AiSuggestion.query.filter(
        AiSuggestion.status == "pending",
        AiSuggestion.created_at < cutoff,
    ).all()
    for suggestion in stale:
        suggestion.status = "expired"
        suggestion.resolved_at = datetime.now(timezone.utc)
        source = db.session.get(Entity, suggestion.source_entity_id)
        if source is not None:
            from models import EntityEvent
            db.session.add(EntityEvent(
                entity_id=source.id,
                event_type="suggestion_expired",
                actor="agent:v4-hygiene",
                new_value={"suggestion_id": suggestion.id, "age_days": SUGGESTION_MAX_AGE_DAYS},
                reason=f"pending longer than {SUGGESTION_MAX_AGE_DAYS} days",
            ))
    summary["expired_suggestions"] = len(stale)
    db.session.commit()

    logger.info("hygiene pass: %s", summary)
    return summary


def schedule_next_hygiene(hours=HYGIENE_INTERVAL_HOURS):
    """Enqueue the next hygiene run if none is pending (idempotent)."""
    from extensions import db
    from models import Job

    existing = Job.query.filter_by(job_type=HYGIENE_JOB_TYPE, status="pending").first()
    if existing is not None:
        return existing

    job = Job(
        job_type=HYGIENE_JOB_TYPE,
        payload={"scheduled": True},
        run_after=datetime.now(timezone.utc) + timedelta(hours=hours),
    )
    db.session.add(job)
    db.session.commit()
    return job


@register_handler(HYGIENE_JOB_TYPE)
def handle_hygiene_job(payload):
    """Run the pass, then re-enqueue tomorrow's."""
    try:
        run_hygiene()
    finally:
        schedule_next_hygiene()


def ensure_hygiene_scheduled(app):
    """Bootstrap: make sure a hygiene job exists (called at app startup).

    First run lands shortly after boot rather than a day later so a fresh
    deploy gets coverage immediately; subsequent runs self-schedule daily.
    """
    from extensions import db
    from models import Job

    with app.app_context():
        existing = Job.query.filter_by(job_type=HYGIENE_JOB_TYPE, status="pending").first()
        if existing is not None:
            return
        job = Job(
            job_type=HYGIENE_JOB_TYPE,
            payload={"scheduled": True, "bootstrap": True},
            run_after=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db.session.add(job)
        db.session.commit()
        logger.info("hygiene job bootstrapped (first run in 5 minutes)")
