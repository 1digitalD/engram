"""Shared assertion helpers for integration tests."""


def applied_change_contains(applied_changes, expected):
    """True when some applied_change dict contains all expected key/value pairs."""
    return any(expected.items() <= change.items() for change in applied_changes)


def parent_context_ref(entity_id, title):
    """Return a matcher for project/area parent refs that include relationship_id."""

    def _matches(actual):
        return (
            len(actual) == 1
            and actual[0]["id"] == entity_id
            and actual[0]["title"] == title
            and actual[0].get("relationship_id")
        )

    return _matches
