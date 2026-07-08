"""Unit tests for the v4 distillation report assembler."""

from extensions import db
from services.v4_report import build_report


def _section(report, name):
    return next(s for s in report["sections"] if s["name"] == name)


def _section_names(report):
    return [s["name"] for s in report["sections"]]


def _items(report, name):
    return _section(report, name)["items"]


NOTE = {
    "id": "note-1",
    "title": "Sync notes",
    "content": "Danish: write boilerplate. Priya: document architecture. Decision: Python stack.",
    "ai_meta": {"intent": "task_signal"},
}


def test_tc10_grouping_counts_all_candidates():
    suggestions = [
        {
            "id": "s1",
            "suggestion_type": "create_task",
            "operation_type": "create_entity",
            "payload": {"type": "task", "title": "Write boilerplate", "assigned_to": "Danish"},
            "confidence": 0.91,
            "reason": "action item",
        },
        {
            "id": "s2",
            "suggestion_type": "create_task",
            "operation_type": "create_entity",
            "payload": {"type": "task", "title": "Document architecture", "assigned_to": "Priya"},
            "confidence": 0.88,
            "reason": "action item",
        },
        {
            "id": "s3",
            "suggestion_type": "create_decision",
            "operation_type": "create_decision",
            "payload": {"statement": "Python stack"},
            "confidence": 0.9,
            "reason": "explicit decision",
        },
    ]

    report = build_report(NOTE, [], suggestions)

    assert report["source_note_id"] == "note-1"
    assert report["stats"]["total"] == 3
    assert len(_items(report, "routing_summary")) == 1
    assert len(_items(report, "proposed_commitments")) == 2
    assert len(_items(report, "decisions")) == 1


def test_tc11_section_order_is_stable():
    suggestions = [
        {
            "id": "s1",
            "suggestion_type": "link_existing",
            "operation_type": "link_existing",
            "payload": {"target_entity_id": "p1", "title": "Rollout"},
            "confidence": 0.7,
            "reason": "mentioned",
        },
        {
            "id": "s2",
            "suggestion_type": "create_task",
            "operation_type": "create_entity",
            "payload": {"type": "task", "title": "Ship feature", "assigned_to": "Danish"},
            "confidence": 0.9,
            "reason": "commitment",
        },
        {
            "id": "s3",
            "suggestion_type": "create_decision",
            "operation_type": "create_decision",
            "payload": {"statement": "Use Flask"},
            "confidence": 0.9,
            "reason": "decision",
        },
    ]
    events = [
        {"id": "e1", "event_type": "tag_added", "entity_id": "note-1", "actor": "agent:v4-capture", "new_value": {"tag": "meeting"}, "reason": "auto-tag"},
    ]

    report = build_report(NOTE, events, suggestions)

    assert _section_names(report) == [
        "routing_summary",
        "applied_annotations",
        "proposed_commitments",
        "decisions",
        "questions",
        "leftovers",
    ]
    assert _items(report, "applied_annotations")[0]["kind"] == "tag_added"
    assert _items(report, "proposed_commitments")[0]["id"] == "s2"
    assert _items(report, "decisions")[0]["id"] == "s3"
    assert _items(report, "leftovers")[0]["id"] == "s1"


def test_tc12_speakerless_commitment_becomes_attribution_question():
    suggestions = [
        {
            "id": "s1",
            "suggestion_type": "create_task",
            "operation_type": "create_entity",
            "payload": {"type": "task", "title": "Follow up on rollout"},
            "confidence": 0.85,
            "reason": "commitment with no speaker",
        },
    ]

    report = build_report(NOTE, [], suggestions)

    questions = _items(report, "questions")
    assert len(questions) == 1
    assert questions[0]["kind"] == "attribution"
    assert questions[0]["owner"] is None
    assert "Who committed to this?" in questions[0]["question"]
    assert len(_items(report, "proposed_commitments")) == 0


def test_tc13_applied_annotations_reference_entity_events():
    events = [
        {"id": "e1", "event_type": "tag_added", "entity_id": "note-1", "actor": "agent:v4-capture", "new_value": {"tag": "meeting"}, "reason": "auto-tag"},
        {"id": "e2", "event_type": "relationship_added", "entity_id": "note-1", "actor": "agent:v4-capture", "new_value": {"target_entity_id": "p1", "title": "Rollout", "relationship_type": "related"}, "reason": "auto-link"},
    ]

    report = build_report(NOTE, events, [])

    applied = _items(report, "applied_annotations")
    assert len(applied) == 2
    assert applied[0]["event_id"] == "e1"
    assert applied[1]["event_id"] == "e2"
    assert applied[1]["kind"] == "relationship_added"


def test_tc17_prior_report_superseded_in_database(app):
    from models import AiSuggestion, DistillationReport, Entity
    from services.v4_report import assemble_report_for_note

    with app.app_context():
        note = Entity(type="note", title="T", content="C", status="active", lifecycle="active", source="test")
        db.session.add(note)
        db.session.flush()

        s1 = AiSuggestion(
            source_entity_id=note.id,
            suggestion_type="create_task",
            operation_type="create_entity",
            payload={"type": "task", "title": "Old task", "assigned_to": "Danish"},
            status="pending",
        )
        db.session.add(s1)
        db.session.commit()

        first = assemble_report_for_note(note.id)
        assert first.status == "pending"
        assert s1.report_id == first.id

        s2 = AiSuggestion(
            source_entity_id=note.id,
            suggestion_type="create_task",
            operation_type="create_entity",
            payload={"type": "task", "title": "New task", "assigned_to": "Priya"},
            status="pending",
        )
        db.session.add(s2)
        db.session.commit()

        second = assemble_report_for_note(note.id)
        assert second.id != first.id

        refreshed_first = db.session.get(DistillationReport, first.id)
        assert refreshed_first.status == "superseded"

        refreshed_s1 = db.session.get(AiSuggestion, s1.id)
        assert refreshed_s1.status == "expired"

        refreshed_s2 = db.session.get(AiSuggestion, s2.id)
        assert refreshed_s2.report_id == second.id


def test_receipt_finds_evidence_offset():
    suggestions = [
        {
            "id": "s1",
            "suggestion_type": "create_task",
            "operation_type": "create_entity",
            "payload": {"type": "task", "title": "Write boilerplate", "assigned_to": "Danish", "evidence": "write boilerplate"},
            "confidence": 0.9,
            "reason": "action item",
        },
    ]

    report = build_report(NOTE, [], suggestions)
    receipt = _items(report, "proposed_commitments")[0]["receipt"]
    assert receipt["start"] >= 0
    assert receipt["length"] > 0
    assert "boilerplate" in (receipt["quote"] or "").lower()


def test_routing_summary_receipt_quote_matches_length():
    long_note = {
        "id": "note-long",
        "title": "Long note",
        "content": "x" * 500,
        "ai_meta": {},
    }
    report = build_report(long_note, [], [])
    receipt = _items(report, "routing_summary")[0]["receipt"]
    assert receipt["start"] == 0
    assert receipt["quote"] == "x" * 200
    assert receipt["length"] == 200
