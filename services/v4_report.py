"""v4 distillation report assembler.

One capture → one report. The assembler runs in the job worker after
reconciliation has finished creating suggestions. It groups all candidates
from a single capture into ordered sections and links every suggestion to
the report row via ``ai_suggestions.report_id``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from extensions import db
from models import AiSuggestion, DistillationReport, Entity, EntityEvent, Job
from services.job_worker import register_handler

logger = logging.getLogger(__name__)

SECTION_ORDER = [
    ("routing_summary", "Routing summary"),
    ("applied_annotations", "Applied annotations"),
    ("proposed_commitments", "Proposed commitments"),
    ("decisions", "Decisions"),
    ("questions", "Open questions"),
    ("leftovers", "Leftovers"),
]

APPLIED_EVENT_TYPES = {
    "tag_added",
    "relationship_added",
    "ai_updated",
    "ai_processed",
}


def _getattr(obj: Any, name: str, default: Any = None) -> Any:
    """Return attribute or dict key, whichever is available."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _find_text_offset(needle: str | None, haystack: str | None) -> dict:
    """Return a receipt pointing to the first occurrence of ``needle`` in note content."""
    needle = (needle or "").strip()
    haystack = haystack or ""
    if not needle:
        return {"start": -1, "length": 0, "quote": None}
    start = haystack.lower().find(needle.lower())
    if start == -1:
        return {"start": -1, "length": 0, "quote": None}
    return {"start": start, "length": len(needle), "quote": needle}


def _receipt_from_suggestion(suggestion: Any, note_content: str | None) -> dict:
    payload = _getattr(suggestion, "payload") or {}
    evidence = ""
    if isinstance(payload, dict):
        evidence = payload.get("evidence") or payload.get("title") or ""
    evidence = evidence or _getattr(suggestion, "reason") or ""
    return _find_text_offset(evidence, note_content)


def _title_from_suggestion(suggestion: Any) -> str | None:
    payload = _getattr(suggestion, "payload") or {}
    if isinstance(payload, dict):
        return payload.get("title") or payload.get("statement") or _getattr(suggestion, "reason")
    return _getattr(suggestion, "reason")


def _suggestion_item(suggestion: Any, note_content: str | None) -> dict:
    payload = _getattr(suggestion, "payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "id": _getattr(suggestion, "id"),
        "kind": _getattr(suggestion, "operation_type") or _getattr(suggestion, "suggestion_type"),
        "suggestion_type": _getattr(suggestion, "suggestion_type"),
        "operation_type": _getattr(suggestion, "operation_type"),
        "title": _title_from_suggestion(suggestion),
        "reason": _getattr(suggestion, "reason"),
        "confidence": _getattr(suggestion, "confidence"),
        "payload": payload,
        "receipt": _receipt_from_suggestion(suggestion, note_content),
    }


def _event_item(event: Any, note_content: str | None) -> dict:
    new_value = _getattr(event, "new_value") or {}
    if not isinstance(new_value, dict):
        new_value = {}

    event_type = _getattr(event, "event_type")
    title = None
    if event_type == "tag_added":
        title = f"Tag added: {new_value.get('tag', '')}"
    elif event_type == "relationship_added":
        rel = new_value.get("relationship_type") or "related"
        target_title = new_value.get("target_title") or new_value.get("title") or "entity"
        title = f"Linked ({rel}): {target_title}"
    elif event_type == "ai_updated":
        title = f"Updated: {', '.join(str(k) for k in new_value.keys())}"
    elif event_type == "ai_processed":
        title = "Summary generated"

    reason = _getattr(event, "reason") or ""
    return {
        "id": _getattr(event, "id"),
        "kind": event_type,
        "event_id": _getattr(event, "id"),
        "entity_id": _getattr(event, "entity_id"),
        "title": title,
        "reason": reason,
        "confidence": _getattr(event, "confidence"),
        "receipt": _find_text_offset(reason or title, note_content),
    }


