# Engram v2 Architectural Overhaul — Implementation Plan

> Generated: 2026-05-11  
> Status: Ready for execution  
> Prerequisite: Read `docs/PRD.md`, `docs/TECH_SPEC.md`, `docs/SCHEMA.sql`, `docs/API_SPEC.md` before starting any task.

---

## What Was Actually Found

All originally reported gaps confirmed, plus the following additional crashes discovered during deep code audit:

- `services/ingestion.py` calls `embed_note()` and `find_related_note_ids()` — **neither function exists** in `services/embeddings.py`. Ingestion crashes at the background threading step in production right now.
- `services/moc.py` and `services/rollup.py` both call `from api.notes import _queue_embedding` — that function **does not exist** in `api/notes.py`. Both services crash on import.
- `api_v2_bp` is registered in `api/__init__.py` but **zero routes are registered on it**. `GET /api/v2/links/:id` returns 404 in production. The C2-LINKS-API test that "passed" never hit a real endpoint.
- All 362 backend tests ran against `sqlite:///:memory:`. No Postgres-specific feature (pgvector HNSW, tsvector, `FOR UPDATE SKIP LOCKED`, generated columns) has ever been exercised.
- The new `Entity` model, `entity_service`, `ai_pipeline`, and `job_worker` are **dead code in production** — no live endpoint calls them.
- `services/job_worker.py` exists but `start_worker()` is never called from `app.py`.

---

## Old-Model File Inventory

Every file that must be rewritten before old models can be deleted:

| File | Old models imported / used |
|---|---|
| `services/ingestion.py` | `Note`, `BucketType`, `Tag`, `Project`, `Area`, `Person`, `Task`, `Priority`, `TaskStatus` |
| `services/rollup.py` | `BucketType`, `Note`, `Project`, `Tag`, `note_projects` |
| `services/moc.py` | `BucketType`, `Link`, `Note`, `NoteType` |
| `services/link_proposer.py` | `Link`, `Note` — accesses `.raw_text`, `.is_archived`, `.modified_at`, `.tags`, `.projects`, `.area_id`, `.person_id`, `.project_id` |
| `services/summarizer.py` | `Area`, `Note`, `Summary`, `SummaryGranularity` |
| `services/links.py` | `Link` |
| `api/links.py` | `Link`, `Note` |
| `api/batch.py` | `Note`, `BucketType`, `Tag`, `Task`, `TaskStatus` |
| `api/review.py` | `Link`, `Note`, `Project`, `Task` |
| `api/daily.py` | `BucketType`, `Note` |
| `api/summaries.py` | `Summary`, `SummaryGranularity`, `Note`, `Project`, `Area` |
| `api/proposals.py` | `Link`, `LinkProposal`, `LinkProposalStatus` |

Old classes to delete from `models.py` (lines 422–796):
`BucketType`, `Priority`, `TaskStatus`, `ResourceType`, `SummaryGranularity`, `LinkProposalStatus`, `NoteType`, `note_tags`, `note_projects`, `resource_tags`, `Note`, `Project`, `Area`, `Resource`, `Person`, `Task`, `Summary`, `NoteChunk`, `Link`, `LinkProposal`

---

## Dependency Graph

```
Phase 0: 0.1 → 0.2 → 0.3 → 0.4 → 0.5
                          ↓
Phase 1: 1.1 (audit — no code change)
                          ↓
Phase 2: 2.1 (ingestion) → 2.2 (embeddings shim)
                          ↓
Phase 3 (parallelizable, with noted deps):
  3.1 (rollup)
  3.2 (summarizer)      ← after 3.1
  3.3 (extractor stub)  ← after 2.1
  3.4 (api/links.py)    ← after 2.2
  3.5 (moc.py)          ← after 2.1
  3.6 (api/batch.py)    ← after 2.1, 3.3
  3.7 (api/daily.py)    ← after 3.3
  3.8 (api/review.py)
  3.9 (api/summaries.py)
  3.10 (link_proposer)  ← after 2.1, 2.2
  3.11 (api/proposals)  ← after 3.10
                          ↓
Phase 4: 4.1 → 4.2 → 4.3, 4.4 (4.3 and 4.4 parallel)
                          ↓
Phase 5: 5.1 → 5.2 → 5.3 → 5.4
                          ↓
Phase 6: 6.1 → 6.2 → 6.3 → 6.4
```

---

## Phase 0 — Database and Test Infrastructure

> Must complete before any other phase. Everything downstream depends on a working Postgres test environment.

---

### Task 0.1 — Switch config.py to PostgreSQL

**File:** `config.py`

**Changes:**

In `Config` (base class), change the default database URI:
```python
# Before
SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///engram.db")
# After
SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "postgresql://localhost/engram")
```

In `TestingConfig`, replace the SQLite in-memory URI:
```python
# Before
SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
# After
SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "postgresql://localhost/engram_test")
```

Remove `JOBS_SYNC = True` from `TestingConfig` if present — it was a SQLite crutch for synchronous job execution.

**Dependencies:** None.

**Validation:**
```bash
python -c "from config import config; c = config['testing'](); print(c.SQLALCHEMY_DATABASE_URI)"
# Must print: postgresql://localhost/engram_test
```

**Risks:**
- Any test lacking a live Postgres connection will fail immediately. The test database must be created before running the suite. Document: `createdb engram_test && psql engram_test -f docs/SCHEMA.sql`.

---

### Task 0.2 — Rewrite tests/conftest.py for Postgres

**File:** `tests/conftest.py`

**Why this must change:** The current conftest calls `db.create_all()` (SQLAlchemy DDL). This cannot create pgvector HNSW indexes, tsvector generated columns, or the `truncate_all_tables()` function. Only `docs/SCHEMA.sql` creates those. The new conftest must use a session-scoped app (schema applied once) and truncate between tests.

**Replace the entire file with:**
```python
import os
import pytest
from app import create_app
from extensions import db as _db
from sqlalchemy import text

collect_ignore = ["test_mcp_server.py"]


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    with app.app_context():
        # Schema must already be applied via: psql $TEST_DATABASE_URL -f docs/SCHEMA.sql
        # Verify v2 tables exist before running any test
        _db.session.execute(text("SELECT 1 FROM entities LIMIT 0"))
        yield app


@pytest.fixture(scope="session")
def db(app):
    with app.app_context():
        yield _db


@pytest.fixture(autouse=True)
def reset_db(db, app):
    """Truncate all v2 tables before each test to ensure isolation."""
    with app.app_context():
        db.session.execute(text(
            "TRUNCATE entities, entity_links, entity_tags, entity_chunks, "
            "entity_events, jobs, tags RESTART IDENTITY CASCADE"
        ))
        db.session.commit()
    yield


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()
```

**Note on unit tests:** `tests/unit/` tests construct model objects without DB sessions. They use `app` but not `db` or `reset_db`. Session-scoped app means the connection is created once — unit tests still pass.

**Dependencies:** Task 0.1, Task 0.5 (schema applied to `engram_test`).

**Validation:**
```bash
createdb engram_test
psql engram_test -f docs/SCHEMA.sql
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest tests/unit/ -q
# Must pass with zero DB errors
```

---

### Task 0.3 — Clean up app.py: remove SQLite cruft, wire job worker

**File:** `app.py`

**Changes:**

