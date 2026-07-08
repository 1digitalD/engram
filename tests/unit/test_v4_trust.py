import pytest

from models import Entity
from services.v4_trust import PINNABLE_FIELDS, check_pin, record_pin


@pytest.mark.parametrize("field", sorted(PINNABLE_FIELDS))
@pytest.mark.parametrize(
    ("actor", "pin_state", "allow_write", "should_pin", "should_demote"),
    [
        ("user", False, True, True, False),
        ("user", True, True, True, False),
        ("agent:v4-capture", False, True, False, False),
        ("agent:v4-capture", True, False, False, True),
        ("agent:v4-review", False, True, False, False),
        ("agent:v4-review", True, False, False, True),
    ],
)
def test_check_pin_matrix(field, actor, pin_state, allow_write, should_pin, should_demote):
    entity = Entity(type="task", title="Pinned task", pinned_fields=[field] if pin_state else [])

    decision = check_pin(entity, field, actor)

    assert decision["allow_write"] is allow_write
    assert decision["should_pin"] is should_pin
    assert decision["should_demote"] is should_demote
    assert decision["is_pinned"] is pin_state
    if should_demote:
        assert field in decision["reason"]


def test_check_pin_allows_non_pinnable_fields():
    entity = Entity(type="task", title="Pinned task", pinned_fields=["status"])

    decision = check_pin(entity, "follow_up_at", "agent:v4-capture")

    assert decision["allow_write"] is True
    assert decision["should_pin"] is False
    assert decision["should_demote"] is False
    assert decision["is_pinned"] is False


def test_check_pin_treats_on_behalf_user_as_human():
    entity = Entity(type="task", title="Pinned task", pinned_fields=["status"])

    decision = check_pin(entity, "status", "mcp:planner", on_behalf="user")

    assert decision["allow_write"] is True
    assert decision["should_pin"] is True
    assert decision["should_demote"] is False


def test_record_pin_is_idempotent():
    entity = Entity(type="task", title="Pinned task", pinned_fields=["status"])

    assert record_pin(entity, "status", "user") is False
    assert entity.pinned_fields == ["status"]

    assert record_pin(entity, "due_at", "user") is True
    assert entity.pinned_fields == ["status", "due_at"]
