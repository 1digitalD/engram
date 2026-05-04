import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Table, Enum, Integer
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

from extensions import db


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


# Association tables
note_tags = Table(
    "note_tags",
    db.Model.metadata,
    Column("note_id", String(36), ForeignKey("notes.id"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("tags.id"), primary_key=True),
)


# ─── Base ────────────────────────────────────────────────────────────────────


class BaseModel(db.Model):
    __abstract__ = True

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── Tags ────────────────────────────────────────────────────────────────────


class Tag(BaseModel):
    __tablename__ = "tags"

    name = Column(String(255), unique=True, nullable=False)
    color = Column(String(7), nullable=True)  # hex color

    notes = relationship("Note", secondary=note_tags, back_populates="tags")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "note_count": len(self.notes) if self.notes else 0,
        }


# ─── Projects ────────────────────────────────────────────────────────────────


class Project(BaseModel):
    __tablename__ = "projects"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Enum(Priority), default=Priority.MEDIUM)
    color = Column(String(7), nullable=True)
    deadline = Column(DateTime, nullable=True)
    is_archived = Column(Boolean, default=False)

    notes = relationship("Note", back_populates="project")
    tasks = relationship("Task", back_populates="project")

    def to_dict(self, include_notes=False):
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority.value if self.priority else None,
            "color": self.color,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "is_archived": self.is_archived,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "note_count": len(self.notes) if self.notes else 0,
            "task_count": len(self.tasks) if self.tasks else 0,
        }
        if include_notes:
            d["notes"] = [n.to_dict() for n in (self.notes or [])]
        return d


# ─── Areas ───────────────────────────────────────────────────────────────────


class Area(BaseModel):
    __tablename__ = "areas"

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)

    notes = relationship("Note", back_populates="area")

    def to_dict(self, include_notes=False):
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "note_count": len(self.notes) if self.notes else 0,
        }
        if include_notes:
            d["notes"] = [n.to_dict() for n in (self.notes or [])]
        return d


# ─── People ──────────────────────────────────────────────────────────────────


class Person(BaseModel):
    __tablename__ = "people"

    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    discord_id = Column(String(64), nullable=True)
    notes_text = Column(Text, nullable=True)  # free-form notes about this person
    last_contacted_at = Column(DateTime, nullable=True)

    notes = relationship("Note", back_populates="person")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "discord_id": self.discord_id,
            "notes": self.notes_text,
            "last_contacted_at": self.last_contacted_at.isoformat() if self.last_contacted_at else None,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }


# ─── Notes ──────────────────────────────────────────────────────────────────


class Note(BaseModel):
    __tablename__ = "notes"

    raw_text = Column(Text, nullable=False)
    bucket = Column(Enum(BucketType), default=BucketType.INBOX)
    is_archived = Column(Boolean, default=False)
    ai_meta = Column(JSON, nullable=True)  # { confidence, reasoning, sentiment }

    # Foreign keys
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True)
    area_id = Column(String(36), ForeignKey("areas.id"), nullable=True)
    person_id = Column(String(36), ForeignKey("people.id"), nullable=True)

    # Relationships
    project = relationship("Project", back_populates="notes")
    area = relationship("Area", back_populates="notes")
    person = relationship("Person", back_populates="notes")
    tags = relationship("Tag", secondary=note_tags, back_populates="notes")

    def to_dict(self, include_relations=True):
        d = {
            "id": self.id,
            "raw_text": self.raw_text,
            "bucket": self.bucket.value if self.bucket else BucketType.INBOX.value,
            "is_archived": self.is_archived,
            "ai_meta": self.ai_meta,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "project_id": self.project_id,
            "area_id": self.area_id,
            "person_id": self.person_id,
            "tag_ids": [t.id for t in (self.tags or [])],
            "tag_names": [t.name for t in (self.tags or [])],
        }
        if include_relations:
            d["project"] = self.project.to_dict() if self.project else None
            d["area"] = self.area.to_dict() if self.area else None
            d["person"] = self.person.to_dict() if self.person else None
            d["tags"] = [t.to_dict() for t in (self.tags or [])]
        return d


# ─── Tasks ───────────────────────────────────────────────────────────────────


class Task(BaseModel):
    __tablename__ = "tasks"

    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    priority = Column(Enum(Priority), default=Priority.MEDIUM)
    due_date = Column(DateTime, nullable=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True)

    project = relationship("Project", back_populates="tasks")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value if self.status else TaskStatus.PENDING.value,
            "priority": self.priority.value if self.priority else Priority.MEDIUM.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "project_id": self.project_id,
            "project": self.project.to_dict() if self.project else None,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }


# ─── WeeklySummaries ────────────────────────────────────────────────────────


class WeeklySummary(BaseModel):
    __tablename__ = "weekly_summaries"

    entity_type = Column(String(20), nullable=False)  # 'project' or 'area'
    entity_id = Column(String(36), nullable=False)
    entity_name = Column(String(255), nullable=False)
    week_year = Column(Integer, nullable=False)
    week_number = Column(Integer, nullable=False)
    summary_content = Column(Text, nullable=False)
    note_count = Column(Integer, default=0)
    token_count = Column(Integer, nullable=True)
    is_manually_generated = Column(Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "week_year": self.week_year,
            "week_number": self.week_number,
            "summary_content": self.summary_content,
            "note_count": self.note_count,
            "token_count": self.token_count,
            "is_manually_generated": self.is_manually_generated,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }


# ─── FTS5 Search ─────────────────────────────────────────────────────────────

def init_fts():
    """Create FTS5 virtual table for full-text search on notes."""
    from extensions import db
    conn = db.engine.connect()
    conn.execute(db.text("""
        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            raw_text,
            content='notes',
            content_rowid='rowid'
        )
    """))
    # Triggers to keep FTS in sync
    conn.execute(db.text("""
        CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
            INSERT INTO notes_fts(rowid, raw_text) VALUES (NEW.rowid, NEW.raw_text);
        END
    """))
    conn.execute(db.text("""
        CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
            INSERT INTO notes_fts(notes_fts, rowid, raw_text) VALUES('delete', OLD.rowid, OLD.raw_text);
        END
    """))
    conn.execute(db.text("""
        CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
            INSERT INTO notes_fts(notes_fts, rowid, raw_text) VALUES('delete', OLD.rowid, OLD.raw_text);
            INSERT INTO notes_fts(rowid, raw_text) VALUES (NEW.rowid, NEW.raw_text);
        END
    """))
    conn.commit()
    conn.close()
