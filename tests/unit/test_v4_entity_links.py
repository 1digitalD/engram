"""Unit tests for the manual link endpoint helpers."""

from api.v4_entities import _is_relationship_compatible


def test_is_relationship_compatible_allows_canonical_pairs():
    assert _is_relationship_compatible("parent", "task", "project") is True
    assert _is_relationship_compatible("parent", "project", "area") is True
    assert _is_relationship_compatible("assigned_to", "task", "person") is True
    assert _is_relationship_compatible("derived_from", "task", "note") is True
    assert _is_relationship_compatible("blocks", "task", "task") is True


def test_is_relationship_compatible_rejects_incompatible_pairs():
    assert _is_relationship_compatible("parent", "task", "person") is False
    assert _is_relationship_compatible("parent", "note", "project") is False
    assert _is_relationship_compatible("assigned_to", "project", "person") is False
    assert _is_relationship_compatible("derived_from", "note", "task") is False
    assert _is_relationship_compatible("blocks", "task", "project") is False
