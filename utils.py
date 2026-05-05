"""Shared utility functions used across the API and services."""
from models import Priority


def parse_priority(val) -> Priority:
    """Coerce a string or Priority enum value into a Priority enum. Defaults to MEDIUM."""
    if val is None:
        return Priority.MEDIUM
    if isinstance(val, Priority):
        return val
    try:
        return Priority(str(val).upper())
    except (ValueError, AttributeError):
        return Priority.MEDIUM
