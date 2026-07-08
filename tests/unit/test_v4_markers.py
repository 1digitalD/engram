"""Unit tests for follow-up marker firing logic."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from extensions import db
from services.v4_markers import (
    _entity_blocks_firing,
    _validate_marker_payload,
    fire_due_markers,
)


MIGRATION_010 = (
    Path(__file__).resolve().parents[2] / "scripts" / "migrations" / "010_followup_markers.sql"
)

NOW = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def apply_migration_010(app):
    assert MIGRATION_010.exists()
    with app.app_context():
        db.session.execute(db.text(MIGRATION_010.read_text()))
        db.session.commit()


class _Entity:
    def __init__(self, *, lifecycle="active", entity_type="task", status="open"):
        self.lifecycle = lifecycle
        self.type = entity_type
        self.status = status


def test_validate_marker_payload_requires_kind_entity_and_due_for_nudge():
    assert _validate_marker_payload({}) == "kind must be one of: custom, discuss, nudge"
    assert _validate_marker_payload({"kind": "nudge"}) == "entity_id is required"
    assert (
        _validate_marker_payload({"kind": "nudge", "entity_id": "task-1"})
        == "due_at is required for nudge markers"
    )
    assert (
        _validate_marker_payload(
            {
                "kind": "discuss",
                "entity_id": "task-1",
                "person_entity_id": "person-1",
            }
        )
        is None
    )


def test_entity_blocks_firing_for_archived_or_done():
    assert _entity_blocks_firing(_Entity(lifecycle="archived")) is True
    assert _entity_blocks_firing(_Entity(status="done")) is True
    assert _entity_blocks_firing(_Entity(status="completed")) is True
    assert _entity_blocks_firing(_Entity()) is False


def test_fire_due_markers_sets_fired_at_once(app):
    from extensions import db
    from models import Entity, FollowupMarker

    with app.app_context():
        task = Entity(type="task", title="Follow up", status="open", lifecycle="active")
        db.session.add(task)
        db.session.commit()

        marker = FollowupMarker(
            entity_id=task.id,
            kind="nudge",
            due_at=NOW - timedelta(days=1),
            note="Ping Sam",
        )
        db.session.add(marker)
        db.session.commit()
        marker_id = marker.id

        first = fire_due_markers(NOW)
        assert len(first["fired"]) == 1
        assert first["fired"][0].fired_at is not None

        second = fire_due_markers(NOW)
        assert second["fired"] == []

        stored = db.session.get(FollowupMarker, marker_id)
        assert stored.fired_at is not None
        assert stored.resolved_at is None


def test_fire_due_markers_auto_resolves_on_closed_entity(app):
    from extensions import db
    from models import Entity, FollowupMarker

    with app.app_context():
        task = Entity(type="task", title="Done task", status="done", lifecycle="active")
        db.session.add(task)
        db.session.commit()

        marker = FollowupMarker(
            entity_id=task.id,
            kind="nudge",
            due_at=NOW - timedelta(hours=1),
        )
        db.session.add(marker)
        db.session.commit()

        result = fire_due_markers(NOW)
        assert result["fired"] == []
        assert result["resolved"] == 1
        assert marker.fired_at is None
        assert marker.resolved_at is not None
