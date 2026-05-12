"""Engram v2 — SQLAlchemy models (Postgres-backed).

All seven canonical tables from docs/SCHEMA.sql:
  Entity, EntityLink, EntityTag, EntityChunk, EntityEvent, Job, Tag
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Integer,
    Float,
    Boolean,
    ForeignKey,
    JSON,
    CheckConstraint,
    UniqueConstraint,
    TypeDecorator,
    Text as SqlText,
    Enum as SAEnum,
    event,
    FetchedValue,
    text,
)
from sqlalchemy.orm import relationship

from extensions import db


# ─── Custom Types ────────────────────────────────────────────────────────────


class Vector(TypeDecorator):
    """pgvector VECTOR(1536) — falls back to TEXT when pgvector is unavailable."""

    impl = SqlText
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return f"[{','.join(str(v) for v in value)}]"
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str) and value.startswith("["):
            try:
                return [float(x) for x in value.strip("[]").split(",")]
            except (ValueError, AttributeError):
                return value
        return value


def _enum_values(enum_cls):
    """Return list of enum .value strings for SQLAlchemy Enum column."""
    return [e.value for e in enum_cls]


# ─── Base ────────────────────────────────────────────────────────────────────


class BaseModel(db.Model):
    __abstract__ = True

    id = Column(String(36), primary_key=True, server_default=text("gen_random_uuid()::text"))
    created_at = Column(DateTime, nullable=False, server_default=text("now()"))


# ─── Tags ────────────────────────────────────────────────────────────────────


class Tag(BaseModel):
    __tablename__ = "tags"

    name = Column(Text, nullable=False, unique=True)
    color = Column(Text, nullable=True)
    updated_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    entity_tags = relationship("EntityTag", back_populates="tag")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }

    def __repr__(self):
        return f"<Tag {self.id[:8]} name={self.name!r}>"


# ─── Entity Tags (junction table) ────────────────────────────────────────────


class EntityTag(db.Model):
    __tablename__ = "entity_tags"

    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    entity = relationship("Entity", back_populates="entity_tags")
    tag = relationship("Tag", back_populates="entity_tags")

    def to_dict(self):
        return {
            "entity_id": self.entity_id,
            "tag_id": self.tag_id,
            "created_at": _iso(self.created_at),
        }

    def __repr__(self):
        return f"<EntityTag entity={self.entity_id[:8]} tag={self.tag_id[:8]}>"


# ─── Entity Links ────────────────────────────────────────────────────────────


class EntityLink(BaseModel):
    __tablename__ = "entity_links"
    __table_args__ = (
        UniqueConstraint("src_id", "dst_id", "link_type", name="uq_entity_links_src_dst_type"),
        CheckConstraint("src_id <> dst_id", name="chk_no_self_link"),
    )

    src_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    dst_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    link_type = Column(Text, nullable=False, default="related")
    weight = Column(Float, nullable=False, default=1.0)
    source = Column(Text, nullable=False, default="manual")
    confidence = Column(Float, nullable=True)
    evidence = Column(Text, nullable=True)

    src_entity = relationship("Entity", foreign_keys=[src_id], back_populates="outgoing_links")
    dst_entity = relationship("Entity", foreign_keys=[dst_id], back_populates="incoming_links")

    def to_dict(self):
        return {
            "id": self.id,
            "src_id": self.src_id,
            "dst_id": self.dst_id,
            "link_type": self.link_type,
            "weight": self.weight,
            "source": self.source,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "created_at": _iso(self.created_at),
        }

    def __repr__(self):
        return f"<EntityLink {self.id[:8]} {self.src_id[:8]}→{self.dst_id[:8]} type={self.link_type!r}>"


# ─── Entity Chunks (embeddings) ──────────────────────────────────────────────


class EntityChunk(BaseModel):
    __tablename__ = "entity_chunks"
    __table_args__ = (
        UniqueConstraint("entity_id", "chunk_index", name="uq_entity_chunks_entity_index"),
    )

    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False, default=0)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    embedding_model = Column(Text, nullable=False, default="text-embedding-3-small")

    entity = relationship("Entity", back_populates="chunks")

    def to_dict(self):
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "chunk_index": self.chunk_index,
            "chunk_text": self.chunk_text,
            "embedding_model": self.embedding_model,
            "created_at": _iso(self.created_at),
        }

    def __repr__(self):
        return f"<EntityChunk {self.id[:8]} entity={self.entity_id[:8]} idx={self.chunk_index}>"


# ─── Entity Events (audit log) ───────────────────────────────────────────────


class EntityEvent(BaseModel):
    __tablename__ = "entity_events"

    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(Text, nullable=False)
    actor = Column(Text, nullable=False)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)

    entity = relationship("Entity", back_populates="events")

    def to_dict(self):
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "event_type": self.event_type,
            "actor": self.actor,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "confidence": self.confidence,
            "reason": self.reason,
            "created_at": _iso(self.created_at),
        }

    def __repr__(self):
        return f"<EntityEvent {self.id[:8]} type={self.event_type!r} actor={self.actor!r}>"


# ─── Entity (single-table inheritance) ───────────────────────────────────────


class Entity(BaseModel):
    __tablename__ = "entities"

    # Discriminator
    type = Column(Text, nullable=False)

    # Universal base fields
    title = Column(Text, nullable=True)
    content = Column(Text, nullable=True)

    # Lifecycle
    status = Column(Text, nullable=False, default="active")
    lifecycle = Column(Text, nullable=False, default="active")
    follow_up_at = Column(DateTime, nullable=True)
    source = Column(Text, nullable=True)
    reference_url = Column(Text, nullable=True)

    # Type-specific fields (JSONB)
    properties = Column(JSON, nullable=False, default=dict)

    # AI metadata
    ai_meta = Column(JSON, nullable=False, default=dict)
    ai_status = Column(Text, nullable=False, default="pending")

    # Generated columns (read-only — populated by Postgres)
    priority = Column(Text, nullable=True, server_default=FetchedValue())
    due_date = Column(Text, nullable=True, server_default=FetchedValue())
    bucket = Column(Text, nullable=True, server_default=FetchedValue())
    search_vector = Column(Text, nullable=True, server_default=FetchedValue())

    updated_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    entity_tags = relationship("EntityTag", back_populates="entity", cascade="all, delete-orphan")
    outgoing_links = relationship(
        "EntityLink", foreign_keys="EntityLink.src_id", back_populates="src_entity",
        cascade="all, delete-orphan",
    )
    incoming_links = relationship(
        "EntityLink", foreign_keys="EntityLink.dst_id", back_populates="dst_entity",
    )
    chunks = relationship("EntityChunk", back_populates="entity", cascade="all, delete-orphan")
    events = relationship("EntityEvent", back_populates="entity", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="entity")

    def to_dict(self):
        """Return full API response shape with backward-compat aliases."""
        # Resolve tag data from relationship or test-time attributes
        tag_ids = []
        tags = []
        if hasattr(self, "_tag_objects"):
            tags = [
                {"id": t.id, "name": t.name, "color": t.color}
                for t in self._tag_objects
            ]
            tag_ids = [t.id for t in self._tag_objects]
        elif self.entity_tags:
            for et in self.entity_tags:
                tag_ids.append(et.tag_id)
                if hasattr(et, "tag") and et.tag:
                    tags.append({"id": et.tag.id, "name": et.tag.name, "color": et.tag.color})

        # Link count from relationship or test-time attribute
        link_count = getattr(self, "_link_count", None)
        if link_count is None:
            link_count = (
                len(self.outgoing_links) + len(self.incoming_links)
                if hasattr(self, "outgoing_links") and hasattr(self, "incoming_links")
                else 0
            )

        d = {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "status": self.status,
            "lifecycle": self.lifecycle,
            "follow_up_at": _iso(self.follow_up_at),
            "source": self.source,
            "reference_url": self.reference_url,
            "properties": self.properties or {},
            "ai_meta": self.ai_meta or {},
            "ai_status": self.ai_status,
            "tag_ids": tag_ids,
            "tags": tags,
            "link_count": link_count,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }

        # ── Backward-compat aliases (Cycle 1 — removed in Cycle 2) ──
        # note.raw_text → alias for content
        d["raw_text"] = self.content

        # note.is_archived / project.is_archived → lifecycle == 'archived'
        d["is_archived"] = self.lifecycle == "archived"

        # project.name → alias for title
        d["name"] = self.title

        # task.due_date → alias for follow_up_at
        d["due_date"] = _iso(self.follow_up_at)

        return d

    def __repr__(self):
        return f"<Entity {self.id[:8]} type={self.type!r} title={self.title!r}>"


# ─── Jobs ────────────────────────────────────────────────────────────────────


class Job(BaseModel):
    __tablename__ = "jobs"

    job_type = Column(Text, nullable=False)
    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=True)
    payload = Column(JSON, nullable=False, default=dict)
    status = Column(Text, nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    error = Column(Text, nullable=True)
    run_after = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    entity = relationship("Entity", back_populates="jobs")

    def to_dict(self):
        return {
            "id": self.id,
            "job_type": self.job_type,
            "entity_id": self.entity_id,
            "payload": self.payload or {},
            "status": self.status,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "error": self.error,
            "run_after": _iso(self.run_after),
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }

    def __repr__(self):
        return f"<Job {self.id[:8]} type={self.job_type!r} status={self.status!r}>"


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _iso(dt):
    """Convert datetime to ISO8601 string, or return None."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


