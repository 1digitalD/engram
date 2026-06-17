"""Engram v4 SQLAlchemy models for the clean-cutover schema."""

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
        UniqueConstraint(
            "source_entity_id",
            "target_entity_id",
            "relationship_type",
            name="uq_entity_links_source_target_type",
        ),
        CheckConstraint("source_entity_id <> target_entity_id", name="chk_entity_links_no_self_link"),
        CheckConstraint(
            "relationship_type IN ("
            "'parent', 'related', 'derived_from', 'mentions', "
            "'assigned_to', 'references', 'blocks', 'activity_update'"
            ")",
            name="chk_entity_links_relationship_type",
        ),
    )

    source_entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    target_entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    relationship_type = Column(Text, nullable=False, default="related")
    source = Column(Text, nullable=False, default="manual")
    confidence = Column(Float, nullable=True)
    evidence = Column(Text, nullable=True)
    updated_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    source_entity = relationship(
        "Entity", foreign_keys=[source_entity_id], back_populates="outgoing_links"
    )
    target_entity = relationship(
        "Entity", foreign_keys=[target_entity_id], back_populates="incoming_links"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "source_entity_id": self.source_entity_id,
            "target_entity_id": self.target_entity_id,
            "relationship_type": self.relationship_type,
            "source": self.source,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }

    def __repr__(self):
        return (
            f"<EntityLink {self.id[:8]} {self.source_entity_id[:8]}→"
            f"{self.target_entity_id[:8]} type={self.relationship_type!r}>"
        )


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
    source_note_id = Column(String(36), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True)
    reverted_at = Column(DateTime, nullable=True)

    entity = relationship("Entity", back_populates="events", foreign_keys=[entity_id])

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
            "source_note_id": self.source_note_id,
            "reverted_at": _iso(self.reverted_at),
            "created_at": _iso(self.created_at),
        }

    def __repr__(self):
        return f"<EntityEvent {self.id[:8]} type={self.event_type!r} actor={self.actor!r}>"


# ─── Entity (single-table inheritance) ───────────────────────────────────────


class Entity(BaseModel):
    __tablename__ = "entities"
    __table_args__ = (
        CheckConstraint(
            "type IN ('note', 'task', 'project', 'area', 'resource', 'person')",
            name="chk_entities_type",
        ),
        CheckConstraint(
            "lifecycle IN ('active', 'archived', 'deleted')",
            name="chk_entities_lifecycle",
        ),
    )

    # Discriminator
    type = Column(Text, nullable=False)

    # Universal base fields
    title = Column(Text, nullable=True)
    content = Column(Text, nullable=True)

    # Lifecycle
    status = Column(Text, nullable=False, default="active")
    lifecycle = Column(Text, nullable=False, default="active")
    due_at = Column(DateTime, nullable=True)
    follow_up_at = Column(DateTime, nullable=True)
    source = Column(Text, nullable=True)
    reference_url = Column(Text, nullable=True)

    # Type-specific fields (JSONB)
    properties = Column(JSON, nullable=False, default=dict)

    # AI metadata
    ai_meta = Column(JSON, nullable=False, default=dict)
    ai_status = Column(Text, nullable=False, default="pending")
    ai_summary = Column(Text, nullable=True)
    ai_summarized_at = Column(DateTime, nullable=True)

    updated_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    entity_tags = relationship("EntityTag", back_populates="entity", cascade="all, delete-orphan")
    outgoing_links = relationship(
        "EntityLink", foreign_keys="EntityLink.source_entity_id", back_populates="source_entity",
        cascade="all, delete-orphan",
    )
    incoming_links = relationship(
        "EntityLink", foreign_keys="EntityLink.target_entity_id", back_populates="target_entity",
    )
    chunks = relationship("EntityChunk", back_populates="entity", cascade="all, delete-orphan")
    events = relationship(
        "EntityEvent",
        back_populates="entity",
        cascade="all, delete-orphan",
        foreign_keys="EntityEvent.entity_id",
    )
    jobs = relationship("Job", back_populates="entity")

    def to_dict(self):
        """Return the canonical v4 Entity DTO."""
        tags = []
        if hasattr(self, "_tag_objects"):
            tags = [
                {"id": t.id, "name": t.name}
                for t in self._tag_objects
            ]
        elif self.entity_tags:
            for et in self.entity_tags:
                if hasattr(et, "tag") and et.tag:
                    tags.append({"id": et.tag.id, "name": et.tag.name})

        relationship_counts = getattr(self, "_relationship_counts", None)
        if relationship_counts is None:
            relationship_counts = {
                "incoming": len(self.incoming_links) if hasattr(self, "incoming_links") else 0,
                "outgoing": len(self.outgoing_links) if hasattr(self, "outgoing_links") else 0,
            }

        ai_meta = self.ai_meta or {}

        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "status": self.status,
            "lifecycle": self.lifecycle,
            "due_at": _iso(self.due_at),
            "follow_up_at": _iso(self.follow_up_at),
            "source": self.source,
            "reference_url": self.reference_url,
            "properties": self.properties or {},
            "tags": tags,
            "ai": {
                "summary": ai_meta.get("summary"),
                "intent": ai_meta.get("intent"),
                "intent_confidence": ai_meta.get("intent_confidence"),
                "status": self.ai_status,
                "confidence": ai_meta.get("confidence"),
                "review_state": ai_meta.get("review_state"),
                "reviewed_at": ai_meta.get("reviewed_at"),
                "review_resolution": ai_meta.get("review_resolution"),
                "entity_summary": self.ai_summary,
                "entity_summarized_at": _iso(self.ai_summarized_at),
            },
            "relationship_counts": relationship_counts,
            "task_counts": getattr(self, "_task_counts", None) or {"open": 0, "total": 0},
            "projects": getattr(self, "_projects", None) or [],
            "linked_counts": getattr(self, "_linked_counts", None) or {},
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }

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
        payload = dict(self.payload or {})
        payload.pop("_fingerprint", None)
        return {
            "id": self.id,
            "source_entity_id": self.source_entity_id,
            "suggestion_type": self.suggestion_type,
            "operation_type": self.operation_type,
            "payload": payload,
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


# ─── App Settings ────────────────────────────────────────────────────────────


class AppSetting(db.Model):
    """Key/value settings store (owner identity, delegation cadence overrides).

    Table: app_settings
    """

    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "key": self.key,
            "value": self.value,
            "updated_at": _iso(self.updated_at),
        }

    def __repr__(self):
        return f"<AppSetting {self.key!r}>"


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _iso(dt):
    """Convert datetime to UTC ISO8601 string, or return None."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()
