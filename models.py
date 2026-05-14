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
    ForeignKey,
    JSON,
    CheckConstraint,
    UniqueConstraint,
    TypeDecorator,
    Text as SqlText,
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
    inverse = Column(Text, nullable=True)
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
            "inverse": self.inverse,
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


# ─── Link Type Allowlist (relationship matrix) ──────────────────────────────


class LinkTypeAllowlist(BaseModel):
    """Defines allowed (src_type, dst_type, link_type) triplets with their inverses."""

    __tablename__ = "link_type_allowlist"
    __table_args__ = (
        UniqueConstraint("src_type", "dst_type", "link_type", name="uq_link_type_allowlist"),
    )

    src_type = Column(Text, nullable=False)
    dst_type = Column(Text, nullable=False)
    link_type = Column(Text, nullable=False)
    inverse = Column(Text, nullable=False)

    @staticmethod
    def is_allowed(src_type, dst_type, link_type):
        return db.session.query(
            db.session.query(LinkTypeAllowlist).filter_by(
                src_type=src_type, dst_type=dst_type, link_type=link_type
            ).exists()
        ).scalar()

    @staticmethod
    def get_inverse(src_type, dst_type, link_type):
        row = LinkTypeAllowlist.query.filter_by(
            src_type=src_type, dst_type=dst_type, link_type=link_type
        ).first()
        return row.inverse if row else None

    @staticmethod
    def get_allowed_types(src_type, dst_type):
        rows = LinkTypeAllowlist.query.filter_by(
            src_type=src_type, dst_type=dst_type
        ).all()
        return [{"link_type": r.link_type, "inverse": r.inverse} for r in rows]

    def to_dict(self):
        return {
            "id": self.id,
            "src_type": self.src_type,
            "dst_type": self.dst_type,
            "link_type": self.link_type,
            "inverse": self.inverse,
            "created_at": _iso(self.created_at),
        }

    def __repr__(self):
        return f"<LinkTypeAllowlist {self.src_type}→{self.dst_type} type={self.link_type!r}>"


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
        tag_names = []
        tags = []
        if hasattr(self, "_tag_objects"):
            tags = [
                {"id": t.id, "name": t.name, "color": t.color}
                for t in self._tag_objects
            ]
            tag_ids = [t.id for t in self._tag_objects]
            tag_names = [t.name for t in self._tag_objects]
        elif self.entity_tags:
            for et in self.entity_tags:
                tag_ids.append(et.tag_id)
                if hasattr(et, "tag") and et.tag:
                    tag_names.append(et.tag.name)
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
            "bucket": (self.properties or {}).get("bucket"),
            "follow_up_at": _iso(self.follow_up_at),
            "source": self.source,
            "reference_url": self.reference_url,
            "properties": self.properties or {},
            "ai_meta": self.ai_meta or {},
            "ai_status": self.ai_status,
            "tag_ids": tag_ids,
            "tag_names": tag_names,
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


# ─── AiSuggestion ────────────────────────────────────────────────────────────


class AiSuggestion(BaseModel):
    """AI-generated suggestions that need user review.

    Table: ai_suggestions

    Statuses: pending, accepted, dismissed, edited, expired
    """

    __tablename__ = "ai_suggestions"

    source_entity_id = Column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    suggestion_type = Column(Text, nullable=False)  # link, create_task, create_project, etc.
    operation_type = Column(Text, nullable=False)    # create_new_entity, link_existing, etc.
    payload = Column(JSON, nullable=False, default=dict)
    confidence = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    status = Column(
        Text,
        nullable=False,
        default="pending",
    )  # pending, accepted, dismissed, edited, expired
    resolved_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    source_entity = relationship("Entity", foreign_keys=[source_entity_id])

    def to_dict(self):
        return {
            "id": self.id,
            "source_entity_id": self.source_entity_id,
            "suggestion_type": self.suggestion_type,
            "operation_type": self.operation_type,
            "payload": self.payload or {},
            "confidence": self.confidence,
            "reason": self.reason,
            "status": self.status,
            "resolved_at": _iso(self.resolved_at),
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }

    def __repr__(self):
        return (
            f"<AiSuggestion {self.id[:8] if self.id else '(unsaved)'} "
            f"type={self.suggestion_type!r} op={self.operation_type!r} "
            f"status={self.status!r} conf={self.confidence}>"
        )


# ─── ChangeBatch ─────────────────────────────────────────────────────────────


class ChangeBatch(BaseModel):
    """A batch of AI-applied changes, supporting undo.

    Table: change_batches
    """

    __tablename__ = "change_batches"

    source_note_id = Column(String(36), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True)
    actor = Column(Text, nullable=False)
    source = Column(Text, nullable=False, default="ai")
    summary = Column(Text, nullable=True)
    applied_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    undone_at = Column(DateTime, nullable=True)

    source_note = relationship("Entity", foreign_keys=[source_note_id])

    def to_dict(self):
        return {
            "id": self.id,
            "source_note_id": self.source_note_id,
            "actor": self.actor,
            "source": self.source,
            "summary": self.summary,
            "applied_at": _iso(self.applied_at),
            "undone_at": _iso(self.undone_at),
        }

    def __repr__(self):
        return f"<ChangeBatch {self.id[:8]} actor={self.actor!r}>"


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _iso(dt):
    """Convert datetime to ISO8601 string, or return None."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()