1. Replace `from extensions import db, load_sqlite_extensions` with `from extensions import db`
2. Remove `from models import init_fts, init_vec`
3. Remove the entire sqlite-vec extension loading block:
   ```python
   # DELETE THESE LINES:
   with app.app_context():
       load_sqlite_extensions(db)
   ```
4. After `db.init_app(app)`, add job worker registration and startup:
   ```python
   with app.app_context():
       from services.ai_pipeline import register_handlers
       register_handlers()
       if not app.config.get("TESTING"):
           try:
               from services.job_worker import start_worker
               start_worker(app)
           except Exception as e:
               logger.warning("Job worker failed to start: %s", e)
   ```
5. Replace the `init-db` CLI command body with a Postgres schema apply:
   ```python
   @app.cli.command("init-db")
   def init_db_cmd():
       """Apply docs/SCHEMA.sql to the configured database."""
       import subprocess
       db_url = app.config["SQLALCHEMY_DATABASE_URI"]
       schema = os.path.join(os.path.dirname(__file__), "docs", "SCHEMA.sql")
       result = subprocess.run(["psql", db_url, "-f", schema],
                               capture_output=True, text=True)
       if result.returncode != 0:
           print(f"Schema error:\n{result.stderr}")
       else:
           print("Database schema applied.")
   ```
6. In the `/health` route, replace:
   ```python
   # Before
   db.session.execute(db.text("SELECT * FROM vec_chunks LIMIT 1"))
   status["vec"] = "ok"
   # After
   db.session.execute(db.text("SELECT 1 FROM entity_chunks LIMIT 0"))
   status["pgvector"] = "ok"
   ```
   Rename the key from `"vec"` to `"pgvector"`.

**Dependencies:** Task 0.1.

**Validation:**
```bash
FLASK_ENV=development python -c "from app import create_app; app = create_app(); print('OK')"
```

---

### Task 0.4 — Remove load_sqlite_extensions from extensions.py

**File:** `extensions.py`

**Changes:** Remove the `load_sqlite_extensions` function entirely. The file should contain only:
```python
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()
```

**Dependencies:** Task 0.3 (app.py no longer imports it).

**Validation:**
```bash
python -c "from extensions import db; print(db)"
```

---

### Task 0.5 — Verify schema applies clean; all 7 tables present

**Files:** `docs/SCHEMA.sql` (read-only verification)

**Steps:**
```bash
dropdb engram_test --if-exists
createdb engram_test
psql engram_test -f docs/SCHEMA.sql

# Verify all 7 tables
psql engram_test -c "\dt" | grep -E "entities|entity_links|entity_chunks|entity_events|entity_tags|jobs|tags"

# Verify generated column
psql engram_test -c "\d entities" | grep "search_vector"

# Verify HNSW index
psql engram_test -c "\di" | grep "hnsw"

# Verify pgvector operator works
psql engram_test -c "SELECT '[1,2,3]'::vector <-> '[1,2,3]'::vector;"
# Must return 0
```

**Dependencies:** Tasks 0.1–0.4.

**Known issue — Schema type mismatch:** `models.py` uses `String(36)` for all `id` columns but `docs/SCHEMA.sql` uses `UUID`. Postgres silently casts in most operations, but `gen_random_uuid()` returns a proper UUID that is always exactly 36 characters when cast to text. This works without errors but creates implicit cast warnings in query plans. Fix properly in Task 6.3 by changing SCHEMA.sql to `TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text`.

---

## Phase 1 — Model Audit

### Task 1.1 — Confirm old-model import inventory

**No code changes. Verification only.**

Run this before starting Phase 2 and again before Phase 6:
```bash
grep -rn \
  "from models import.*Note\b\|from models import.*Task\b\|from models import.*Project\b\|from models import.*Area\b\|from models import.*Resource\b\|from models import.*Person\b\|from models import.*Link\b\|from models import.*Summary\b\|from models import.*BucketType\|from models import.*TaskStatus\|from models import.*Priority" \
  . --include="*.py" \
  --exclude-dir=".venv"
```

Expected output before Phase 2: the 12 files listed in the inventory table above.
Expected output after Phase 6: zero results.

---

## Phase 2 — Live Capture Path Migration

> The heart of the overhaul. After this phase, real user capture goes through `entity_service`.

---

### Task 2.1 — Rewrite services/ingestion.py

**File:** `services/ingestion.py`

This is the most complex single rewrite. The current `run_ingestion` function creates `Note`, `Project`, `Area`, `Person`, `Task` old-model records and calls two functions that don't exist (`embed_note`, `find_related_note_ids`), causing a crash. It must be fully rewritten.

**Import changes:**

Remove:
```python
from models import Note, BucketType, Tag, Project, Area, Person, Task
```
Add:
```python
from models import Entity, Tag, EntityTag
from services.entity_service import create_entity
from services.link_service import create_link
```

**Step 2 — Load existing entities:**
```python
# Before
existing_projects = Project.query.filter_by(is_archived=False).all()
existing_areas    = Area.query.all()
existing_people   = Person.query.all()
project_names     = [p.name for p in existing_projects]
area_names        = [a.name for a in existing_areas]

# After
existing_projects = Entity.query.filter_by(type="project", lifecycle="active").all()
existing_areas    = Entity.query.filter_by(type="area").all()
existing_people   = Entity.query.filter_by(type="person").all()
project_names     = [p.title for p in existing_projects]
area_names        = [a.title for a in existing_areas]
```

**`_resolve_entity` helper:** Add an `attr` parameter so it works with `.title` instead of `.name`:
```python
def _resolve_entity(name, existing, attr="title"):
    if not name:
        return None
    name_lower = name.strip().lower()
    for entity in existing:
        if getattr(entity, attr, "").strip().lower() == name_lower:
            return entity
    return None
```
Call as: `_resolve_entity(extraction.suggested_project, existing_projects, attr="title")`

**Auto-create project/area:**
```python
# Before
resolved_project = Project(name=..., description=...)
db.session.add(resolved_project)
db.session.flush()

# After
resolved_project = create_entity(
    entity_type="project",
    title=extraction.suggested_project,
    content=f"Auto-created during ingestion of: {full_content[:80]}",
    source="ai",
    actor="agent:ingest",
)
# create_entity commits internally — no flush needed
```
Apply the same pattern for area auto-creation.

**Person creation:**
```python
person = create_entity(
    entity_type="person",
    title=ep.name,
    properties={"email": ep.email or ""},
    source="ai",
    actor="agent:ingest",
)
```

**Note creation (Step 5):**

Replace `Note(raw_text=..., bucket=..., ...)` with:
```python
properties = {
    "bucket": bucket.value if hasattr(bucket, "value") else str(bucket),
    "source": source,
    "media_type": media_type,
    "media_url": media_url,
}
if resolved_person:
    properties["person_id"] = resolved_person.id
if resolved_area:
    properties["area_id"] = resolved_area.id

note_entity = Entity(
    type="note",
    content=full_content,
    properties=properties,
    source=source,
    ai_meta=ai_meta,
    ai_status="pending",
    status="active",
    lifecycle="active",
)
db.session.add(note_entity)
db.session.flush()
```

Attach tags:
```python
for tag in tag_objects:
    db.session.add(EntityTag(entity_id=note_entity.id, tag_id=tag.id))
```

