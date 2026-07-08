"""Pin enforcement helpers for v4 entity writes."""

PINNABLE_FIELDS = frozenset({"status", "due_at", "title", "owner", "parent"})


def normalize_pin_field(field):
    value = (field or "").strip().lower()
    return value or None


def relationship_pin_field(relationship_type):
    if relationship_type == "assigned_to":
        return "owner"
    if relationship_type == "parent":
        return "parent"
    return None


def is_human_actor(actor, on_behalf=None):
    if (on_behalf or "").strip().lower() == "user":
        return True
    return (actor or "").strip().lower() == "user"


def _pinned_fields(entity):
    return list(getattr(entity, "pinned_fields", None) or [])


def pin_reason(field):
    return f"Field '{field}' is pinned and requires human review before AI can change it"


def check_pin(entity, field, actor, on_behalf=None):
    field_name = normalize_pin_field(field)
    pinnable = field_name in PINNABLE_FIELDS
    pinned = field_name in _pinned_fields(entity) if pinnable else False
    human = is_human_actor(actor, on_behalf=on_behalf)
    should_demote = pinnable and pinned and not human
    return {
        "field": field_name,
        "allow_write": not should_demote,
        "should_pin": pinnable and human,
        "should_demote": should_demote,
        "is_pinned": pinned,
        "reason": pin_reason(field_name) if should_demote else None,
    }


def set_pin(entity, field):
    field_name = normalize_pin_field(field)
    if field_name not in PINNABLE_FIELDS:
        return False
    pinned_fields = _pinned_fields(entity)
    if field_name in pinned_fields:
        return False
    entity.pinned_fields = [*pinned_fields, field_name]
    return True


def clear_pin(entity, field):
    field_name = normalize_pin_field(field)
    pinned_fields = _pinned_fields(entity)
    if field_name not in pinned_fields:
        return False
    entity.pinned_fields = [value for value in pinned_fields if value != field_name]
    return True


def record_pin(entity, field, actor, on_behalf=None):
    decision = check_pin(entity, field, actor, on_behalf=on_behalf)
    if not decision["should_pin"]:
        return False
    return set_pin(entity, field)
