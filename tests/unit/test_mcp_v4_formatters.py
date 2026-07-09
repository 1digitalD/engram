from mcp_server.v4_formatters import (
    format_capture_result,
    format_entity,
    format_marker,
    format_nudge_draft,
    format_recent,
    format_report_detail,
    format_reports_list,
    format_resolve_report,
    format_search_results,
    format_workboard,
)


def test_format_search_results_uses_v4_payload():
    text = format_search_results(
        {
            "results": [{
                "entity": {"id": "p1", "type": "project", "title": "Memory Lookup"},
                "score": 0.91,
                "match": {"source": "keyword", "snippet": "rollout"},
            }]
        },
        "memory",
    )

    assert "Memory Lookup" in text
    assert "score=0.910" in text
    assert "source=keyword" in text
    assert "rollout" in text


def test_format_entity_includes_relationship_sections():
    text = format_entity(
        {
            "entity": {"id": "t1", "type": "task", "title": "Follow up", "status": "open", "lifecycle": "active"},
            "sections": [{
                "title": "Project",
                "items": [{
                    "entity": {"id": "p1", "title": "Memory Lookup"},
                    "relationship": {"relationship_type": "parent"},
                }],
            }],
        }
    )

    assert "Task `t1`" in text
    assert "Relationships:" in text
    assert "Memory Lookup" in text
    assert "parent" in text


def test_format_recent_lists_entities():
    text = format_recent({"data": [{"id": "n1", "type": "note", "title": "Captured note"}]}, entity_type="note")

    assert "Recent note entities" in text
    assert "Captured note" in text


def test_format_search_results_shows_explicit_missing_title():
    text = format_search_results(
        {"results": [{"entity": {"id": "t1", "type": "task", "title": None}, "score": 0.5}]},
        "orphan",
    )

    assert "(no title)" in text
    assert "Untitled" not in text
    assert "`t1`" in text
    assert "[task]" in text


def test_format_entity_shows_explicit_missing_title():
    text = format_entity(
        {"entity": {"id": "p1", "type": "project", "title": None, "status": "active", "lifecycle": "active"}}
    )

    assert "Title: (no title)" in text
    assert "Untitled" not in text


def test_format_recent_shows_explicit_missing_title():
    text = format_recent({"data": [{"id": "n2", "type": "note", "title": None}]}, entity_type="note")

    assert "(no title)" in text
    assert "Untitled" not in text
    assert "`n2`" in text
    assert "[note]" in text


def test_format_capture_result_includes_report_id():
    text = format_capture_result({
        "source_note": {"id": "n1", "title": "Captured"},
        "applied_changes": [],
        "suggestions": [],
        "warnings": [],
        "report_id": "r1",
    })

    assert "Report `r1`" in text


def test_format_reports_list_shows_pending_reports():
    text = format_reports_list({
        "data": [{"id": "r1", "status": "pending", "source_note_id": "n1", "stats": {"suggestion_count": 3}}],
        "meta": {"total": 1},
    })

    assert "r1" in text
    assert "3 suggestion(s)" in text


def test_format_report_detail_includes_narrative_and_suggestions():
    text = format_report_detail({
        "data": {
            "id": "r1",
            "status": "pending",
            "source_note_id": "n1",
            "narrative": {"summary": "Meeting recap", "sections": [{"title": "Tasks"}]},
        },
        "source_note": {"title": "Standup"},
        "suggestions": [{"id": "s1", "operation_type": "create_task", "confidence": 0.9, "reason": "add task"}],
    })

    assert "Meeting recap" in text
    assert "create_task" in text


def test_format_resolve_report_summarizes_batch():
    text = format_resolve_report({
        "data": {"id": "r1", "status": "reviewed"},
        "change_batch": {"id": "b1"},
        "meta": {"applied": 1, "dismissed": 0, "later": 1},
    })

    assert "Applied: 1" in text
    assert "b1" in text


def test_format_workboard_lists_grouped_tasks():
    text = format_workboard({
        "data": {
            "groups": [{
                "label": "Rollout",
                "items": [{
                    "id": "t1",
                    "title": "Write docs",
                    "status": "open",
                    "owner": {"title": "Sam"},
                    "states": {"mine": True},
                }],
            }],
        },
        "meta": {"group": "space", "total": 1, "counts": {"total": 1, "mine": 1}},
    })

    assert "Write docs" in text
    assert "Rollout" in text


def test_format_marker_and_nudge_draft():
    marker_text = format_marker({"data": {"id": "m1", "kind": "nudge", "entity_id": "t1", "note": "Ping"}})
    assert "m1" in marker_text
    assert "Ping" in marker_text

    nudge_text = format_nudge_draft({
        "data": {
            "commitment_id": "t1",
            "draft": "Quick follow-up",
            "original_ask": "Send report",
            "receipts": [],
            "auto_sent": False,
        }
    })
    assert "Quick follow-up" in nudge_text
    assert "Send report" in nudge_text