Link to project/area/people:
```python
if resolved_project:
    create_link(note_entity.id, resolved_project.id,
                link_type="project", source="ai", actor="agent:ingest")
if resolved_area:
    create_link(note_entity.id, resolved_area.id,
                link_type="area", source="ai", actor="agent:ingest")
for person in resolved_people:
    create_link(note_entity.id, person.id,
                link_type="mentions", source="ai", actor="agent:ingest")
```

**Task creation (Step 6):**
```python
task_entity = create_entity(
    entity_type="task",
    title=et.title,
    properties={
        "priority": priority_str,
        "project_id": task_project_id,
    },
    follow_up_at=due,
    source="ai",
    actor="agent:ingest",
)
if task_project_id:
    create_link(task_entity.id, task_project_id,
                link_type="project", source="ai", actor="agent:ingest")
create_link(task_entity.id, note_entity.id,
            link_type="derived_from", source="ai", actor="agent:ingest")
created_tasks.append(task_entity)
```

Remove the `extract_inline_tasks` call entirely (it creates old-model `Task` records; it becomes a no-op stub in Task 3.3).

**Background embed/autolink — replace threading with job queue:**

Remove the entire `threading.Thread` block and the calls to `embed_note` / `find_related_note_ids` (these functions don't exist and cause a crash). Replace with:
```python
from services.ai_pipeline import enqueue_embed, enqueue_autolink
enqueue_embed(note_entity.id)
enqueue_autolink(note_entity.id)
db.session.commit()
```

**Return dict:** Change `"note": note.to_dict()` to `"note": note_entity.to_dict()`. `Entity.to_dict()` returns `raw_text` as a backward-compat alias, so API consumers are unaffected.

**Dependencies:** Phase 0 complete.

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest tests/unit/test_ingestion.py -v
```

Update any test assertions that check `db.session.get(Note, ...)` to use `Entity.query.filter_by(type="note").first()`.

**Risk:** `create_entity` and `create_link` each call `db.session.commit()` internally. One ingest request produces 4–5 commits. This is correct but reduces throughput. Optimize later by adding a `commit=False` parameter.

---

### Task 2.2 — Add missing shims to services/embeddings.py

**File:** `services/embeddings.py`

These functions are called from code that hasn't been migrated yet (Tasks 3.4, 3.10). Without them, imports crash immediately.

Add to the bottom of `services/embeddings.py`:
```python
def embed_note(note_id: str, text: str):
    """Compatibility shim. Delegates to embed_entity."""
    return embed_entity(note_id, text)


def find_related_note_ids(entity_id: str, limit: int = 5, min_similarity: float = 0.80):
    """Compatibility shim. Delegates to services.search.find_related."""
    from services.search import find_related
    return find_related(entity_id, limit=limit)
```

**Dependencies:** None.

**Validation:**
```bash
python -c "from services.embeddings import find_related_note_ids, embed_note; print('OK')"
```

---

## Phase 3 — Old Service Rewrites

> Tasks 3.1–3.11 touch different files and can be parallelized across agents, subject to the dependencies noted per task.

---

### Task 3.1 — Rewrite services/rollup.py

**File:** `services/rollup.py`

**Import changes:**

Remove: `from models import BucketType, Note, Project, Tag, note_projects`

Add:
```python
from models import Entity, EntityTag, EntityLink, Tag
from services.entity_service import create_entity, archive_entity
from services.link_service import create_link
```

**`_notes_for_project(project_id)`:**
```python
def _notes_for_project(project_id: str) -> list:
    linked_ids = (
        db.session.query(EntityLink.src_id)
        .filter(EntityLink.dst_id == project_id, EntityLink.link_type == "project")
        .all()
    )
    ids = [r[0] for r in linked_ids]
    if not ids:
        return []
    return (
        Entity.query
        .filter(Entity.type == "note", Entity.lifecycle != "archived", Entity.id.in_(ids))
        .order_by(Entity.created_at.asc())
        .all()
    )
```

**`rollup_project_to_area`:**
- Replace `db.session.get(Project, project_id)` with `db.session.get(Entity, project_id)`
- Replace `project.area_id` with `(project.properties or {}).get("area_id")`
- Replace `project.name` with `project.title`

**Summary note creation:** Replace `Note(raw_text=..., bucket=..., ...)` with:
```python
summary_entity = create_entity(
    entity_type="note",
    content=raw_text,
    properties={
        "bucket": "AREAS",
        "area_id": area_id,
        "rollup": True,
        "rollup_project_id": project_id,
    },
    source="system",
    actor="system",
)
for tag in tag_objs:
    db.session.add(EntityTag(entity_id=summary_entity.id, tag_id=tag.id))
if area_id:
    create_link(summary_entity.id, area_id,
                link_type="area", source="system", actor="system")
```

**Archive project:** Replace `project.is_archived = True` with `archive_entity(project_id, actor="system")`.

**Remove** `_maybe_queue_embedding` calls — `create_entity` enqueues embed jobs automatically.

**Fix** access to `note.raw_text` throughout: change to `note.content or ""`.

**Dependencies:** Phase 0 complete.

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest tests/test_rollup.py -v
```

---

### Task 3.2 — Rewrite services/summarizer.py

**File:** `services/summarizer.py`

**Dependencies:** Task 3.1.

**Import changes:**

Remove: `from models import Area, Note, Summary, SummaryGranularity`

Add: `from models import Entity, EntityLink, Summary, SummaryGranularity`

**`_format_note_line`:** Change `note.raw_text` to `getattr(note, 'raw_text', None) or getattr(note, 'content', '')`.

**`execute_scheduled_summarization`:**
```python
# Before
areas = Area.query.order_by(Area.name).all()
for area in areas:
    notes = Note.query.filter(Note.area_id == area.id, Note.created_at >= since, ...).all()

# After
areas = Entity.query.filter_by(type="area").order_by(Entity.title).all()
for area in areas:
    linked_note_ids = (
        db.session.query(EntityLink.src_id)
        .filter(EntityLink.dst_id == area.id, EntityLink.link_type == "area")
        .subquery()
    )
    notes = (
        Entity.query
        .filter(Entity.type == "note", Entity.created_at >= since, Entity.id.in_(linked_note_ids))
        .order_by(Entity.created_at.asc())
        .all()
    )
```

Replace `area.name` with `area.title`.

**Note on `Summary` model:** `Summary` is not in `docs/SCHEMA.sql`. Keep it as a legacy model and add it to SCHEMA.sql in Task 6.3. Do not delete it here.

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest -k "summariz" -v
```

---

### Task 3.3 — Stub extract_inline_tasks in services/extractor.py

**File:** `services/extractor.py`

**Dependencies:** Task 2.1.

`extract_inline_tasks` creates old-model `Task` records. Its callers (`api/batch.py`, `api/daily.py`) will be migrated in Tasks 3.6 and 3.7. Until then, replace the body with a no-op:

```python
def extract_inline_tasks(content, project_id=None, area_id=None):
    """Deprecated. Use extract_and_create_inline_tasks instead."""
    import logging
    logging.getLogger(__name__).warning(
        "extract_inline_tasks is deprecated and is now a no-op. "
        "Caller must be migrated to extract_and_create_inline_tasks."
    )
    return []
```

Also add a new replacement function:
```python
def extract_and_create_inline_tasks(entity_id, content, project_entity_id=None):
    """Parse inline tasks from content and create Entity(type='task') records."""
    from services.entity_service import create_entity
    from services.link_service import create_link

    tasks = _parse_task_lines(content)  # existing parser logic, extracted
    created = []
    for t in tasks:
        task = create_entity(
            entity_type="task",
            title=t["title"],
            properties={"priority": t.get("priority", "medium")},
            follow_up_at=t.get("due"),
            source="inline",
            actor="user",
        )
        create_link(task.id, entity_id, link_type="derived_from",
                    source="inline", actor="user")
        if project_entity_id:
            create_link(task.id, project_entity_id, link_type="project",
                        source="inline", actor="user")
        created.append(task)
    return created
```

**Validation:** No direct test — covered by callers' integration tests.

---

### Task 3.4 — Rewrite api/links.py

**File:** `api/links.py`

**Dependencies:** Task 2.2.

**Import changes:**

Remove: `from models import Link, Note`

Add:
```python
from models import Entity, EntityLink
from services.link_service import create_link as svc_create_link, delete_link as svc_delete_link, get_links
```

**`list_links()`:** Replace `Link.query` with `EntityLink.query`.

**`get_note_links(note_id)`:** Replace `db.session.get(Note, note_id)` with `Entity.query.filter_by(id=note_id, type="note").first()`. Use `get_links(note_id)` instead of accessing relationship attributes.

**`get_related_notes(note_id)`:** Replace `db.session.get(Note, note_id)` with `Entity.query.filter_by(id=note_id, type="note").first()`. Replace `find_related_note_ids` call with `from services.search import find_related; find_related(note_id, limit=limit)`.

**`create_link()`:** Replace direct `Link()` instantiation with `svc_create_link(src_id, dst_id, link_type, source="manual")`.

**`delete_link(link_id)`:** Replace `db.session.get(Link, link_id)` with `svc_delete_link(link_id)`.

**Register v2 routes on `api_v2_bp`** (currently defined but has zero routes):

```python
@api_v2_bp.route("/links/<entity_id>", methods=["GET"])
def v2_get_entity_links(entity_id):
    entity = db.session.get(Entity, entity_id)
    if not entity:
        return jsonify({"error": "not found"}), 404

    limit = min(request.args.get("limit", 50, type=int), 500)
    offset = request.args.get("offset", 0, type=int)
    link_type_filter = request.args.get("link_type")

    query = EntityLink.query.filter(
        (EntityLink.src_id == entity_id) | (EntityLink.dst_id == entity_id)
    )
    if link_type_filter:
        query = query.filter(EntityLink.link_type == link_type_filter)

    total = query.count()
    links = (
        query.order_by(EntityLink.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return jsonify({
        "data": [l.to_dict() for l in links],
        "total": total,
        "limit": limit,
        "offset": offset,
    })
```

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest tests/test_links_api.py -v
```

---

### Task 3.5 — Rewrite services/moc.py

**File:** `services/moc.py`

**Dependencies:** Task 2.1.

**Import changes:**

Remove: `from models import BucketType, Link, Note, NoteType`

Add:
```python
from models import Entity, EntityLink, EntityTag, Tag
from services.entity_service import create_entity
from services.link_service import create_link
```

**`generate_map_of_content`:**
- Replace `db.session.get(Note, nid)` with `db.session.get(Entity, nid)`
- Replace `n.raw_text` with `n.content`
- Replace `Note(raw_text=..., bucket=..., note_type=..., area_id=...)` with:
  ```python
  moc_entity = create_entity(
      entity_type="note",
      content=moc_text,
      properties={"bucket": bucket_value, "area_id": area_id, "note_type": "MOC"},
      ai_meta=ai_meta,
      source="llm",
      actor="agent:moc",
  )
  ```
- Replace `Link(src_id=moc.id, dst_id=src, link_type="child_of")` with `create_link(moc_entity.id, src, link_type="child_of", source="llm", actor="agent:moc")`
- Remove all `_maybe_queue_embedding` calls

**Helper functions:**
- `_note_title_line(note)`: change `note.raw_text` to `note.content or ""`
- `_note_excerpt(note)`: change `note.raw_text` to `note.content or ""`
- `_infer_bucket_area(notes)`: change `note.bucket` to `(note.properties or {}).get("bucket", "INBOX")`; change `note.area_id` to `(note.properties or {}).get("area_id")`

**Remove:** `from api.notes import _queue_embedding` — this function does not exist and crashes the import. Replace with the job enqueueing approach (or remove entirely since `create_entity` already enqueues an embed job).

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest -k "moc" -v
```

---

### Task 3.6 — Rewrite api/batch.py

**File:** `api/batch.py`

**Dependencies:** Task 2.1, Task 3.3.

**`_op_create_note`:** Already calls `run_ingestion` — after Task 2.1 that returns Entity-based data. No structural changes needed; verify response shape is correct.

**`_op_get_note`:**

Remove: `from models import Note`

Add: `from models import Entity`

Replace `db.session.get(Note, note_id)` with `Entity.query.filter_by(id=note_id, type="note").first()`.

**`_op_update_note`:**

Replace `db.session.get(Note, note_id)` with `Entity.query.filter_by(id=note_id, type="note").first()`.

Replace `note.raw_text = new_text` with `note.content = new_text`.

Replace bucket update:
```python
# Before
note.bucket = BucketType(body["bucket"].upper())
# After
props = dict(note.properties or {})
props["bucket"] = body["bucket"].upper()
note.properties = props
```

Replace tag manipulation: instead of `note.tags = _resolve_or_create_tags(...)`, use `EntityTag` records directly.

Remove `extract_inline_tasks` call (it's a no-op stub after Task 3.3).

**`_op_create_task`:**

Remove: `from models import Task`

Add: `from services.entity_service import create_entity`

Replace `Task(title=..., ...)` with:
```python
task = create_entity(entity_type="task", title=body["title"],
                     properties={"priority": body.get("priority", "medium")},
                     source="manual", actor="user")
```

**`_op_update_task`:**

Remove: `from models import Task, TaskStatus`

Add: `from models import Entity`, `from services.entity_service import transition_status`

Replace `db.session.get(Task, task_id)` with `Entity.query.filter_by(id=task_id, type="task").first()`.

Replace `task.status = TaskStatus(body["status"].lower())` with `transition_status(task_id, body["status"].lower(), actor="user")`.

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest tests/unit/test_batch_api.py -v
```

---

### Task 3.7 — Rewrite api/daily.py

**File:** `api/daily.py`

**Dependencies:** Task 3.3.

**Import changes:**

Remove: `from models import BucketType, Note`

Add: `from models import Entity`, `from services.entity_service import create_entity`

**`_find_daily_note(date_value)`:**
```python
def _find_daily_note(date_value):
    return (
        Entity.query
        .filter(
            Entity.type == "note",
            Entity.lifecycle == "active",
            Entity.properties.contains({"bucket": "INBOX"}),
            Entity.content.like(f"{DAILY_HEADING_PREFIX}{date_value}%"),
        )
        .order_by(Entity.created_at.asc())
        .first()
    )
```

**`_get_or_create_daily_note(date_value)`:**
```python
entity = create_entity(
    entity_type="note",
    content=_daily_template(date_value),
    properties={"bucket": "INBOX"},
    source="system",
    actor="system",
)
return entity, True
```

**`append_daily_note`:**
- Replace `note.raw_text = ...` with `note.content = ...`
- Remove `extract_inline_tasks` call
- Replace `note.project_id` with `(note.properties or {}).get("project_id")`
- Replace `note.area_id` with `(note.properties or {}).get("area_id")`

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest -k "daily" -v
```

---

### Task 3.8 — Rewrite api/review.py

**File:** `api/review.py`

**Dependencies:** None (queries are simple counts).

**Import changes:**

Remove: `from models import Link, Note, Project, Task`

Add: `from models import Entity, EntityLink`, `from sqlalchemy import func, select`

**`weekly_digest()`:**
```python
notes_count = db.session.scalar(
    select(func.count(Entity.id))
    .where(Entity.type == "note", Entity.created_at >= since)
)
tasks_count = db.session.scalar(
    select(func.count(Entity.id))
    .where(Entity.type == "task", Entity.created_at >= since)
)
links_count = db.session.scalar(
    select(func.count(EntityLink.id))
    .where(EntityLink.created_at >= since)
)
projects_completed = db.session.scalar(
    select(func.count(Entity.id))
    .where(
        Entity.type == "project",
        Entity.lifecycle == "archived",
        Entity.updated_at >= since,
    )
)
```

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest -k "weekly_digest or review" -v
```

---

### Task 3.9 — Rewrite api/summaries.py

**File:** `api/summaries.py`

**Dependencies:** None.

**Import changes:**

Remove: `from models import Summary, SummaryGranularity, Note, Project, Area`

Add: `from models import Summary, SummaryGranularity, Entity, EntityLink`

**`generate_summary()`:**
- Replace `db.session.get(Project, entity_id)` with `Entity.query.filter_by(id=entity_id, type="project").first()`
- Replace `db.session.get(Area, entity_id)` with `Entity.query.filter_by(id=entity_id, type="area").first()`
- Replace `entity.name` with `entity.title`
- Replace `Note.query.filter(Note.project_id == entity_id, ...)`:
  ```python
  linked_note_ids = (
      db.session.query(EntityLink.src_id)
      .filter(EntityLink.dst_id == entity_id, EntityLink.link_type == "project")
      .subquery()
  )
  notes = (
      Entity.query
      .filter(Entity.type == "note", Entity.id.in_(linked_note_ids))
      .order_by(Entity.created_at.desc())
      .limit(limit)
      .all()
  )
  ```
- Replace `n.raw_text` with `n.content`

**`create_summary()` / `patch_summary()`:**
- Replace `db.session.get(Note, note_id)` with `db.session.get(Entity, note_id)`

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest -k "summar" -v
```

---

### Task 3.10 — Rewrite services/link_proposer.py

**File:** `services/link_proposer.py`

**Dependencies:** Task 2.1, Task 2.2.

This is the most attribute-heavy old-model migration. All field access must be translated:

| Old | New |
|---|---|
| `Note.is_archived == False` | `Entity.lifecycle != 'archived'` |
| `Note.modified_at` | `Entity.updated_at` |
| `n.raw_text` | `n.content or ""` |
| `n.tags` (relationship) | batch-loaded via `EntityTag` |
| `n.projects` / `n.project_id` | batch-loaded via `EntityLink(link_type="project")` |
| `n.area_id` | `(n.properties or {}).get("area_id")` |
| `n.person_id` | `(n.properties or {}).get("person_id")` |

**Import changes:**

Remove: `from models import Link, Note`

Add: `from models import Entity, EntityLink, EntityTag`

**Performance — avoid N+1 queries.** Load tags and project links in bulk for the entire pool:
```python
pool_ids = [e.id for e in notes]

# Load tags for all pool entities in 2 queries
tag_rows = (
    db.session.query(EntityTag.entity_id, EntityTag.tag_id)
    .filter(EntityTag.entity_id.in_(pool_ids))
    .all()
)
entity_tags = {}
for entity_id, tag_id in tag_rows:
    entity_tags.setdefault(entity_id, set()).add(tag_id)

# Load project links for all pool entities
project_rows = (
    db.session.query(EntityLink.src_id, EntityLink.dst_id)
    .filter(EntityLink.src_id.in_(pool_ids), EntityLink.link_type == "project")
    .all()
)
entity_projects = {}
for src_id, dst_id in project_rows:
    entity_projects.setdefault(src_id, set()).add(dst_id)
```

Then access via `entity_tags.get(n.id, set())` and `entity_projects.get(n.id, set())` instead of `n.tags` and `n.projects`.

**`_link_exists` check:** Replace `Link.query.filter(...)` with `EntityLink.query.filter(...)`.

**`propose_links` return fields:** Keep `from_note_id` / `to_note_id` keys in the return dict for backward compatibility with callers.

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest tests/test_link_proposer.py -v
```

---

### Task 3.11 — Rewrite api/proposals.py

**File:** `api/proposals.py`

**Dependencies:** Task 3.10.

**`_link_exists`:** Replace `Link.query.filter(...)` with `EntityLink.query.filter(...)`.

**`accept_link_proposal`:** Replace `Link(src_id=..., dst_id=..., ...)` creation with:
```python
from services.link_service import create_link
create_link(proposal.src_id, proposal.dst_id,
            link_type=proposal.link_type, source="ai", actor="user")
```

**Note on `LinkProposal` model:** Keep it as a legacy model for now. Add `link_proposals` table to `docs/SCHEMA.sql` in Task 6.3.

**Import changes:**

Remove: `from models import Link, LinkProposal, LinkProposalStatus`

Add: `from models import EntityLink, LinkProposal, LinkProposalStatus`, `from services.link_service import create_link`

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest -k "proposal" -v
```

---

## Phase 4 — Missing API Endpoints

---

### Task 4.1 — Implement POST /entity-links and DELETE /entity-links/:id

**File:** `api/links.py`

**Dependencies:** Task 3.4.

Add to `api_v2_bp`:

```python
@api_v2_bp.route("/entity-links", methods=["POST"])
def v2_create_entity_link():
    data = request.get_json(silent=True) or {}
    src_id = data.get("src_id")
    dst_id = data.get("dst_id")
    link_type = data.get("link_type", "related")

    if not src_id or not dst_id:
        return jsonify({"error": "src_id and dst_id are required"}), 400

    try:
        from services.link_service import create_link
        link = create_link(
            src_id=src_id,
            dst_id=dst_id,
            link_type=link_type,
            source=data.get("source", "manual"),
            confidence=data.get("confidence"),
            evidence=data.get("evidence"),
            actor="user",
        )
        return jsonify({"data": link.to_dict()}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@api_v2_bp.route("/entity-links/<link_id>", methods=["DELETE"])
def v2_delete_entity_link(link_id):
    try:
        from services.link_service import delete_link
        delete_link(link_id, actor="user")
        return jsonify({"success": True}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
```

**Write tests** in `tests/integration/test_links.py`:
- `POST /api/v2/entity-links` creates a link between two entities
- `POST /api/v2/entity-links` with invalid src_id returns 400
- `POST /api/v2/entity-links` with self-link returns 400
- `POST /api/v2/entity-links` with duplicate link returns 400
- `POST /api/v2/entity-links` parent link enforces cardinality (second parent rejected)
- `DELETE /api/v2/entity-links/:id` removes the link
- `DELETE /api/v2/entity-links/:id` with non-existent id returns 404

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest tests/integration/test_links.py -v
```

---

### Task 4.2 — Implement GET /entities/:id/delete-preview

**File:** `api/links.py` (add to `api_v2_bp`)

**Dependencies:** Task 4.1.

```python
@api_v2_bp.route("/entities/<entity_id>/delete-preview", methods=["GET"])
def v2_delete_preview(entity_id):
    entity = db.session.get(Entity, entity_id)
    if not entity:
        return jsonify({"error": "not found"}), 404
    try:
        from services.link_service import delete_preview
        preview = delete_preview(entity_id)
        return jsonify(preview), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
```

Also wire `DELETE /notes/:id` in `api/notes.py` to use `entity_service.delete_entity`:
```python
@api_bp.route("/notes/<note_id>", methods=["DELETE"])
def delete_note(note_id):
    note = Entity.query.filter_by(id=note_id, type="note").first()
    if not note:
        return jsonify({"error": "not found"}), 404

    cascade = request.args.get("cascade", "false").lower() == "true"
    from services.entity_service import delete_entity, delete_preview as svc_delete_preview
    if not cascade:
        preview = svc_delete_preview(note_id)
        return jsonify(preview), 200
    result = delete_entity(note_id, cascade_orphans=True)
    return jsonify(result), 200
```

Apply the same `delete_entity` wiring to `DELETE /tasks/:id`, `DELETE /projects/:id`, `DELETE /areas/:id`.

**Write tests** in `tests/integration/test_links.py`:
- Entity with no links returns `{safe_to_cascade: [], blocked: []}`
- Entity with orphan-only links returns correct `safe_to_cascade` list
- Entity with shared links returns correct `blocked` list

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest -k "delete_preview" -v
```

---

### Task 4.3 — Implement POST /ai/propose-from-selection

**Files:**
- Create `api/ai_selection.py`
- Update `api/__init__.py`
- Update `ui/src/components/Editor/TipTapEditor.tsx`

**Dependencies:** Phase 0 complete.

**Create `api/ai_selection.py`:**

```python
"""AI selection actions — process selected text from the editor."""

from flask import request, jsonify
from api import api_v2_bp
import logging

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"classify", "extract_task", "create_link", "improve_writing"}


@api_v2_bp.route("/ai/propose-from-selection", methods=["POST"])
def propose_from_selection():
    """
    Process an AI action on selected text from the editor.

    Request body:
        action:        "classify" | "extract_task" | "create_link" | "improve_writing"
        selected_text: str (required)
        entity_id:     str (optional — the entity containing the selection)

    Response:
        { action, result, entity?: {...}, candidates?: [...], meta?: {...} }
    """
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    selected_text = data.get("selected_text", "").strip()
    entity_id = data.get("entity_id")

    if not action or action not in VALID_ACTIONS:
        return jsonify({"error": f"action must be one of: {sorted(VALID_ACTIONS)}"}), 400
    if not selected_text:
        return jsonify({"error": "selected_text is required"}), 400

    try:
        if action == "classify":
            result = _classify_selection(selected_text, entity_id)
        elif action == "extract_task":
            result = _extract_task_from_selection(selected_text, entity_id)
        elif action == "create_link":
            result = _propose_link_from_selection(selected_text, entity_id)
        elif action == "improve_writing":
            result = _improve_writing(selected_text)
        return jsonify({"action": action, **result}), 200
    except Exception as e:
        logger.exception("AI selection action failed: %s", e)
        return jsonify({"error": str(e)}), 500


def _classify_selection(text, entity_id):
    from services.extractor import extract
    extraction = extract(content=text, projects=[], area_names=[])
    return {
        "result": extraction.summary or text,
        "meta": {
            "para_bucket": extraction.para_bucket,
            "confidence": extraction.confidence,
            "tags": extraction.tags,
        },
    }


def _extract_task_from_selection(text, entity_id):
    from services.entity_service import create_entity
    from services.link_service import create_link

    task = create_entity(
        entity_type="task",
        title=text[:200],
        content=text,
        source="selection",
        actor="user",
    )
    if entity_id:
        try:
            create_link(task.id, entity_id, link_type="derived_from",
                        source="manual", actor="user")
        except ValueError:
            pass
    return {"result": f"Task created: {text[:80]}", "entity": task.to_dict()}


def _propose_link_from_selection(text, entity_id):
    from services.search import search
    results = search(text, limit=5, mode="hybrid")
    candidates = [r for r in results if (r.get("id") if isinstance(r, dict) else r.id) != entity_id][:3]
    candidate_dicts = [r if isinstance(r, dict) else r.to_dict() for r in candidates]
    return {
        "result": f"Found {len(candidate_dicts)} potential link candidates.",
        "candidates": candidate_dicts,
    }


def _improve_writing(text):
    import os
    if not os.getenv("OPENAI_API_KEY"):
        return {"result": text, "note": "OPENAI_API_KEY not set — returning original text"}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Improve the clarity and conciseness of the provided text. Return only the improved text."},
                {"role": "user", "content": text},
            ],
            max_tokens=500,
            temperature=0.3,
        )
        return {"result": resp.choices[0].message.content}
    except Exception as e:
        return {"result": text, "error": str(e)}
```

**Update `api/__init__.py`:** Add `from . import ai_selection` to the import block.

**Update `ui/src/components/Editor/TipTapEditor.tsx`:**

Find the `handleAiSelectionAction` function. Currently `callAiAction` is called with `null` as the `apiCall` parameter, falling through to the stub. Replace with a real API call:

```typescript
const handleAiSelectionAction = async (actionId: string) => {
  if (!selectedText) return;

  const apiCall = async (action: string, text: string) => {
    const resp = await fetch('/api/v2/ai/propose-from-selection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action,
        selected_text: text,
        entity_id: noteId,  // prop passed to TipTapEditor
      }),
    });
    if (!resp.ok) throw new Error(`AI action failed: ${resp.statusText}`);
    return resp.json();
  };

  const result = await callAiAction(actionId, selectedText, apiCall);
  // ... rest of existing handler
};
```

**Write tests** in `tests/integration/test_ai_actions.py`:
- `POST /api/v2/ai/propose-from-selection` with `action=extract_task` creates a task entity
- `POST /api/v2/ai/propose-from-selection` with `action=create_link` returns candidates
- `POST /api/v2/ai/propose-from-selection` with missing `selected_text` returns 400
- `POST /api/v2/ai/propose-from-selection` with invalid `action` returns 400

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest tests/integration/test_ai_actions.py -v
cd ui && npm run build
```

