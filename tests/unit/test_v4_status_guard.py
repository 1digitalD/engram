"""Unit tests for SQ-09 explicit status language guard."""

from api.v4_entities import _status_change_is_explicit


class TestStatusChangeIsExplicit:
    def test_affirms_done_language(self):
        assert _status_change_is_explicit("We shipped the rollout.", "done") is True
        assert _status_change_is_explicit("Task is done now.", "done") is True

    def test_rejects_negated_done_language(self):
        assert _status_change_is_explicit("This is not done yet.", "done") is False
        assert _status_change_is_explicit("We haven't shipped yet.", "done") is False
        assert _status_change_is_explicit("Don't close this out.", "done") is False

    def test_affirms_done_despite_unrelated_no_phrasing(self):
        assert _status_change_is_explicit("No blockers, shipped today.", "done") is True
        assert _status_change_is_explicit("No issues — completed the rollout.", "done") is True

    def test_affirms_blocked_language(self):
        assert _status_change_is_explicit("Blocked on legal review.", "blocked") is True

    def test_rejects_negated_blocked_language(self):
        assert _status_change_is_explicit("Not blocked anymore.", "blocked") is False
        assert _status_change_is_explicit("We aren't blocked on this.", "blocked") is False

    def test_affirms_waiting_language(self):
        assert _status_change_is_explicit("Waiting on Mary for sign-off.", "waiting") is True

    def test_rejects_negated_waiting_language(self):
        assert _status_change_is_explicit("Not waiting on anyone now.", "waiting") is False
