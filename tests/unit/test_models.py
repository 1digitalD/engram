"""Unit tests for the v4 SQLAlchemy data model."""

import uuid
from datetime import datetime, timezone


V4_TABLES = {
    "entities",
    "entity_links",
    "tags",
    "entity_tags",
    "entity_chunks",
    "entity_events",
    "ai_suggestions",
    "jobs",
    "change_batches",
}

FORBIDDEN_DTO_FIELDS = {
    "raw_text",
    "name",
    "is_archived",
    "project_id",
    "project_ids",
    "area_id",
    "person_id",
    "note_id",
    "parent_id",
    "due_date",
}


def _make_entity(**overrides):
    from models import Entity

    defaults = dict(
        id=str(uuid.uuid4()),
        type="task",
        title="Follow up with Henry",
        content="Ask for rollout stages.",
        status="open",
        lifecycle="active",
        follow_up_at=datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc),
        source="manual",
        reference_url=None,
        properties={"priority": "high"},
        ai_meta={"summary": "Short generated summary", "confidence": 0.91},
        ai_status="done",
        created_at=datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 18, 12, 5, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Entity(**defaults)


def _make_tag(**overrides):
    from models import Tag

    defaults = dict(
        id=str(uuid.uuid4()),
        name="memory",
        color=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Tag(**defaults)


def _make_entity_link(**overrides):
    from models import EntityLink

    defaults = dict(
        id=str(uuid.uuid4()),
        source_entity_id=str(uuid.uuid4()),
        target_entity_id=str(uuid.uuid4()),
        relationship_type="related",
        source="manual",
        confidence=None,
        evidence=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return EntityLink(**defaults)


def test_v4_model_metadata_contains_required_tables_only():
    from extensions import db
    import models  # noqa: F401

    assert set(db.Model.metadata.tables) == V4_TABLES


def test_fresh_database_initializes_v4_tables(app):
    from sqlalchemy import text
    from extensions import db

    rows = db.session.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            """
        )
    ).scalars()

    assert set(rows) == V4_TABLES


def test_fresh_database_uses_v4_entity_link_columns(app):
    from sqlalchemy import text
    from extensions import db

    rows = db.session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'entity_links'
            """
        )
    ).scalars()

    columns = set(rows)
    assert {"source_entity_id", "target_entity_id", "relationship_type"}.issubset(columns)
    assert {"src_id", "dst_id", "link_type", "weight", "inverse"}.isdisjoint(columns)


def test_init_db_resets_stale_entity_links_shape(app, runner):
    from sqlalchemy import text
    from extensions import db

    db.session.remove()
    connection = db.engine.raw_connection()
    try:
        connection.autocommit = True
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                DO $$ DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                    END LOOP;
                END $$;
                """
            )
            cursor.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
            cursor.execute("CREATE TABLE entities (id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text)")
            cursor.execute(
                """
                CREATE TABLE entity_links (
                    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
                    src_id TEXT,
                    dst_id TEXT,
                    link_type TEXT
                )
                """
            )
            connection.commit()
        finally:
            cursor.close()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    result = runner.invoke(args=["init-db"])

    assert result.exit_code == 0
    assert "fresh v4 schema applied." in result.output

    rows = db.session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'entity_links'
            """
        )
    ).scalars()
    columns = set(rows)
    assert {"source_entity_id", "target_entity_id", "relationship_type"}.issubset(columns)
    assert {"src_id", "dst_id", "link_type"}.isdisjoint(columns)


def test_entity_canonical_dto_shape_has_no_legacy_fields():
    tag = _make_tag()
    entity = _make_entity()
    entity._tag_objects = [tag]
    entity._relationship_counts = {"incoming": 2, "outgoing": 5}

    dto = entity.to_dict()

    assert dto == {
        "id": entity.id,
        "type": "task",
        "title": "Follow up with Henry",
        "content": "Ask for rollout stages.",
        "status": "open",
        "lifecycle": "active",
        "follow_up_at": "2026-05-20T10:00:00+00:00",
        "source": "manual",
        "reference_url": None,
        "properties": {"priority": "high"},
        "tags": [{"id": tag.id, "name": "memory"}],
        "ai": {"summary": "Short generated summary", "status": "done", "confidence": 0.91},
        "relationship_counts": {"incoming": 2, "outgoing": 5},
        "created_at": "2026-05-18T12:00:00+00:00",
        "updated_at": "2026-05-18T12:05:00+00:00",
    }
    assert FORBIDDEN_DTO_FIELDS.isdisjoint(dto)


def test_all_v4_entity_types_serialize_without_legacy_fields():
    for entity_type in ("note", "task", "project", "area", "resource", "person"):
        dto = _make_entity(type=entity_type, title=f"Test {entity_type}").to_dict()
        assert dto["type"] == entity_type
        assert FORBIDDEN_DTO_FIELDS.isdisjoint(dto)


def test_relationships_use_entity_link_columns_not_properties():
    link = _make_entity_link(relationship_type="parent", confidence=0.95)
    dto = link.to_dict()

    assert dto["source_entity_id"] == link.source_entity_id
    assert dto["target_entity_id"] == link.target_entity_id
    assert dto["relationship_type"] == "parent"
    assert {"src_id", "dst_id", "link_type", "weight", "inverse"}.isdisjoint(dto)


def test_entity_link_declares_v4_relationship_constraints():
    from models import EntityLink

    columns = set(EntityLink.__table__.columns.keys())
    assert {"source_entity_id", "target_entity_id", "relationship_type"}.issubset(columns)
    assert {"src_id", "dst_id", "link_type"}.isdisjoint(columns)

    constraints = {constraint.name for constraint in EntityLink.__table__.constraints}
    assert "uq_entity_links_source_target_type" in constraints
    assert "chk_entity_links_no_self_link" in constraints
    assert "chk_entity_links_relationship_type" in constraints


def test_entity_event_uses_v4_event_names():
    from models import EntityEvent

    event = EntityEvent(
        id=str(uuid.uuid4()),
        entity_id=str(uuid.uuid4()),
        event_type="relationship_added",
        actor="agent:autolink",
        new_value={"relationship_type": "mentions"},
        created_at=datetime.now(timezone.utc),
    )

    dto = event.to_dict()
    assert dto["event_type"] == "relationship_added"
    assert dto["actor"] == "agent:autolink"


def test_ai_suggestion_and_change_batch_serialize():
    from models import AiSuggestion, ChangeBatch

    source_id = str(uuid.uuid4())
    suggestion = AiSuggestion(
        id=str(uuid.uuid4()),
        source_entity_id=source_id,
        suggestion_type="create_task",
        operation_type="create_entity",
        payload={"title": "Follow up"},
        confidence=0.88,
        reason="Looks actionable",
        status="pending",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    batch = ChangeBatch(
        id=str(uuid.uuid4()),
        source_note_id=source_id,
        actor="agent:autolink",
        source="ai",
        summary="Applied safe links",
        created_at=datetime.now(timezone.utc),
    )

    assert suggestion.to_dict()["payload"] == {"title": "Follow up"}
    assert batch.to_dict()["source_note_id"] == source_id