---

### Task 4.4 — Wire services/feedback.py into API

**Files:**
- Create `api/feedback.py`
- Update `api/__init__.py`

**Dependencies:** Phase 0 complete.

**Create `api/feedback.py`:**

```python
"""Feedback API — correction signals for AI classification quality."""

from flask import request, jsonify
from api import api_v2_bp
from services.feedback import record_feedback, get_accuracy_stats, get_correction_signals
import logging

logger = logging.getLogger(__name__)


@api_v2_bp.route("/feedback", methods=["POST"])
def submit_feedback():
    """
    Record user feedback on an AI classification.

    Body: { entity_id: str, verdict: "correct"|"incorrect", reason?: str }
    """
    data = request.get_json(silent=True) or {}
    entity_id = data.get("entity_id")
    verdict = data.get("verdict")
    reason = data.get("reason")

    if not entity_id or not verdict:
        return jsonify({"error": "entity_id and verdict are required"}), 400
    if verdict not in ("correct", "incorrect"):
        return jsonify({"error": "verdict must be 'correct' or 'incorrect'"}), 400

    try:
        event = record_feedback(entity_id, verdict, reason)
        return jsonify({"data": event.to_dict()}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@api_v2_bp.route("/feedback/stats", methods=["GET"])
def feedback_stats():
    stats = get_accuracy_stats()
    return jsonify({"data": stats})


@api_v2_bp.route("/feedback/corrections", methods=["GET"])
def feedback_corrections():
    verdict = request.args.get("verdict")
    para_bucket = request.args.get("para_bucket")
    limit = min(request.args.get("limit", 20, type=int), 100)
    signals = get_correction_signals(verdict=verdict, para_bucket=para_bucket, limit=limit)
    return jsonify({"data": signals})
```

