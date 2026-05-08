import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Table, Enum, Integer, Float, func, select, event, or_
from sqlalchemy.orm import Session as SaSession
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

note_projects = Table(
    "note_projects",
    db.Model.metadata,
    Column(
        "note_id",
        String(36),
        ForeignKey("notes.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "project_id",
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
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
    color = Column(String(7), nullable=True)

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
    area_id = Column(String(36), ForeignKey("areas.id"), nullable=True)

    notes = relationship(
        "Note",
        secondary=note_projects,
        back_populates="projects",
    )
    tasks = relationship("Task", back_populates="project")
    area = relationship("Area", back_populates="projects")

    def to_dict(self, include_notes=False):
        # Use scalar count queries to avoid loading all related rows
        note_count = db.session.scalar(
            select(func.count())
            .select_from(note_projects)
            .where(note_projects.c.project_id == self.id)
        ) or 0
        task_count = db.session.scalar(
            select(func.count(Task.id)).where(Task.project_id == self.id)
        ) or 0
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority.value if self.priority else None,
            "color": self.color,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "is_archived": self.is_archived,
            "area_id": self.area_id,
            "area_name": self.area.name if self.area else None,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "note_count": note_count,
            "task_count": task_count,
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
    projects = relationship("Project", back_populates="area")
    tasks = relationship("Task", back_populates="area")

    def to_dict(self, include_notes=False):
        note_count = db.session.scalar(
            select(func.count(Note.id)).where(Note.area_id == self.id)
        ) or 0
        project_count = db.session.scalar(
            select(func.count(Project.id)).where(Project.area_id == self.id)
        ) or 0
        task_count = db.session.scalar(
            select(func.count(Task.id)).where(Task.area_id == self.id)
        ) or 0
        d = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "note_count": note_count,
            "project_count": project_count,
            "task_count": task_count,
        }
        if include_notes:
            d["notes"] = [n.to_dict() for n in (self.notes or [])]
        return d


# ─── People ──────────────────────────────────────────────────────────────────


class Person(BaseModel):
    __tablename__ = "people"

    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    # Generic bag for platform-specific identifiers: {"discord": "...", "slack": "...", etc.}
    external_ids = Column(JSON, nullable=True, default=dict)
    notes_text = Column(Text, nullable=True)
    last_contacted_at = Column(DateTime, nullable=True)

    notes = relationship("Note", back_populates="person")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "external_ids": self.external_ids or {},
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
    ai_meta = Column(JSON, nullable=True)

    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True)
    area_id = Column(String(36), ForeignKey("areas.id"), nullable=True)
    person_id = Column(String(36), ForeignKey("people.id"), nullable=True)

    project = relationship(
        "Project",
        foreign_keys=[project_id],
        overlaps="projects,notes",
    )
    projects = relationship(
        "Project",
        secondary=note_projects,
        back_populates="notes",
        overlaps="project",
    )
    area = relationship("Area", back_populates="notes")
    person = relationship("Person", back_populates="notes")
    tags = relationship("Tag", secondary=note_tags, back_populates="notes")
    chunks = relationship("NoteChunk", back_populates="note", cascade="all, delete-orphan")
    outgoing_links = relationship("Link", foreign_keys="Link.src_id", back_populates="source_note", cascade="all, delete-orphan")
    incoming_links = relationship("Link", foreign_keys="Link.dst_id", back_populates="dest_note")
    tasks = relationship("Task", back_populates="source_note", foreign_keys="Task.note_id")

    def to_dict(self, include_relations=True):
        task_count = db.session.scalar(
            select(func.count(Task.id)).where(Task.note_id == self.id)
        ) or 0
        plist = list(self.projects or [])
        by_id = {p.id: p for p in plist}
        primary = self.project_id
        if primary and primary in by_id:
            ordered = [primary] + sorted(
                [p.id for p in plist if p.id != primary],
                key=lambda x: x or "",
            )
        else:
            ordered = sorted(by_id.keys(), key=lambda x: x or "")
        d = {
            "id": self.id,
            "raw_text": self.raw_text,
            "bucket": self.bucket.value if self.bucket else BucketType.INBOX.value,
            "is_archived": self.is_archived,
            "ai_meta": self.ai_meta,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "project_id": self.project_id,
            "project_ids": ordered,
            "area_id": self.area_id,
            "person_id": self.person_id,
            "tag_ids": [t.id for t in (self.tags or [])],
            "tag_names": [t.name for t in (self.tags or [])],
            "link_count": len(self.outgoing_links) + len(self.incoming_links),
            "backlink_count": len(self.incoming_links),
            "task_count": task_count,
        }
        if include_relations:
            d["project"] = self.project.to_dict() if self.project else None
            d["projects"] = [
                p.to_dict() for pid in ordered if (p := by_id.get(pid))
            ]
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
    area_id = Column(String(36), ForeignKey("areas.id"), nullable=True)
    note_id = Column(String(36), ForeignKey("notes.id"), nullable=True)
    # Stable key for markdown checkbox lines (- [ ] / - [x]); only set for extractor-managed tasks
    inline_title_hash = Column(String(64), nullable=True)

    project = relationship("Project", back_populates="tasks")
    area = relationship("Area", back_populates="tasks")
    source_note = relationship("Note", back_populates="tasks", foreign_keys=[note_id])

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value if self.status else TaskStatus.PENDING.value,
            "priority": self.priority.value if self.priority else Priority.MEDIUM.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "project_id": self.project_id,
            "area_id": self.area_id,
            "area_name": self.area.name if self.area else None,
            "note_id": self.note_id,
            "inline_title_hash": self.inline_title_hash,
            "project": self.project.to_dict() if self.project else None,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
        }


