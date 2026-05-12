"""Shared utility functions used across the API and services."""

VALID_PRIORITIES = {"low", "medium", "high", "urgent"}


def parse_priority(val) -> str:
    """Normalize a priority value to a lowercase string. Defaults to 'medium'."""
    if val is None:
        return "medium"
    normalized = str(val).lower()
    return normalized if normalized in VALID_PRIORITIES else "medium"