**Update `api/__init__.py`:** Add `from . import feedback`.

**Write tests** in `tests/unit/test_feedback.py` (file already exists — extend it):
- `POST /api/v2/feedback` writes an `entity_event` with `event_type='ai_correction'`
- `POST /api/v2/feedback` with missing fields returns 400
- `GET /api/v2/feedback/stats` returns accuracy breakdown
- `GET /api/v2/feedback/corrections` returns correction signals

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest tests/unit/test_feedback.py -v
```

---

## Phase 5 — Postgres-Specific Validation

> Every test in this phase must run against a real Postgres instance. These are the tests that were never run before.

---

### Task 5.1 — Prove tsvector FTS works; fix fragile SQL in search.py

**Files:** `services/search.py`, `tests/integration/test_search_api.py`

**Bug to fix first in `services/search.py`:** The `_fts_only` function uses unsafe string substitution to inject filters:
```python
# BEFORE (fragile — breaks if "LIMIT" appears in any value)
sql = sql.replace("LIMIT", "AND type = :etype LIMIT")
```

Rewrite `_fts_only` with proper parameterized SQL:
```python
def _fts_only(query, limit, filters=None):
    filters = filters or {}
    try:
        where_clauses = [
            "search_vector @@ plainto_tsquery('english', :query)",
            "lifecycle = 'active'",
        ]
        params = {"query": query, "limit": limit}
        if filters.get("type"):
            where_clauses.append("type = :etype")
            params["etype"] = filters["type"]
        if filters.get("status"):
            where_clauses.append("status = :status")
            params["status"] = filters["status"]

        where = " AND ".join(where_clauses)
        sql = f"""
            SELECT id FROM entities
            WHERE {where}
            ORDER BY ts_rank(search_vector, plainto_tsquery('english', :query)) DESC
            LIMIT :limit
        """
        rows = db.session.execute(db.text(sql), params).fetchall()
        entity_ids = [row[0] for row in rows]
        if not entity_ids:
            return []
        entities = Entity.query.filter(Entity.id.in_(entity_ids)).all()
        entities_map = {e.id: e for e in entities}
        return [entities_map[eid] for eid in entity_ids if eid in entities_map]
    except Exception as e:
        logger.error("FTS search error: %s", e)
        return []