# ─── WeeklySummaries ────────────────────────────────────────────────────────


class WeeklySummary(BaseModel):
    __tablename__ = "weekly_summaries"

    entity_type = Column(String(20), nullable=False)
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


# ─── NoteChunk (for embeddings) ─────────────────────────────────────────────


class NoteChunk(BaseModel):
    __tablename__ = "note_chunks"

    note_id = Column(String(36), ForeignKey("notes.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False, default=0)
    chunk_text = Column(Text, nullable=False)
    embedding_model = Column(String(64), nullable=False, default="text-embedding-3-small")

    note = relationship("Note", back_populates="chunks")

    def to_dict(self):
        return {
            "id": self.id,
            "note_id": self.note_id,
            "chunk_index": self.chunk_index,
            "chunk_text": self.chunk_text,
            "embedding_model": self.embedding_model,
            "created_at": self.created_at.isoformat(),
        }


# ─── Links (knowledge graph) ─────────────────────────────────────────────────


class Link(BaseModel):
    __tablename__ = "links"

    src_id = Column(String(36), ForeignKey("notes.id"), nullable=False)
    dst_id = Column(String(36), ForeignKey("notes.id"), nullable=False)
    link_type = Column(String(32), nullable=False, default="related")
    weight = Column(Float, default=1.0)
    source = Column(String(32), nullable=False, default="manual")  # manual|embedding|llm|wikilink

    source_note = relationship("Note", foreign_keys=[src_id], back_populates="outgoing_links")
    dest_note = relationship("Note", foreign_keys=[dst_id], back_populates="incoming_links")

    def to_dict(self):
        return {
            "id": self.id,
            "src_id": self.src_id,
            "dst_id": self.dst_id,
            "link_type": self.link_type,
            "weight": self.weight,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
        }


def _sync_note_projects_m2m(session, note: Note) -> None:
    """Align note_projects rows with scalar project_id and collection order."""
    plist = list(note.projects or [])
    if plist:
        first_id = plist[0].id
        if note.project_id != first_id:
            note.project_id = first_id
        return
    if note.project_id:
        proj = session.get(Project, note.project_id)
        if proj is not None:
            note.projects.append(proj)


@event.listens_for(SaSession, "before_flush")
def _before_flush_note_projects(session, flush_context, instances):
    for obj in session.new.union(session.dirty):
        if isinstance(obj, Note):
            _sync_note_projects_m2m(session, obj)


# ─── FTS5 + sqlite-vec initialization ────────────────────────────────────────

def init_fts(conn=None):
    """Create FTS5 virtual table for full-text search on notes."""
    from extensions import db as _db
    c = conn or _db.engine.connect()

    c.execute(_db.text("""
        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            raw_text,
            content='notes',
            content_rowid='rowid'
        )
    """))
    c.execute(_db.text("""
        CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
            INSERT INTO notes_fts(rowid, raw_text) VALUES (NEW.rowid, NEW.raw_text);
        END
    """))
    c.execute(_db.text("""
        CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
            INSERT INTO notes_fts(notes_fts, rowid, raw_text) VALUES('delete', OLD.rowid, OLD.raw_text);
        END
    """))
    c.execute(_db.text("""
        CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
            INSERT INTO notes_fts(notes_fts, rowid, raw_text) VALUES('delete', OLD.rowid, OLD.raw_text);
            INSERT INTO notes_fts(rowid, raw_text) VALUES (NEW.rowid, NEW.raw_text);
        END
    """))

    if conn is None:
        c.commit()
        c.close()


def init_vec(conn=None):
    """Create sqlite-vec virtual table for vector search on note chunks."""
    from extensions import db as _db
    c = conn or _db.engine.connect()

    try:
        c.execute(_db.text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                chunk_id TEXT PRIMARY KEY,
                embedding FLOAT[1536]
            )
        """))
        if conn is None:
            c.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"sqlite-vec not available, vector search disabled: {e}")
    finally:
        if conn is None:
            try:
                c.close()
            except Exception:
                pass
