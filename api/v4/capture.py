"""Engram v4 capture API."""

from api import api_v4_bp
from api import v4_entities as _v4e
from api.v4._shared import *

@api_v4_bp.route("/capture", methods=["POST"])
def capture():
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return _error("content is required")

    user_title = (data.get("title") or "").strip() or None
    existing = _find_duplicate_capture_note(content)
    if existing is not None:
        return jsonify({
            "source_note": existing.to_dict(),
            "applied_changes": [],
            "suggestions": [],
            "warnings": [],
            "skipped": True,
            "reason": "exact duplicate",
        })

    stream = request.args.get("stream", "").lower() == "true"
    if stream:
        return Response(
            stream_with_context(_capture_sse_stream(data, content, user_title)),
            mimetype="text/event-stream",
            status=200,
        )

    note = _create_capture_note(data, content, user_title)
    thread_id = _capture_thread_id_from_data(data)
    applied_changes, suggestions, warnings, report_id = _run_capture_extraction(
        note,
        content,
        data.get("mode") or "auto",
        thread_id=thread_id,
    )
    db.session.commit()
    return jsonify(_capture_result_payload(note, applied_changes, suggestions, warnings, report_id=report_id)), 201


def _capture_sse_stream(data, content, user_title):
    try:
        note = _create_capture_note(data, content, user_title)
        thread_id = _capture_thread_id_from_data(data)
        yield _format_capture_sse_event(
            "reading",
            {"note_id": note.id, "title": note.title, "content_length": len(content)},
        )

        applied_changes = []
        suggestions = []
        warnings = []
        report_id = None
        applied_changes.extend(_apply_explicit_mentions(note, content))

        mode = data.get("mode") or "auto"
        yield _format_capture_sse_event("extracting", {"mode": mode})

        extraction = {}
        try:
            extraction = _v4e._run_basic_capture_extraction(note, mode, thread_id=thread_id) or {}
        except Exception as exc:
            warnings.append(str(exc))
            note.ai_status = "failed"
            _apply_capture_intent(note, {})

        candidate_count = _count_extraction_candidates(extraction)
        yield _format_capture_sse_event("candidates", {"count": candidate_count})

        yield _format_capture_sse_event("reconciling", {"candidate_count": candidate_count})
        yield _format_capture_sse_event("applying", {"candidate_count": candidate_count})

        if not warnings:
            try:
                extraction_changes, extraction_suggestions, extraction_report_id = _process_capture_extraction(
                    note,
                    content,
                    extraction,
                    thread_id=thread_id,
                )
                applied_changes.extend(extraction_changes)
                suggestions.extend(extraction_suggestions)
                report_id = extraction_report_id
            except Exception as exc:
                warnings.append(str(exc))
                note.ai_status = "failed"
                _apply_capture_intent(note, {})

        link_count = sum(
            1 for change in applied_changes if change.get("type") == "relationship_added"
        )
        yield _format_capture_sse_event("linking", {"links_created": link_count})

        summarize_queued = _count_capture_summarize_jobs()
        yield _format_capture_sse_event("summarizing", {"queued": summarize_queued})

        db.session.commit()
        yield _format_capture_sse_event(
            "done",
            _capture_result_payload(note, applied_changes, suggestions, warnings, report_id=report_id),
        )
    except Exception as exc:
        db.session.rollback()
        yield _format_capture_sse_event("error", {"message": str(exc)})


def _run_capture_extraction(note, content, mode, thread_id=None):
    applied_changes = []
    suggestions = []
    warnings = []
    report_id = None
    applied_changes.extend(_apply_explicit_mentions(note, content))
    try:
        result = _v4e._run_basic_capture_extraction(note, mode, thread_id=thread_id)
        extraction_changes, extraction_suggestions, extraction_report_id = _process_capture_extraction(
            note,
            content,
            result or {},
            thread_id=thread_id,
        )
        applied_changes.extend(extraction_changes)
        suggestions.extend(extraction_suggestions)
        report_id = extraction_report_id
    except Exception as exc:
        warnings.append(str(exc))
        note.ai_status = "failed"
        _apply_capture_intent(note, {})
    return applied_changes, suggestions, warnings, report_id


@api_v4_bp.route("/entities/<entity_id>/ingest_candidates", methods=["POST"])
def ingest_candidates(entity_id):
    """Accept pre-extracted candidates from a calling agent, bypassing LLM extraction."""
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    if entity.type not in ENTITY_TYPES:
        return _error(f"unsupported entity type: {entity.type}")

    from services.v4_extraction import normalize_candidates
    extraction = normalize_candidates(request.get_json(silent=True) or {})
    _clear_review_resolution(entity)

    thread_id = entity.id if entity.type in THREAD_INGEST_SOURCE_TYPES else None
    try:
        applied_changes, suggestions, report_id = _reconcile_capture_candidates(
            entity, extraction, thread_id=thread_id
        )
    except Exception as exc:
        db.session.rollback()
        return _error(f"reconciliation failed: {exc}", 500)

    db.session.commit()
    entity_dict = _load_entity(entity.id).to_dict()
    return jsonify({
        "source_entity": entity_dict,
        "source_note": entity_dict,
        "applied_changes": applied_changes,
        "suggestions": suggestions,
        "warnings": [],
        "report_id": report_id,
    })


@api_v4_bp.route("/entities/<entity_id>/reprocess", methods=["POST"])
def reprocess_entity(entity_id):
    entity = _load_entity(entity_id)
    if entity is None:
        return _error("entity not found", 404)
    if entity.type != "note":
        return _error("reprocess is only supported for notes")

    pending = AiSuggestion.query.filter_by(
        source_entity_id=entity_id, status="pending"
    ).all()
    for s in pending:
        s.status = "dismissed"
        s.resolved_at = datetime.utcnow()
    db.session.flush()

    # Reset AI status so reconciliation's normal pending→done transition fires
    # cleanly. (Without this, an entity in `done` would stay `done` even if the
    # reprocess pass set no summary, which would still be fine, but resetting
    # makes the lifecycle explicit.)
    entity.ai_status = "pending"
    _clear_review_resolution(entity)

    applied_changes = []
    suggestions = []
    report_id = None
    try:
        result = _v4e._run_basic_capture_extraction(entity, "auto")
        applied_changes, suggestions, report_id = _reconcile_capture_candidates(entity, result or {})
    except Exception as exc:
        entity.ai_status = "failed"
        db.session.commit()
        return _error(f"extraction failed: {exc}", 500)

    db.session.commit()
    return jsonify({"applied_changes": applied_changes, "suggestions": suggestions, "report_id": report_id})


