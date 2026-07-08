"""Unit tests for the SQ-07 task structural gate."""

import pytest

from api.v4_entities import (
    _title_has_deliverable_shape,
    _task_structural_score,
    _task_suggest_ok,
    _suggestion_task_structural_score,
    _collect_work_carrying_persons,
)


class TestTitleHasDeliverableShape:
    def test_recognizes_verb_object(self):
        assert _title_has_deliverable_shape("Ship the rollout plan") is True
        assert _title_has_deliverable_shape("Draft the Q3 roadmap") is True
        assert _title_has_deliverable_shape("Follow up with Henry") is True

    def test_follow_up_compound_verb(self):
        assert _title_has_deliverable_shape("Follow up with legal") is True
        assert _title_has_deliverable_shape("Follow-up with legal") is True

    def test_rejects_logistics_verbs(self):
        assert _title_has_deliverable_shape("Attend all hands") is False
        assert _title_has_deliverable_shape("Hold a meeting") is False
        assert _title_has_deliverable_shape("Book a room") is False

    def test_rejects_stance_verbs(self):
        assert _title_has_deliverable_shape("Endorse L2 priority") is False
        assert _title_has_deliverable_shape("Defer L3 work") is False
        assert _title_has_deliverable_shape("Revisit next quarter") is False
        assert _title_has_deliverable_shape("Prioritize L2 over L3") is False

    def test_rejects_tentative_prefix(self):
        assert _title_has_deliverable_shape("Maybe follow up with Henry") is False
        assert _title_has_deliverable_shape("Possibly ship the plan") is False

    def test_rejects_bare_verb_or_noun_phrase(self):
        assert _title_has_deliverable_shape("Rollout") is False
        assert _title_has_deliverable_shape("Ship") is False


class TestTaskStructuralScore:
    def test_full_score_for_strong_task(self):
        candidate = {
            "title": "Ship the L2 rollout plan",
            "assigned_to": "Akash",
            "due_at": "2026-07-10",
        }
        decision = {"top_match_score": 0.0}
        # target_resolvable needs a note object; pass None so it scores 0 for that signal.
        assert _task_structural_score(None, candidate, decision) == 3

    def test_owner_and_deliverable_score_two(self):
        candidate = {
            "title": "Follow up with Henry on rollout",
            "assigned_to": "Henry",
        }
        decision = {"top_match_score": 0.0}
        assert _task_structural_score(None, candidate, decision) == 2

    def test_deliverable_alone_score_one(self):
        candidate = {"title": "Follow up on rollout"}
        decision = {"top_match_score": 0.0}
        assert _task_structural_score(None, candidate, decision) == 1

    def test_stance_fragment_score_zero_or_one(self):
        candidate = {"title": "Endorse L2 priority"}
        decision = {"top_match_score": 0.0}
        assert _task_structural_score(None, candidate, decision) == 0

    def test_logistics_score_zero(self):
        candidate = {"title": "Attend all hands in Vancouver"}
        decision = {"top_match_score": 0.0}
        assert _task_structural_score(None, candidate, decision) == 0


class TestTaskSuggestGate:
    def test_owner_and_deliverable_suggests(self):
        candidate = {
            "title": "Follow up with Henry on rollout",
            "assigned_to": "Henry",
        }
        decision = {"top_match_score": 0.0}
        assert _task_suggest_ok(None, candidate, decision, 0.7) is True

    def test_perfect_score_low_confidence_suggests(self):
        candidate = {
            "title": "Ship the L2 rollout plan",
            "assigned_to": "Akash",
            "due_at": "2026-07-10",
        }
        decision = {"top_match_score": 0.8}
        assert _task_suggest_ok(None, candidate, decision, 0.55) is True

    def test_logistics_does_not_suggest(self):
        candidate = {"title": "Attend all hands in Vancouver"}
        decision = {"top_match_score": 0.0}
        assert _task_suggest_ok(None, candidate, decision, 0.99) is False

    def test_stance_fragment_does_not_suggest(self):
        candidate = {"title": "Endorse L2 priority"}
        decision = {"top_match_score": 0.0}
        assert _task_suggest_ok(None, candidate, decision, 0.99) is False

    def test_low_confidence_partial_score_drops(self):
        candidate = {
            "title": "Follow up with Henry on rollout",
            "assigned_to": "Henry",
        }
        decision = {"top_match_score": 0.0}
        assert _task_suggest_ok(None, candidate, decision, 0.45) is False


class TestSuggestionTaskStructuralScore:
    def test_prefers_stronger_structural_candidate_over_confidence(self):
        note = None
        weak_high_conf = {
            "suggestion_type": "create_task",
            "confidence": 0.99,
            "payload": {"title": "Attend all hands", "assigned_to": None},
        }
        strong_low_conf = {
            "suggestion_type": "create_task",
            "confidence": 0.55,
            "payload": {
                "title": "Follow up with Henry on rollout",
                "assigned_to": "Henry",
            },
        }
        assert _suggestion_task_structural_score(note, strong_low_conf) > _suggestion_task_structural_score(
            note, weak_high_conf
        )


class TestCollectWorkCarryingPersons:
    def test_includes_assignee_and_follow_up_target(self):
        candidates = [
            {"type": "task", "title": "Follow up with Mary on contract", "assigned_to": "Akash"},
            {
                "type": "person",
                "title": "Legal Team",
                "_source": "link",
                "relationship_type": "assigned_to",
            },
        ]
        names = _collect_work_carrying_persons(candidates)
        assert "Akash" in names
        assert "Mary" in names
        assert "Legal Team" in names