# ─── SQLite/legacy compatibility stubs ───────────────────────────────────────
# Kept so existing API/service imports do not break. These map to the old
# SQLite tables and are superseded by the v2 Entity model above.
# Do NOT use for new code — use Entity + properties instead.


from enum import Enum as PyEnum
from sqlalchemy import Table


class BucketType(PyEnum):
    INBOX = "INBOX"
    PROJECTS = "PROJECTS"
    AREAS = "AREAS"
    RESOURCES = "RESOURCES"
    ARCHIVES = "ARCHIVES"


class Priority(PyEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TaskStatus(PyEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class ResourceType(PyEnum):
    ARTICLE = "ARTICLE"
    BOOK = "BOOK"
    URL = "URL"
    VIDEO = "VIDEO"
    PAPER = "PAPER"
    TOOL = "TOOL"
    OTHER = "OTHER"


class SummaryGranularity(PyEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class LinkProposalStatus(PyEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"


class NoteType(PyEnum):
    NOTE = "NOTE"
    MOC = "MOC"
    DAILY = "DAILY"
    MEETING = "MEETING"
    DECISION = "DECISION"


# Legacy association tables
note_tags = Table(
    "note_tags",
    db.Model.metadata,
    Column("note_id", String(36), ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

note_projects = Table(
    "note_projects",
    db.Model.metadata,
    Column("note_id", String(36), ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("project_id", String(36), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
)

resource_tags = Table(
    "resource_tags",
    db.Model.metadata,
    Column("resource_id", String(36), ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Note(BaseModel):
    __tablename__ = "notes"
    raw_text = Column(Text, nullable=False)
    bucket = Column(SAEnum(BucketType, values_callable=_enum_values), default=BucketType.INBOX)
    note_type = Column(SAEnum(NoteType, values_callable=_enum_values), default=NoteType.NOTE, nullable=False)
    is_archived = Column(Boolean, default=False)
    ai_meta = Column(JSON, nullable=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True)
    area_id = Column(String(36), ForeignKey("areas.id"), nullable=True)
    person_id = Column(String(36), ForeignKey("people.id"), nullable=True)
    modified_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    projects = relationship("Project", secondary=note_projects, backref="notes_m2m")
    tags = relationship("Tag", secondary=note_tags, backref="notes")
    area = relationship("Area", backref="notes")
    person = relationship("Person", backref="notes")

    def to_dict(self, include_relations=True):
        d = {
            "id": self.id, "raw_text": self.raw_text,
            "bucket": self.bucket.value if hasattr(self.bucket, "value") else self.bucket,
            "note_type": self.note_type.value if hasattr(self.note_type, "value") else self.note_type,
            "is_archived": self.is_archived, "ai_meta": self.ai_meta,
            "created_at": _iso(self.created_at), "modified_at": _iso(self.modified_at) if hasattr(self, "modified_at") else None,
            "project_id": self.project_id, "area_id": self.area_id, "person_id": self.person_id,
            "task_count": Task.query.filter_by(note_id=self.id).count(),
        }
        if include_relations:
            # project_ids / projects from note_projects association or project_id
            pids = []
            projs = []
            if hasattr(self, "projects") and self.projects:
                for p in self.projects:
                    if p.id not in pids:
                        pids.append(p.id)
                        projs.append({"id": p.id, "name": p.name})
            elif self.project_id and self.project_id not in pids:
                pids.append(self.project_id)
                p = db.session.get(Project, self.project_id)
                if p:
                    projs.append({"id": p.id, "name": p.name})
            d["project_ids"] = pids
            d["projects"] = projs
            # tag_ids / tags
            tids = [t.id for t in getattr(self, "tags", [])]
            tdata = [{"id": t.id, "name": t.name, "color": t.color} for t in getattr(self, "tags", [])]
            d["tag_ids"] = tids
            d["tags"] = tdata
        return d

    def __repr__(self):
        return f"<Note {self.id[:8]}>"


# Sync note.project_id when note.projects collection changes
@event.listens_for(Note.projects, "append")
def _note_projects_append(note, project, initiator):
    if not note.project_id:
        note.project_id = project.id


@event.listens_for(Note.projects, "remove")
def _note_projects_remove(note, project, initiator):
    if note.project_id == project.id:
        note.project_id = note.projects[0].id if note.projects else None


@event.listens_for(Note.projects, "set")
def _note_projects_set(note, projects, old_projects, initiator):
    if projects:
        note.project_id = projects[0].id
    else:
        note.project_id = None


class Project(BaseModel):
    __tablename__ = "projects"
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(SAEnum(Priority, values_callable=_enum_values), default=Priority.MEDIUM)
    color = Column(Text, nullable=True)
    deadline = Column(DateTime, nullable=True)
    is_archived = Column(Boolean, default=False)
    area_id = Column(String(36), ForeignKey("areas.id"), nullable=True)
    modified_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    area = relationship("Area", backref="projects")

    @property
    def notes(self):
        """Combine notes linked via project_id scalar and note_projects M2M."""
        by_fk = Note.query.filter_by(project_id=self.id).all()
        by_m2m = list(getattr(self, "notes_m2m", []))
        seen = {n.id for n in by_fk}
        for n in by_m2m:
            if n.id not in seen:
                by_fk.append(n)
                seen.add(n.id)
        return by_fk

    def to_dict(self, include_notes=False):
        d = {"id": self.id, "name": self.name,
                "priority": self.priority.value if hasattr(self.priority, "value") else self.priority,
                "is_archived": self.is_archived, "area_id": self.area_id,
                "color": self.color, "description": self.description}
        if self.area:
            d["area_name"] = self.area.name
        if include_notes:
            # Include notes linked via project_id scalar or note_projects M2M
            notes_by_fk = Note.query.filter_by(project_id=self.id).all()
            d["notes"] = [n.to_dict(include_relations=False) for n in notes_by_fk]
        return d

    def __repr__(self):
        return f"<Project {self.id[:8]}>"


class Area(BaseModel):
    __tablename__ = "areas"
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    color = Column(Text, nullable=True)

    def to_dict(self, include_notes=False):
        d = {"id": self.id, "name": self.name, "description": self.description,
             "color": self.color,
             "project_count": Project.query.filter_by(area_id=self.id).count(),
             "task_count": Task.query.filter_by(area_id=self.id).count()}
        if include_notes:
            d["resource_count"] = Resource.query.filter_by(area_id=self.id).count()
        return d

    def __repr__(self):
        return f"<Area {self.id[:8]}>"


class Resource(BaseModel):
    __tablename__ = "resources"
    title = Column(Text, nullable=False)
    resource_type = Column(SAEnum(ResourceType, values_callable=_enum_values), default=ResourceType.OTHER)
    url = Column(Text, nullable=True)
    author = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    my_notes = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    rating = Column(Integer, nullable=True)
    area_id = Column(String(36), ForeignKey("areas.id"), nullable=True)
    modified_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tags = relationship("Tag", secondary=resource_tags, backref="resources")
    area = relationship("Area", backref="resources")

    def to_dict(self, include_relations=True):
        d = {"id": self.id, "title": self.title,
             "resource_type": self.resource_type.value if hasattr(self.resource_type, "value") else self.resource_type,
             "url": self.url, "author": self.author, "description": self.description,
             "my_notes": self.my_notes, "is_read": self.is_read, "rating": self.rating,
             "area_id": self.area_id, "published_at": _iso(self.published_at)}
        if include_relations:
            d["tag_ids"] = [t.id for t in getattr(self, "tags", [])]
            d["tags"] = [{"id": t.id, "name": t.name, "color": t.color} for t in getattr(self, "tags", [])]
        return d

    def __repr__(self):
        return f"<Resource {self.id[:8]}>"


class Person(BaseModel):
    __tablename__ = "people"
    name = Column(Text, nullable=False)
    email = Column(Text, nullable=True)
    external_ids = Column(JSON, nullable=True, default=dict)
    notes_text = Column(Text, nullable=True)
    last_contacted_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name}

    def __repr__(self):
        return f"<Person {self.id[:8]}>"


class Task(BaseModel):
    __tablename__ = "tasks"
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(TaskStatus, values_callable=_enum_values), default=TaskStatus.PENDING)
    priority = Column(SAEnum(Priority, values_callable=_enum_values), default=Priority.MEDIUM)
    due_date = Column(DateTime, nullable=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True)
    area_id = Column(String(36), ForeignKey("areas.id"), nullable=True)
    note_id = Column(String(36), ForeignKey("notes.id"), nullable=True)
    inline_title_hash = Column(String(64), nullable=True)
    modified_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    project = relationship("Project", backref="tasks")
    area = relationship("Area", backref="tasks")
    note = relationship("Note", backref="tasks")
    source_note = relationship("Note", foreign_keys=[note_id], overlaps="note")

    def to_dict(self):
        d = {"id": self.id, "title": self.title, "description": self.description,
                "status": self.status.value if hasattr(self.status, "value") else self.status,
                "priority": self.priority.value if hasattr(self.priority, "value") else self.priority,
                "due_date": _iso(self.due_date) if self.due_date else None,
                "project_id": self.project_id, "area_id": self.area_id,
                "note_id": self.note_id, "inline_title_hash": self.inline_title_hash,
                "created_at": _iso(self.created_at),
                "modified_at": _iso(self.modified_at) if hasattr(self, "modified_at") else None}
        if self.area:
            d["area_name"] = self.area.name
        return d

    def __repr__(self):
        return f"<Task {self.id[:8]}>"


class Summary(BaseModel):
    __tablename__ = "summaries"
    note_id = Column(String(36), nullable=False)
    area_id = Column(String(36), nullable=True)
    summary_text = Column(Text, nullable=False)
    generated_at = Column(DateTime, nullable=False)
    summary_type = Column(Text, nullable=True)
    granularity = Column(SAEnum(SummaryGranularity, values_callable=_enum_values), default=SummaryGranularity.WEEKLY, nullable=False)
    date_from = Column(DateTime, nullable=True)
    date_to = Column(DateTime, nullable=True)
    key_themes = Column(JSON, nullable=True)
    action_items = Column(JSON, nullable=True)
    entity_type = Column(Text, nullable=True)

    def to_dict(self):
        return {"id": self.id, "summary_text": self.summary_text,
                "note_id": self.note_id, "area_id": self.area_id,
                "summary_type": self.summary_type,
                "granularity": self.granularity.value if hasattr(self.granularity, "value") else self.granularity,
                "date_from": _iso(self.date_from), "date_to": _iso(self.date_to),
                "key_themes": self.key_themes, "action_items": self.action_items,
                "entity_type": self.entity_type,
                "generated_at": _iso(self.generated_at),
                "created_at": _iso(self.created_at)}

    def __repr__(self):
        return f"<Summary {self.id[:8]}>"


class NoteChunk(BaseModel):
    __tablename__ = "note_chunks"
    note_id = Column(String(36), nullable=False)
    chunk_index = Column(Integer, nullable=False, default=0)
    chunk_text = Column(Text, nullable=False)
    embedding_model = Column(Text, nullable=False, default="text-embedding-3-small")

    def to_dict(self):
        return {"id": self.id, "note_id": self.note_id, "chunk_text": self.chunk_text}

    def __repr__(self):
        return f"<NoteChunk {self.id[:8]}>"


class Link(BaseModel):
    __tablename__ = "links"
    src_id = Column(String(36), nullable=False)
    dst_id = Column(String(36), nullable=False)
    link_type = Column(Text, nullable=False, default="related")
    weight = Column(Float, default=1.0)
    source = Column(Text, nullable=False, default="manual")

    def to_dict(self):
        return {"id": self.id, "src_id": self.src_id, "dst_id": self.dst_id,
                "link_type": self.link_type, "weight": self.weight, "source": self.source,
                "created_at": _iso(self.created_at)}

    def __repr__(self):
        return f"<Link {self.id[:8]}>"


class LinkProposal(BaseModel):
    __tablename__ = "link_proposals"
    src_id = Column(String(36), nullable=False)
    dst_id = Column(String(36), nullable=False)
    confidence = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(SAEnum(LinkProposalStatus, values_callable=_enum_values), default=LinkProposalStatus.PENDING, nullable=False)

    def to_dict(self):
        return {"id": self.id, "src_id": self.src_id, "dst_id": self.dst_id,
                "status": self.status.value if hasattr(self.status, "value") else self.status,
                "confidence": self.confidence, "reason": self.reason,
                "created_at": _iso(self.created_at)}

    def __repr__(self):
        return f"<LinkProposal {self.id[:8]}>"


# ─── SQLite/FTS stubs (kept for app.py imports) ─────────────────────────────


def init_fts(conn=None):
    """No-op stub — FTS is now a Postgres generated column."""
    pass


def init_vec(conn=None):
    """No-op stub — vector search is now pgvector HNSW index."""
    pass
