"""Unit tests for SQLAlchemy models — no DB required."""

import uuid
from datetime import datetime, timezone

import pytest


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_entity(**overrides):
    """Build an Entity instance without a session."""
    from models import Entity

    defaults = dict(
        id=str(uuid.uuid4()),
        type="note",
        title="Test Note",
        content="Test content",
        status="active",
        lifecycle="active",
        follow_up_at=None,
        source="manual",
        reference_url=None,
        properties={},
        ai_meta={},
        ai_status="pending",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Entity(**defaults)


def _make_tag(**overrides):
    from models import Tag

    defaults = dict(
        id=str(uuid.uuid4()),
        name="test-tag",
        color=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Tag(**defaults)


def _make_entity_tag(entity_id=None, tag_id=None, **overrides):
    from models import EntityTag

    eid = entity_id or str(uuid.uuid4())
    tid = tag_id or str(uuid.uuid4())
    defaults = dict(
        entity_id=eid,
        tag_id=tid,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return EntityTag(**defaults)


def _make_entity_link(src_id=None, dst_id=None, **overrides):
    from models import EntityLink

    sid = src_id or str(uuid.uuid4())
    did = dst_id or str(uuid.uuid4())
    defaults = dict(
        id=str(uuid.uuid4()),
        src_id=sid,
        dst_id=did,
        link_type="related",
        weight=1.0,
        source="manual",
        confidence=None,
        evidence=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return EntityLink(**defaults)


def _make_entity_chunk(entity_id=None, **overrides):
    from models import EntityChunk

    eid = entity_id or str(uuid.uuid4())
    defaults = dict(
        id=str(uuid.uuid4()),
        entity_id=eid,
        chunk_index=0,
        chunk_text="chunk text",
        embedding=None,
        embedding_model="text-embedding-3-small",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return EntityChunk(**defaults)


def _make_entity_event(entity_id=None, **overrides):
    from models import EntityEvent

    eid = entity_id or str(uuid.uuid4())
    defaults = dict(
        id=str(uuid.uuid4()),
        entity_id=eid,
        event_type="created",
        actor="user",
        old_value=None,
        new_value=None,
        confidence=None,
        reason=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return EntityEvent(**defaults)


def _make_job(**overrides):
    from models import Job

    defaults = dict(
        id=str(uuid.uuid4()),
        job_type="classify",
        entity_id=str(uuid.uuid4()),
        payload={},
        status="pending",
        attempts=0,
        max_attempts=3,
        error=None,
        run_after=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Job(**defaults)


# ─── Model construction ──────────────────────────────────────────────────────


class TestEntityConstruction:
    def test_minimal_note(self):
        e = _make_entity(type="note", title=None, content="hello")
        assert e.type == "note"
        assert e.content == "hello"
        assert e.title is None

    def test_task_with_properties(self):
        e = _make_entity(
            type="task",
            title="Fix bug",
            properties={"priority": "high", "due_date": "2026-06-01"},
        )
        assert e.type == "task"
        assert e.properties["priority"] == "high"

    def test_project(self):
        e = _make_entity(type="project", title="Engram v2")
        assert e.type == "project"
        assert e.title == "Engram v2"

    def test_area(self):
        e = _make_entity(type="area", title="Health")
        assert e.type == "area"

    def test_resource(self):
        e = _make_entity(
            type="resource",
            title="Article",
            reference_url="https://example.com",
        )
        assert e.type == "resource"
        assert e.reference_url == "https://example.com"

    def test_person(self):
        e = _make_entity(
            type="person",
            title="Alice",
            properties={"email": "alice@example.com"},
        )
        assert e.type == "person"
        assert e.properties["email"] == "alice@example.com"

    def test_defaults(self):
        e = _make_entity()
        assert e.status == "active"
        assert e.lifecycle == "active"
        assert e.ai_status == "pending"
        assert e.properties == {}
        assert e.ai_meta == {}
        assert e.source == "manual"

    def test_generated_columns_present(self):
        """Generated columns (priority, due_date, bucket, search_vector) are mapped."""
        e = _make_entity(
            type="task",
            properties={"priority": "high"},
        )
        # These columns exist on the model; values come from DB in production
        assert hasattr(e, "priority")
        assert hasattr(e, "due_date")
        assert hasattr(e, "bucket")
        assert hasattr(e, "search_vector")


class TestTagConstruction:
    def test_minimal(self):
        t = _make_tag(name="urgent")
        assert t.name == "urgent"
        assert t.color is None

    def test_with_color(self):
        t = _make_tag(name="bug", color="#ff0000")
        assert t.color == "#ff0000"


class TestEntityTagConstruction:
    def test_minimal(self):
        et = _make_entity_tag()
        assert et.entity_id is not None
        assert et.tag_id is not None


class TestEntityLinkConstruction:
    def test_minimal(self):
        el = _make_entity_link()
        assert el.link_type == "related"
        assert el.weight == 1.0
        assert el.source == "manual"
        assert el.confidence is None

    def test_ai_link(self):
        el = _make_entity_link(
            link_type="parent",
            source="ai",
            confidence=0.95,
            evidence="high confidence parent",
        )
        assert el.source == "ai"
        assert el.confidence == 0.95


class TestEntityChunkConstruction:
    def test_minimal(self):
        c = _make_entity_chunk()
        assert c.chunk_index == 0
        assert c.embedding_model == "text-embedding-3-small"

    def test_with_embedding(self):
        embed = [0.1] * 1536
        c = _make_entity_chunk(embedding=embed)
        assert c.embedding == embed


class TestEntityEventConstruction:
    def test_minimal(self):
        ev = _make_entity_event()
        assert ev.event_type == "created"
        assert ev.actor == "user"

    def test_ai_event(self):
        ev = _make_entity_event(
            event_type="ai_classified",
            actor="agent:classify",
            confidence=0.95,
            new_value={"para_bucket": "PROJECTS"},
        )
        assert ev.actor == "agent:classify"
        assert ev.confidence == 0.95


class TestJobConstruction:
    def test_minimal(self):
        j = _make_job()
        assert j.status == "pending"
        assert j.attempts == 0
        assert j.max_attempts == 3

    def test_failed_job(self):
        j = _make_job(
            status="failed",
            attempts=2,
            error="API timeout",
        )
        assert j.error == "API timeout"


# ─── to_dict() ───────────────────────────────────────────────────────────────


class TestEntityToDict:
    def test_base_fields(self):
        e = _make_entity()
        d = e.to_dict()
        assert d["id"] == e.id
        assert d["type"] == "note"
        assert d["title"] == "Test Note"
        assert d["content"] == "Test content"
        assert d["status"] == "active"
        assert d["lifecycle"] == "active"
        assert d["follow_up_at"] is None
        assert d["source"] == "manual"
        assert d["reference_url"] is None
        assert d["properties"] == {}
        assert d["ai_meta"] == {}
        assert d["ai_status"] == "pending"
        assert "created_at" in d
        assert "updated_at" in d

    def test_tag_ids_and_tags(self):
        tag = _make_tag(name="test")
        e = _make_entity()
        # Simulate loaded relationships
        e._tag_objects = [tag]
        d = e.to_dict()
        assert d["tag_ids"] == [tag.id]
        assert d["tags"] == [{"id": tag.id, "name": tag.name, "color": tag.color}]

    def test_link_count(self):
        e = _make_entity()
        e._link_count = 5
        d = e.to_dict()
        assert d["link_count"] == 5

    def test_backward_compat_raw_text_alias(self):
        """note.raw_text → alias for content."""
        e = _make_entity(type="note", content="hello world")
        d = e.to_dict()
        assert d["raw_text"] == "hello world"

    def test_backward_compat_is_archived_alias(self):
        """note/project.is_archived → lifecycle == 'archived'."""
        e_active = _make_entity(type="note", lifecycle="active")
        e_archived = _make_entity(type="note", lifecycle="archived")
        assert e_active.to_dict()["is_archived"] is False
        assert e_archived.to_dict()["is_archived"] is True

    def test_backward_compat_name_alias(self):
        """project.name → alias for title."""
        e = _make_entity(type="project", title="My Project")
        d = e.to_dict()
        assert d["name"] == "My Project"

    def test_backward_compat_due_date_alias(self):
        """task.due_date → alias for follow_up_at."""
        dt = datetime(2026, 6, 1, tzinfo=timezone.utc)
        e = _make_entity(type="task", follow_up_at=dt)
        d = e.to_dict()
        assert d["due_date"] == dt.isoformat()

    def test_created_at_isoformat(self):
        dt = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
        e = _make_entity(created_at=dt, updated_at=dt)
        d = e.to_dict()
        assert d["created_at"] == "2026-05-11T12:00:00+00:00"

    def test_follow_up_at_isoformat(self):
        dt = datetime(2026, 6, 1, 9, 30, 0, tzinfo=timezone.utc)
        e = _make_entity(follow_up_at=dt)
        d = e.to_dict()
        assert d["follow_up_at"] == "2026-06-01T09:30:00+00:00"

    def test_all_entity_types_to_dict(self):
        for etype in ("note", "task", "project", "area", "resource", "person"):
            e = _make_entity(type=etype, title=f"Test {etype}")
            d = e.to_dict()
            assert d["type"] == etype
            assert d["id"] is not None
            # All should have backward-compat aliases
            if etype == "note":
                assert "raw_text" in d
            if etype in ("note", "project"):
                assert "is_archived" in d
            if etype == "project":
                assert "name" in d
            if etype == "task":
                assert "due_date" in d


class TestTagToDict:
    def test_basic(self):
        t = _make_tag(name="urgent", color="#ff0000")
        d = t.to_dict()
        assert d["id"] == t.id
        assert d["name"] == "urgent"
        assert d["color"] == "#ff0000"

    def test_null_color(self):
        t = _make_tag(name="plain")
        d = t.to_dict()
        assert d["color"] is None


class TestEntityLinkToDict:
    def test_basic(self):
        el = _make_entity_link()
        d = el.to_dict()
        assert d["id"] == el.id
        assert d["src_id"] == el.src_id
        assert d["dst_id"] == el.dst_id
        assert d["link_type"] == "related"
        assert d["weight"] == 1.0
        assert d["source"] == "manual"
        assert d["confidence"] is None
        assert d["evidence"] is None

    def test_ai_link_with_confidence(self):
        el = _make_entity_link(source="ai", confidence=0.87, evidence="similar")
        d = el.to_dict()
        assert d["confidence"] == 0.87
        assert d["evidence"] == "similar"


class TestEntityChunkToDict:
    def test_basic(self):
        c = _make_entity_chunk()
        d = c.to_dict()
        assert d["id"] == c.id
        assert d["entity_id"] == c.entity_id
        assert d["chunk_index"] == 0
        assert d["chunk_text"] == "chunk text"
        assert d["embedding_model"] == "text-embedding-3-small"


class TestEntityEventToDict:
    def test_basic(self):
        ev = _make_entity_event()
        d = ev.to_dict()
        assert d["id"] == ev.id
        assert d["event_type"] == "created"
        assert d["actor"] == "user"
        assert d["old_value"] is None
        assert d["new_value"] is None
        assert d["confidence"] is None
        assert d["reason"] is None

    def test_with_values(self):
        ev = _make_entity_event(
            event_type="status_changed",
            old_value={"status": "pending"},
            new_value={"status": "in_progress"},
            reason="starting work",
        )
        d = ev.to_dict()
        assert d["old_value"] == {"status": "pending"}
        assert d["new_value"] == {"status": "in_progress"}
        assert d["reason"] == "starting work"


class TestJobToDict:
    def test_basic(self):
        j = _make_job()
        d = j.to_dict()
        assert d["id"] == j.id
        assert d["job_type"] == "classify"
        assert d["entity_id"] == j.entity_id
        assert d["payload"] == {}
        assert d["status"] == "pending"
        assert d["attempts"] == 0
        assert d["max_attempts"] == 3
        assert d["error"] is None


# ─── __repr__ ────────────────────────────────────────────────────────────────


class TestRepr:
    def test_entity_repr(self):
        e = _make_entity(type="note", title="Hello")
        r = repr(e)
        assert "Entity" in r
        assert "note" in r

    def test_tag_repr(self):
        t = _make_tag(name="urgent")
        r = repr(t)
        assert "Tag" in r
        assert "urgent" in r

    def test_entity_link_repr(self):
        el = _make_entity_link()
        r = repr(el)
        assert "EntityLink" in r

    def test_entity_chunk_repr(self):
        c = _make_entity_chunk()
        r = repr(c)
        assert "EntityChunk" in r

    def test_entity_event_repr(self):
        ev = _make_entity_event()
        r = repr(ev)
        assert "EntityEvent" in r

    def test_job_repr(self):
        j = _make_job()
        r = repr(j)
        assert "Job" in r

    def test_entity_tag_repr(self):
        et = _make_entity_tag()
        r = repr(et)
        assert "EntityTag" in r