```

**Write tests in `tests/integration/test_search_api.py`:**
```python
def test_fts_search_finds_by_title(client, db):
    # Create entity, search by title word
    entity = Entity(type="note", title="pgvector embedding search", content="test")
    db.session.add(entity)
    db.session.commit()
    # Wait for generated column (it's immediate in Postgres)
    results = search("embedding search", mode="fts")
    assert any(r.id == entity.id for r in results)

def test_fts_search_finds_by_content(client, db):
    entity = Entity(type="note", title="untitled", content="HNSW nearest neighbor index")
    db.session.add(entity)
    db.session.commit()
    results = search("nearest neighbor", mode="fts")
    assert any(r.id == entity.id for r in results)

def test_fts_search_type_filter(client, db):
    note = Entity(type="note", title="quarterly planning")
    task = Entity(type="task", title="quarterly review task")
    db.session.add_all([note, task])
    db.session.commit()
    results = search("quarterly", mode="fts", filters={"type": "task"})
    ids = [r.id for r in results]
    assert task.id in ids
    assert note.id not in ids
```

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest tests/integration/test_search_api.py -v -k "fts"
```

---

### Task 5.2 — Prove pgvector HNSW search works

**Files:** `tests/integration/test_search_api.py` (same file)

**Write tests:**
```python
from models import EntityChunk
import pytest

def test_semantic_search_returns_similar_entities(client, db):
    """Semantic search should rank entities by cosine similarity."""
    entity_a = Entity(type="note", title="machine learning model training")
    entity_b = Entity(type="note", title="cooking recipes and ingredients")
    db.session.add_all([entity_a, entity_b])
    db.session.flush()

    # Insert embeddings: entity_a is "near" the query, entity_b is far
    near_vector = [0.9] + [0.0] * 1535     # close to query
    far_vector  = [0.0] * 1535 + [0.9]     # far from query
    db.session.add(EntityChunk(entity_id=entity_a.id, chunk_index=0,
                               text="ml text", embedding=near_vector))
    db.session.add(EntityChunk(entity_id=entity_b.id, chunk_index=0,
                               text="cooking text", embedding=far_vector))
    db.session.commit()

    from unittest.mock import patch
    query_vector = [0.85] + [0.0] * 1535
    with patch("services.embeddings.embed_query", return_value=query_vector):
        results = search("machine learning", mode="semantic", limit=2)

    assert len(results) >= 1
    assert results[0].id == entity_a.id  # more similar should rank first

def test_pgvector_operator_available(db):
    """Verify <-> cosine distance operator works."""
    from sqlalchemy import text
    result = db.session.execute(
        text("SELECT '[1,0,0]'::vector <-> '[1,0,0]'::vector")
    ).scalar()
    assert result == pytest.approx(0.0, abs=1e-6)
```

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest tests/integration/test_search_api.py -v -k "semantic or pgvector"
```

---

### Task 5.3 — Prove FOR UPDATE SKIP LOCKED works; enable concurrent pickup tests

**Files:** `tests/integration/test_jobs.py`

**Change:** Find all `@pytest.mark.skipif(True, reason="SQLite doesn't support concurrent writes")` or `@pytest.mark.skip(reason="...")` decorators on `TestConcurrentPickup` tests. Remove them.

Also verify `_is_postgres()` in `services/job_worker.py` returns `True`:
```python
def test_is_postgres_returns_true_with_postgres_url(app):
    with app.app_context():
        from services.job_worker import _is_postgres
        assert _is_postgres() is True
