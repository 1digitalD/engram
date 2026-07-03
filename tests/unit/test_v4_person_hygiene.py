"""Unit tests for SQ-08 person deduplication and auto-creation hygiene."""

from api.v4_entities import _find_existing_person, _person_carries_work
from extensions import db
from models import Entity


def test_find_existing_person_exact_match(client, app):
    with app.app_context():
        person = Entity(type="person", title="Priya Dhandapani", lifecycle="active", status="active")
        db.session.add(person)
        db.session.commit()

        assert _find_existing_person("Priya Dhandapani") is not None
        assert _find_existing_person("priya dhandapani") is not None


def test_find_existing_person_first_name_match(client, app):
    with app.app_context():
        person = Entity(type="person", title="Priya Dhandapani", lifecycle="active", status="active")
        db.session.add(person)
        db.session.commit()

        found = _find_existing_person("Priya")
        assert found is not None
        assert found.title == "Priya Dhandapani"


def test_find_existing_person_ambiguous_first_name_returns_none(client, app):
    with app.app_context():
        db.session.add_all([
            Entity(type="person", title="Sam Smith", lifecycle="active", status="active"),
            Entity(type="person", title="Sam Jones", lifecycle="active", status="active"),
        ])
        db.session.commit()

        assert _find_existing_person("Sam") is None


def test_find_existing_person_no_match_returns_none(client, app):
    with app.app_context():
        assert _find_existing_person("Henry") is None


def test_person_carries_work_exact_name():
    assert _person_carries_work("Henry", {"Henry"}) is True
    assert _person_carries_work("henry", {"Henry"}) is True


def test_person_carries_work_first_name_of_assignee():
    assert _person_carries_work("Priya", {"Priya Dhandapani"}) is True


def test_person_carries_work_assignee_first_name_of_candidate():
    assert _person_carries_work("Priya Dhandapani", {"Priya"}) is True


def test_person_carries_work_no_match():
    assert _person_carries_work("Henry", set()) is False
    assert _person_carries_work("Henry", {"Akash"}) is False
