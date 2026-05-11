"""Unit tests for entity lifecycle — VALID_TRANSITIONS and service logic.

Tests the transition validation logic and service-level behavior
without requiring a database connection.
"""

import pytest

from services.entity_service import VALID_TRANSITIONS


# ─── VALID_TRANSITIONS structure ─────────────────────────────────────────────


class TestValidTransitionsStructure:
    """Verify the transition map has the expected shape."""

    def test_all_entity_types_present(self):
        expected_types = {"task", "project", "note", "area", "resource", "person"}
        assert set(VALID_TRANSITIONS.keys()) == expected_types

    def test_task_transitions(self):
        t = VALID_TRANSITIONS["task"]
        assert "pending" in t
        assert "in_progress" in t
        assert "done" in t
        assert "cancelled" in t
        assert "in_progress" in t["pending"]
        assert "done" in t["pending"]
        assert "cancelled" in t["pending"]
        assert "pending" in t["done"]
        assert "pending" in t["cancelled"]

    def test_project_transitions(self):
        t = VALID_TRANSITIONS["project"]
        assert "active" in t
        assert "on_hold" in t
        assert "completed" in t
        assert "cancelled" in t
        assert "on_hold" in t["active"]
        assert "completed" in t["active"]
        assert "cancelled" in t["active"]
        assert "active" in t["completed"]
        assert "active" in t["cancelled"]

    def test_note_transitions(self):
        t = VALID_TRANSITIONS["note"]
        assert t == {"active": ["archived"], "archived": ["active"]}

    def test_area_transitions(self):
        t = VALID_TRANSITIONS["area"]
        assert t == {"active": ["archived"], "archived": ["active"]}

    def test_resource_transitions(self):
        t = VALID_TRANSITIONS["resource"]
        assert t == {"active": ["archived"], "archived": ["active"]}

    def test_person_transitions(self):
        t = VALID_TRANSITIONS["person"]
        assert t == {"active": ["archived"], "archived": ["active"]}

    def test_all_transitions_are_lists(self):
        for entity_type, transitions in VALID_TRANSITIONS.items():
            for from_status, to_statuses in transitions.items():
                assert isinstance(to_statuses, list), \
                    f"{entity_type}.{from_status} should be a list"

    def test_no_self_transitions(self):
        """A status should never list itself as a valid transition."""
        for entity_type, transitions in VALID_TRANSITIONS.items():
            for from_status, to_statuses in transitions.items():
                assert from_status not in to_statuses, \
                    f"{entity_type}.{from_status} should not transition to itself"


# ─── Transition validation logic (pure function tests) ───────────────────────


class TestTransitionValidation:
    """Test the logic of what transitions are allowed."""

    def _is_valid(self, entity_type, from_status, to_status):
        """Helper: check if a transition is valid."""
        if entity_type not in VALID_TRANSITIONS:
            return False
        allowed = VALID_TRANSITIONS[entity_type].get(from_status, [])
        return to_status in allowed

    # Task transitions
    def test_task_pending_to_in_progress(self):
        assert self._is_valid("task", "pending", "in_progress")

    def test_task_pending_to_done(self):
        assert self._is_valid("task", "pending", "done")

    def test_task_pending_to_cancelled(self):
        assert self._is_valid("task", "pending", "cancelled")

    def test_task_in_progress_to_pending(self):
        assert self._is_valid("task", "in_progress", "pending")

    def test_task_in_progress_to_done(self):
        assert self._is_valid("task", "in_progress", "done")

    def test_task_done_to_pending(self):
        assert self._is_valid("task", "done", "pending")

    def test_task_invalid_pending_to_archived(self):
        assert not self._is_valid("task", "pending", "archived")

    def test_task_invalid_done_to_cancelled(self):
        assert not self._is_valid("task", "done", "cancelled")

    def test_task_invalid_cancelled_to_done(self):
        assert not self._is_valid("task", "cancelled", "done")

    # Project transitions
    def test_project_active_to_on_hold(self):
        assert self._is_valid("project", "active", "on_hold")

    def test_project_active_to_completed(self):
        assert self._is_valid("project", "active", "completed")

    def test_project_active_to_cancelled(self):
        assert self._is_valid("project", "active", "cancelled")

    def test_project_on_hold_to_active(self):
        assert self._is_valid("project", "on_hold", "active")

    def test_project_completed_to_active(self):
        assert self._is_valid("project", "completed", "active")

    def test_project_invalid_active_to_archived(self):
        assert not self._is_valid("project", "active", "archived")

    # Note/area/resource/person transitions
    def test_note_active_to_archived(self):
        assert self._is_valid("note", "active", "archived")

    def test_note_archived_to_active(self):
        assert self._is_valid("note", "archived", "active")

    def test_note_invalid_active_to_done(self):
        assert not self._is_valid("note", "active", "done")

    def test_area_active_to_archived(self):
        assert self._is_valid("area", "active", "archived")

    def test_resource_active_to_archived(self):
        assert self._is_valid("resource", "active", "archived")

    def test_person_active_to_archived(self):
        assert self._is_valid("person", "active", "archived")

    # Unknown type
    def test_unknown_type_rejected(self):
        assert not self._is_valid("unknown_type", "active", "archived")

    # Unknown from_status
    def test_unknown_from_status_rejected(self):
        assert not self._is_valid("task", "unknown_status", "done")