```

The concurrent pickup test should verify that two simulated workers do not pick up the same job:
```python
def test_skip_locked_prevents_double_pickup(app, db):
    """Two concurrent workers must not pick up the same job."""
    from services.job_worker import get_next_job
    from models import Job

    job = Job(job_type="test", entity_id="test-entity", payload={})
    db.session.add(job)
    db.session.commit()

    # Simulate first worker picking up the job
    job1 = get_next_job()
    assert job1 is not None
    assert job1.id == job.id

    # Second worker should get nothing (job is in-flight)
    job2 = get_next_job()
    assert job2 is None
```

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest tests/integration/test_jobs.py -v
# All tests including formerly-skipped concurrent tests must pass
```

---

### Task 5.4 — Full suite + coverage gate

**Files:** `.coveragerc` (create if missing)

**Create `.coveragerc`:**
```ini
[run]
omit =
    .venv/*
    tests/*
    migrations/*
    scripts/*
    mcp_server/*

[report]
fail_under = 80
include =
    services/*
    api/*
    models.py
```

**Run:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test \
    pytest --cov=. --cov-report=term-missing --cov-config=.coveragerc -q
```

**Done when:** All tests pass. Coverage report shows ≥ 80% for all included paths. No SQLite-related failures.

---

## Phase 6 — Cleanup

---

### Task 6.1 — Delete old model classes from models.py

**File:** `models.py`

**Pre-condition:** Run the old-model import grep (Task 1.1) and confirm zero results before touching this file.

**Delete lines 422–796** (everything from `class BucketType(PyEnum)` onward). This removes:
- Enums: `BucketType`, `Priority`, `TaskStatus`, `ResourceType`, `SummaryGranularity`, `LinkProposalStatus`, `NoteType`
- Association tables: `note_tags`, `note_projects`, `resource_tags`
- Models: `Note`, `Project`, `Area`, `Resource`, `Person`, `Task`, `Summary`, `NoteChunk`, `Link`, `LinkProposal`
- Event listeners: `_note_projects_append`, `_note_projects_remove`, `_note_projects_set`

Also remove `init_fts` and `init_vec` functions (now no-ops after Task 0.3 removed their app.py import).

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://localhost/engram_test pytest -q
# Full suite must still pass after deletion
```

