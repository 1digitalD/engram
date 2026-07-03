"""Unit tests for the SQ-04 structural guardrail on decision extraction.

The LLM prompt in services/v4_decisions.py already requires a named actor and
a concrete date/deliverable before extracting a decision, but the model
sometimes ignores that (real example: "We can close this task now." was
extracted as a decision). These tests exercise the post-hoc structural
guardrail applied in _normalize_decisions, independent of the LLM.
"""
from services.v4_decisions import _normalize_decisions


def _item(statement, context=None, decided_at=None, decided_by="user"):
    return {
        "statement": statement,
        "context": context or statement,
        "decided_at": decided_at,
        "decided_by": decided_by,
    }


def test_rejects_closure_language_without_actor_or_date():
    result = _normalize_decisions([_item("We can close this task now.")])
    assert result == []


def test_rejects_wrap_up_language_without_actor_or_date():
    result = _normalize_decisions([_item("We should wrap this up.")])
    assert result == []


def test_rejects_statement_with_no_named_actor_and_no_date():
    # No closure language either, but still lacks any structural signal.
    result = _normalize_decisions([_item("We agreed to move forward.")])
    assert result == []


def test_accepts_named_actor_with_concrete_date():
    result = _normalize_decisions(
        [_item("Dan will deliver the wireframes by 2026-07-15.", decided_at="2026-07-15T00:00:00+00:00")]
    )
    assert len(result) == 1
    assert result[0]["statement"] == "Dan will deliver the wireframes by 2026-07-15."


def test_accepts_agent_decision_with_proper_noun_deliverable():
    result = _normalize_decisions(
        [_item("The agent decided to use Python for the new stack.", decided_by="agent:v4-capture")]
    )
    assert len(result) == 1
    assert result[0]["decided_by"] == "agent:v4-capture"


def test_accepts_closure_language_when_actor_is_named():
    # Closure-flavored language is fine when there's a named actor making a
    # forward commitment — the guardrail targets unattributed status chatter,
    # not every mention of "close"/"done".
    result = _normalize_decisions([_item("Dan will close out the task once the review lands.")])
    assert len(result) == 1


def test_accepts_closure_language_with_concrete_date():
    result = _normalize_decisions([_item("This task will be marked as done by Friday.")])
    assert len(result) == 1


def test_rejects_i_statement_without_date_or_deliverable_is_still_gated_by_tentative_filter():
    # Sanity check that a tentative "I" statement is still caught by the
    # existing TENTATIVE_MARKERS filter, not just the new guardrail.
    result = _normalize_decisions([_item("I think we should close this out.")])
    assert result == []