def _is_commitment_candidate(suggestion: Any) -> bool:
    op = _getattr(suggestion, "operation_type")
    st = _getattr(suggestion, "suggestion_type")
    payload = _getattr(suggestion, "payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    if op == "create_decision":
        return False
    if st == "create_task":
        return True
    if op in {"create_entity", "create_new_entity"} and payload.get("type") == "task":
        return True
    return False


def _has_owner(suggestion: Any) -> bool:
    payload = _getattr(suggestion, "payload") or {}
    if isinstance(payload, dict):
        return bool(payload.get("assigned_to"))
    return False


def build_report(
    source_note: Any,
    applied_events: list[Any],
    suggestions: list[Any],
) -> dict:
    """Build the narrative for a capture without touching the database.

    ``source_note`` may be an ``Entity`` instance or a dict with ``id``,
    ``content``, and ``ai_meta``. ``applied_events`` and ``suggestions`` may
    be model instances or dicts.
    """
    note_content = _getattr(source_note, "content") or ""
    ai_meta = _getattr(source_note, "ai_meta") or {}
    if not isinstance(ai_meta, dict):
        ai_meta = {}

    routing_item = {
        "kind": "routing_summary",
        "note_id": _getattr(source_note, "id"),
        "title": _getattr(source_note, "title"),
        "intent": ai_meta.get("intent"),
        "candidate_count": len(suggestions),
        "receipt": {"start": 0, "length": len(note_content), "quote": note_content[:200]},
    }

    applied_items = [_event_item(event, note_content) for event in applied_events]
    commitment_items: list[dict] = []
    decision_items: list[dict] = []
    question_items: list[dict] = []
    leftover_items: list[dict] = []

    for suggestion in suggestions:
        op = _getattr(suggestion, "operation_type")

        if op == "create_decision":
            decision_items.append(_suggestion_item(suggestion, note_content))
            continue

        if _is_commitment_candidate(suggestion):
            if _has_owner(suggestion):
                commitment_items.append(_suggestion_item(suggestion, note_content))
            else:
                item = _suggestion_item(suggestion, note_content)
                item["kind"] = "attribution"
                item["question"] = "Who committed to this?"
                item["owner"] = None
                question_items.append(item)
            continue

        if op == "update_unresolved":
            item = _suggestion_item(suggestion, note_content)
            item["kind"] = "unresolved_update"
            question_items.append(item)
            continue

        leftover_items.append(_suggestion_item(suggestion, note_content))

    section_items = {
        "routing_summary": [routing_item],
        "applied_annotations": applied_items,
        "proposed_commitments": commitment_items,
        "decisions": decision_items,
        "questions": question_items,
        "leftovers": leftover_items,
    }

    sections = [
        {"name": name, "title": title, "items": section_items[name]}
        for name, title in SECTION_ORDER
    ]

    stats = {
        "total": len(suggestions),
        "applied": len(applied_items),
        "proposed": len(commitment_items),
        "decisions": len(decision_items),
        "questions": len(question_items),
        "leftovers": len(leftover_items),
    }

    return {
        "source_note_id": _getattr(source_note, "id"),
        "sections": sections,
        "stats": stats,
    }


def supersede_prior_reports(source_note_id: str, new_report_id: str | None) -> None:
    """Mark earlier reports for this note superseded and expire their pending items."""
    query = DistillationReport.query.filter(
        DistillationReport.source_note_id == source_note_id,
        DistillationReport.status.in_(["pending", "partial", "reviewed"]),
    )
    if new_report_id:
        query = query.filter(DistillationReport.id != new_report_id)
    prior_reports = query.with_for_update().all()

    now = datetime.now(timezone.utc)
    for report in prior_reports:
        report.status = "superseded"
        report.reviewed_at = now

    prior_ids = [r.id for r in prior_reports]
    if prior_ids:
        stale = (
            AiSuggestion.query.filter(
                AiSuggestion.report_id.in_(prior_ids),
                AiSuggestion.status == "pending",
            )
            .with_for_update()
            .all()
        )
        for suggestion in stale:
            suggestion.status = "expired"
            suggestion.resolved_at = now


def assemble_report_for_note(source_note_id: str) -> DistillationReport | None:
    """Group all current candidates from one capture into a single report.

    Creates the report, links suggestions, and supersedes any prior report for
    the same capture. Prior pending suggestions are expired before the new
    report is built so the report only contains fresh candidates.
    """
    note = db.session.get(Entity, source_note_id)
    if note is None:
        logger.warning("assemble_report: note %s not found", source_note_id)
        return None

    supersede_prior_reports(source_note_id, None)

    suggestions = (
        AiSuggestion.query.filter_by(
            source_entity_id=source_note_id,
            status="pending",
        )
        .order_by(AiSuggestion.created_at.asc())
        .all()
    )

    applied_events = (
        EntityEvent.query.filter(
            EntityEvent.source_note_id == source_note_id,
            EntityEvent.event_type.in_(APPLIED_EVENT_TYPES),
            EntityEvent.actor.like("agent:%"),
        )
        .order_by(EntityEvent.created_at.asc())
        .all()
    )

    if not suggestions and not applied_events:
        logger.info("assemble_report: no candidates for note %s", source_note_id)
        return None

    narrative = build_report(note, applied_events, suggestions)

    report = DistillationReport(
        source_note_id=source_note_id,
        status="pending",
        narrative=narrative,
        stats=narrative.get("stats") or {},
    )
    db.session.add(report)
    db.session.flush()

    for suggestion in suggestions:
        suggestion.report_id = report.id

    db.session.commit()
    logger.info(
        "Assembled report %s for note %s with %d suggestions",
        report.id,
        source_note_id,
        len(suggestions),
    )
    return report


def queue_assemble_report_job(source_note_id: str) -> None:
    """Enqueue a report-assembly job, skipping duplicates."""
    already_queued = (
        db.session.query(Job)
        .filter(
            Job.job_type == "assemble_report",
            Job.entity_id == source_note_id,
            Job.status.in_(["pending", "running"]),
        )
        .first()
    )
    if already_queued:
        return

    db.session.add(
        Job(
            job_type="assemble_report",
            entity_id=source_note_id,
            payload={"source_note_id": source_note_id},
        )
    )


@register_handler("assemble_report")
def handle_assemble_report(payload: dict) -> None:
    source_note_id = (payload or {}).get("source_note_id")
    if not source_note_id:
        raise ValueError("assemble_report job payload missing source_note_id")
    assemble_report_for_note(source_note_id)