---

### Task 6.2 — Delete dead services

**Files:** `services/links.py`

`services/links.py` only contains `VALID_LINK_TYPES` (no longer imported after Task 3.4) and `create_embedding_links` (removed from ingestion in Task 2.1). Delete the file.

Confirm no remaining imports:
```bash
grep -rn "from services.links import\|from services import links" . --include="*.py" --exclude-dir=".venv"
# Must return zero results
```

**Dependencies:** All Phase 3 tasks complete.

---

### Task 6.3 — Fix SCHEMA.sql: primary key types and missing tables

**File:** `docs/SCHEMA.sql`

1. Change all `UUID PRIMARY KEY DEFAULT gen_random_uuid()` to `TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text` to match `String(36)` in models.py and eliminate implicit cast warnings.

2. Add the `summaries` table (used by `services/summarizer.py` and `api/summaries.py`):
```sql
CREATE TABLE IF NOT EXISTS summaries (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    entity_id   TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    granularity TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS summaries_entity_idx ON summaries (entity_id);
```

3. Add the `link_proposals` table (used by `api/proposals.py`):
```sql
CREATE TABLE IF NOT EXISTS link_proposals (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    src_id      TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    dst_id      TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    link_type   TEXT NOT NULL DEFAULT 'related',
    confidence  FLOAT,
    evidence    TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Re-apply schema to test DB after:
```bash
psql engram_test -f docs/SCHEMA.sql
```

---

### Task 6.4 — Update AGENTS.md and EXECUTION-TRACKER.md

**Files:** `AGENTS.md`, `EXECUTION-TRACKER.md`

In `AGENTS.md`:
- Update the "Working rules" section to note that the SQLite path has been removed
- Remove any reference to `init_fts`, `init_vec`, or sqlite-vec
- Add a note that `pytest` requires `TEST_DATABASE_URL` pointing at a live Postgres instance

In `EXECUTION-TRACKER.md`:
- Mark all cycles as truly complete (with notes about what was corrected)
- Add a "v2 Overhaul Completion" entry with the date

---

## Key Risks Summary

| Risk | Mitigation |
|---|---|
| `create_entity` commits internally — 4–5 commits per ingest | Correct for now. Add `commit=False` param later for batch ingestion. |
| `link_proposer.py` N+1 queries for tags/projects | Fixed in Task 3.10 with bulk batch loading. |
| `Summary` model not in SCHEMA.sql | Added in Task 6.3. Do not delete until Task 6.1. |
| `String(36)` vs `UUID` type mismatch in Postgres | Fixed in Task 6.3. Works without error in the interim. |
| `_fts_only` fragile string-replace SQL | Fixed in Task 5.1 before writing tests. |
| Job worker thread starts immediately in dev | Wrapped in `try/except` with `logger.warning` in Task 0.3. |
| Old-model `test_*` test files may conflict with new conftest | Rename or delete `tests/test_models_legacy.py` and `tests/test_phase1_backend_foundation.py` after Phase 6. |
| `Entity.query.get(id)` deprecated in SQLAlchemy 2.x | Grep for `.query.get(` and replace with `db.session.get(Entity, id)` throughout all changed files. |

---

## Completion Checklist

```
Phase 0: [ ] 0.1  [ ] 0.2  [ ] 0.3  [ ] 0.4  [ ] 0.5
Phase 1: [ ] 1.1
Phase 2: [ ] 2.1  [ ] 2.2
Phase 3: [ ] 3.1  [ ] 3.2  [ ] 3.3  [ ] 3.4  [ ] 3.5
         [ ] 3.6  [ ] 3.7  [ ] 3.8  [ ] 3.9  [ ] 3.10  [ ] 3.11
Phase 4: [ ] 4.1  [ ] 4.2  [ ] 4.3  [ ] 4.4
Phase 5: [ ] 5.1  [ ] 5.2  [ ] 5.3  [ ] 5.4
Phase 6: [ ] 6.1  [ ] 6.2  [ ] 6.3  [ ] 6.4
```

**Done when:**
- `grep` for old-model imports returns zero results
- Full suite passes against Postgres
- Coverage ≥ 80% for `services/` and `api/`
- `app.py` starts cleanly with no sqlite references
- `POST /ingest` writes an `Entity` record to Postgres, not a `Note`
- Job worker starts on app boot and processes the queued classify/embed jobs
- `GET /api/v2/entity-links/:id`, `POST /api/v2/entity-links`, `DELETE /api/v2/entity-links/:id`, `GET /api/v2/entities/:id/delete-preview` all return non-404 responses
- `POST /api/v2/ai/propose-from-selection` returns a result for each of the 4 valid actions

---

## Gap Additions (2026-05-11)

### Task 0.6 — Run migration script against production Postgres

**File:** `scripts/migrate_sqlite_to_postgres.py`

**Steps:**
```bash
# Backup SQLite first
cp instance/engram.db instance/engram.db.v2-overhaul-backup

# Dry run first
python3 scripts/migrate_sqlite_to_postgres.py \
  --sqlite instance/engram.db \
  --database-url "$DATABASE_URL" \
  --dry-run

# Then run for real
python3 scripts/migrate_sqlite_to_postgres.py \
  --sqlite instance/engram.db \
  --database-url "$DATABASE_URL"
```

**Dependencies:** Task 0.5 (schema verified), before Phase 2.

---

### Task 3.12 — Remove/archive old v1 test files

**Files to remove:**
- `tests/test_api.py` (1409 lines of v1 tests)
- `tests/test_phase1_backend_foundation.py`
- `tests/test_rollup.py`
- `tests/test_link_proposer.py`
- `tests/test_models_legacy.py`

Move to `tests/archive/` or delete after confirming no remaining v1 imports.

**Dependencies:** Tasks 3.1–3.11 complete.

---

### Task 5.5 — Frontend build + smoke test against new API

**Steps:**
```bash
cd ui && npm run build
# Verify frontend pages load without console errors
# Manual: visit /notes, /tasks, /projects, /search, /kanban
```

**Dependencies:** Phase 4 complete.

---

### Task 6.5 — Replace Entity.query.get() → db.session.get()

**Find:**
```bash
grep -rn '\.query\.get(' api/ services/ --include="*.py"
```

Replace each with `db.session.get(Entity, id)` pattern.

**Dependencies:** Phase 5 complete, before Phase 6 final validation.
