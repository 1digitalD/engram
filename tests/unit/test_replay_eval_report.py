"""Unit tests for replay eval report grouping metrics."""

from scripts.replay_eval import score_report_grouping


def _report_with_sections(section_items):
    return {
        "source_note_id": "note-1",
        "sections": [
            {"name": "routing_summary", "items": section_items.get("routing_summary", [])},
            {
                "name": "applied_annotations",
                "items": section_items.get("applied_annotations", []),
            },
            {
                "name": "proposed_commitments",
                "items": section_items.get("proposed_commitments", []),
            },
            {"name": "decisions", "items": section_items.get("decisions", [])},
            {"name": "questions", "items": section_items.get("questions", [])},
            {"name": "leftovers", "items": section_items.get("leftovers", [])},
        ],
    }


def test_score_report_grouping_returns_perfect_score_for_expected_sections():
    report = _report_with_sections(
        {
            "routing_summary": [{"id": "route-1", "kind": "routing_summary"}],
            "applied_annotations": [{"id": "event-1", "event_id": "event-1", "kind": "tag_added"}],
            "proposed_commitments": [
                {
                    "id": "suggestion-1",
                    "kind": "create_entity",
                    "payload": {"type": "task", "title": "Write docs", "assigned_to": "Danish"},
                }
            ],
            "decisions": [
                {
                    "id": "suggestion-2",
                    "kind": "create_decision",
                    "payload": {"statement": "Use Flask"},
                }
            ],
            "questions": [
                {
                    "id": "question-1",
                    "kind": "attribution",
                    "owner": None,
                    "question": "Who committed this?",
                }
            ],
            "leftovers": [
                {
                    "id": "suggestion-3",
                    "kind": "link_existing",
                    "payload": {"target_entity_id": "project-1", "title": "Agent Platform"},
                }
            ],
        }
    )

    score = score_report_grouping(report)

    assert score["items_scored"] == 6
    assert score["correctly_grouped"] == 6
    assert score["grouping_score"] == 1.0
    assert score["section_order_score"] == 1.0
    assert score["overall_score"] == 1.0


def test_score_report_grouping_penalizes_wrong_sections_and_wrong_order():
    report = {
        "source_note_id": "note-1",
        "sections": [
            {
                "name": "routing_summary",
                "items": [{"id": "route-1", "kind": "routing_summary"}],
            },
            {
                "name": "proposed_commitments",
                "items": [{"id": "event-1", "event_id": "event-1", "kind": "tag_added"}],
            },
            {
                "name": "applied_annotations",
                "items": [
                    {
                        "id": "suggestion-1",
                        "kind": "create_entity",
                        "payload": {"type": "task", "title": "Write docs", "assigned_to": "Danish"},
                    }
                ],
            },
            {
                "name": "questions",
                "items": [
                    {
                        "id": "suggestion-2",
                        "kind": "create_decision",
                        "payload": {"statement": "Use Flask"},
                    }
                ],
            },
            {
                "name": "decisions",
                "items": [
                    {
                        "id": "question-1",
                        "kind": "attribution",
                        "owner": None,
                        "question": "Who committed this?",
                    }
                ],
            },
            {
                "name": "leftovers",
                "items": [
                    {
                        "id": "suggestion-3",
                        "kind": "link_existing",
                        "payload": {"target_entity_id": "project-1", "title": "Agent Platform"},
                    }
                ],
            },
        ],
    }

    score = score_report_grouping(report)

    assert score["items_scored"] == 6
    assert score["correctly_grouped"] == 2
    assert score["grouping_score"] < 1.0
    assert score["section_order_score"] < 1.0
    assert score["overall_score"] < 1.0
