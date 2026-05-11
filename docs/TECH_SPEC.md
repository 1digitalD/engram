# Engram — Technical Specification
> Version 2.0 | Read alongside docs/PRD.md and docs/SCHEMA.sql

---

## Stack

| Layer | Choice | Rationale |
|---|---|---|
| Database | PostgreSQL 16 + pgvector | Production-grade vector search (HNSW), real FK constraints, JSONB, FTS as generated column |
| ORM | SQLAlchemy 2.x | Same as current, models rewritten for new schema |
| Backend | Flask + flask-openapi3 | Unchanged |
| AI extraction | OpenAI GPT-4o (temp=0) | Structured outputs via Pydantic |
| Embeddings | OpenAI text-embedding-3-small (1536d) | Same as current |
| Audio | OpenAI Whisper | Unchanged |
| Summarization | Anthropic claude-sonnet-4-6 | Unchanged |
| Frontend | React 18 + Vite + Zustand | Unchanged |
| Editor | TipTap 2 | Replaces textarea, live markdown |
| Drag-and-drop | dnd-kit | Kanban task board |

---

## Architecture

```
Browser / MCP Agent
       │
       ▼
Flask REST API (/api/v1/*)
       │
  ┌────┴────────────────────┐
  │   Service Layer         │
  │  entity_service         │  ← all entity CRUD + lifecycle
  │  link_service           │  ← entity_links CRUD + cascade delete
  │  search_service         │  ← hybrid FTS + vector
  │  ai_pipeline            │  ← classify, extract, embed (writes to jobs table)
  │  job_worker             │  ← polling loop, runs queued jobs
  └────────────────────────┘
       │
       ▼
  PostgreSQL (entities, entity_links, entity_tags,
              entity_chunks, entity_events, jobs, tags)
```

The API layer calls services only. Services call the DB directly via SQLAlchemy. No business logic in API handlers.

---

## Database — Key Design Decisions

### Single-table inheritance for entities
All entity types live in the `entities` table. The `type` column discriminates. Type-specific fields are stored in `properties JSONB`. Frequently queried type-specific fields are promoted to **generated columns** with indexes.

```sql
-- Example generated columns (defined in SCHEMA.sql)
priority  GENERATED ALWAYS AS (properties->>'priority') STORED
due_date  GENERATED ALWAYS AS ((properties->>'due_date')::timestamptz) STORED
bucket    GENERATED ALWAYS AS (properties->>'bucket') STORED
```

This means:
- `WHERE type = 'task' AND priority = 'HIGH'` uses an index
- Adding a new entity type requires zero schema migration
- Cross-type queries are single table scans

### FTS via generated tsvector column
```sql
search_vector GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(content, '')), 'B')
) STORED
```
GIN-indexed. No triggers. Automatically stays in sync. Covers all entity types.

### Vector search via pgvector HNSW
`entity_chunks.embedding VECTOR(1536)` with `USING hnsw (embedding vector_cosine_ops)`.
HNSW index means ANN search stays fast as the dataset grows. Supports filtered search: `WHERE entity_id IN (SELECT id FROM entities WHERE type = 'note')`.

### Relationships as data
`entity_links(src_id, dst_id, link_type)` with real FK constraints to `entities.id`. A `UNIQUE(src_id, dst_id, link_type)` constraint prevents duplicate links. A `CHECK(src_id != dst_id)` prevents self-links.

**Cardinality enforcement** for `parent` links is done at the service layer:
```python
# link_service.py — before creating a 'parent' link
if link_type == 'parent':
    existing = EntityLink.query.filter_by(src_id=src_id, link_type='parent').first()
    if existing:
        raise ValueError("entity already has a parent")
```

---

## Service Layer Contracts

### entity_service.py
```python
create_entity(type, title, content, properties, source, actor) -> Entity
    # Creates entity, writes entity_events('created'), enqueues classify+embed jobs

update_entity(entity_id, fields, actor) -> Entity
    # Updates fields, writes entity_events('field_updated') for each changed field

transition_status(entity_id, new_status, actor, reason=None) -> Entity
    # Validates transition via VALID_TRANSITIONS[type][current_status]
    # Raises ValueError on invalid transition
    # Writes entity_events('status_changed')

archive_entity(entity_id, actor) -> Entity
    # Sets lifecycle='archived', writes entity_events('archived')

delete_entity(entity_id, cascade_orphans=False) -> dict
    # Returns {deleted: [ids], blocked: [ids]} preview if cascade_orphans=False
    # Executes deletion if cascade_orphans=True
```

**VALID_TRANSITIONS** (enforced in service, not DB):
```python
VALID_TRANSITIONS = {
    "task":     {"pending": ["in_progress","done","cancelled"],
                 "in_progress": ["pending","done","cancelled"],
                 "done": ["pending"], "cancelled": ["pending"]},
    "project":  {"active": ["on_hold","completed","cancelled"],
                 "on_hold": ["active","cancelled"],
                 "completed": ["active"], "cancelled": ["active"]},
    "note":     {"active": ["archived"], "archived": ["active"]},
    "area":     {"active": ["archived"], "archived": ["active"]},
    "resource": {"active": ["archived"], "archived": ["active"]},
    "person":   {"active": ["archived"], "archived": ["active"]},
}
```

### link_service.py
```python
create_link(src_id, dst_id, link_type, source, confidence, evidence, actor) -> EntityLink
    # Enforces parent cardinality constraint
    # Writes entity_events('link_added') on both entities

delete_link(link_id, actor) -> None
    # Writes entity_events('link_removed') on both entities

get_links(entity_id, direction='both', link_types=None) -> list[EntityLink]

delete_preview(entity_id) -> {entity, safe_to_cascade: [ids], blocked: [ids]}
    # safe_to_cascade: linked entities with no other connections
    # blocked: linked entities connected elsewhere (will not be deleted)
```

### ai_pipeline.py
```python
enqueue_classify(entity_id) -> Job
enqueue_embed(entity_id) -> Job
enqueue_autolink(entity_id) -> Job

# Called by job worker, not directly by API:
run_classify(entity_id) -> None
    # Calls extract() with temperature=0
    # Applies results via entity_service + link_service
    # Writes entity_events('ai_classified') with confidence
    # If confidence < 0.92 for new entity creation: stores in ai_meta only

run_embed(entity_id) -> None
    # Chunks content, generates embeddings, upserts entity_chunks

run_autolink(entity_id) -> None
    # Finds semantically similar entities via pgvector
    # Creates entity_links with source='embedding', confidence=score
```

### search_service.py
```python
search(query, limit=20, mode='hybrid', filters={}) -> list[Entity]
    # mode: 'hybrid' | 'fts' | 'semantic'
    # filters: type, status, lifecycle, area_id (via entity_links)
    # hybrid: RRF fusion of FTS (tsvector) + vector (pgvector)

find_related(entity_id, limit=5, exclude_linked=True) -> list[Entity]
    # Semantic similarity via entity_chunks embeddings
    # Used for proactive surfacing on entity open
```

### job_worker.py
```python
# Runs as a background thread (or separate process) on app start
# Polls jobs table every 5 seconds
# Picks up pending/failed jobs where run_after <= now() and attempts < max_attempts
# Marks running, executes, marks done or failed with error
# Exponential backoff: run_after = now() + 2^attempts * 10 seconds
```

---

## AI Pipeline Design

### Capture flow (synchronous part — fast)
```
POST /notes (or /ingest)
  → entity_service.create_entity(type='note', ...)
  → entity written to DB immediately
  → enqueue_classify(entity_id)
  → enqueue_embed(entity_id)
  → return entity to caller (< 50ms)
```

### Classification job (async — 2-5 seconds)
```
run_classify(entity_id)
  → load entity content
  → call extract(content, existing_projects, existing_areas, temperature=0)
  → for each extracted entity (task, person, tag):
      if existing entity matches (fuzzy ≥ 88%):
          create entity_link (source='ai', confidence=...)
          write entity_event('link_added', actor='agent:classify')
      elif confidence >= 0.92:
          create new entity
          create entity_link
          write entity_event('ai_extracted', actor='agent:classify')
      else:
          store in ai_meta['suggestions'] only
  → update entity.ai_meta with classification result
  → update entity.ai_status = 'done'
  → write entity_event('ai_classified', actor='agent:classify', confidence=...)
```

### Embedding job (async — 1-3 seconds)
```
run_embed(entity_id)
  → load entity (title + content)
  → chunk text (markdown headings + 400-token sliding window, 64-token overlap)
  → for each chunk: generate embedding via OpenAI
  → upsert entity_chunks (delete old, insert new)
```

### Autolink job (async — runs after embed)
```
run_autolink(entity_id)
  → load entity embedding(s)
  → pgvector ANN search: top 10 nearest entity_chunks
  → for each result with cosine_similarity >= 0.82:
      if no existing link between entities:
          create entity_link(src=entity_id, dst=result.entity_id,
                             type='related', source='embedding',
                             confidence=similarity)
          write entity_event('link_added', actor='agent:autolink')
```

---

## Migration from SQLite

Migration script: `scripts/migrate_sqlite_to_postgres.py`

**Field mapping:**

| Source | → entities field |
|---|---|
| notes.raw_text | content |
| notes.bucket | properties.bucket |
| notes.note_type | properties.note_type |
| notes.ai_meta | ai_meta |
| projects.name | title |
| projects.description | content |
| projects.deadline | follow_up_at |
| projects.priority | properties.priority |
| projects.color | properties.color |
| projects.is_archived | lifecycle ('archived' if true) |
| tasks.title | title |
| tasks.description | content |
| tasks.due_date | follow_up_at |
| tasks.status | status (lowercase) |
| tasks.priority | properties.priority |
| tasks.inline_title_hash | properties.inline_title_hash |
| areas.name | title |
| areas.description | content |
| areas.color | properties.color |
| resources.title | title |
| resources.description | content |
| resources.my_notes | appended to content |
| resources.url | reference_url |
| resources.resource_type | properties.resource_type |
| resources.is_read | properties.is_read |
| resources.rating | properties.rating |
| resources.author | properties.author |
| people.name | title |
| people.notes_text | content |
| people.email | properties.email |
| people.external_ids | properties.external_ids |
| people.last_contacted_at | properties.last_contacted_at |

**Relationship mapping:**

| Source | → entity_links |
|---|---|
| tasks.project_id | (task→project, type='parent') |
| tasks.area_id | (task→area, type='parent') |
| tasks.note_id | (task→note, type='derived_from') |
| notes.project_id / note_projects | (note→project, type='related') |
| notes.area_id | (note→area, type='related') |
| notes.person_id | (note→person, type='mentions') |
| projects.area_id | (project→area, type='parent') |
| resources.area_id | (resource→area, type='related') |
| links (note→note) | (note→note, same link_type, source) |
| note_tags | entity_tags |
| resource_tags | entity_tags |

Migration runs in a transaction. Validates row counts before committing.

---

## API Compatibility

All existing route paths and response shapes are preserved in Cycle 1. The `id` fields change from SQLite UUIDs (string) to Postgres UUIDs — same format, no frontend change needed.

New fields added to all entity responses:
- `lifecycle` — string
- `follow_up_at` — ISO datetime or null
- `source` — string or null
- `reference_url` — string or null
- `ai_status` — `pending | processing | done | failed`

Deprecated fields removed after Cycle 2:
- `Note.is_archived` → use `lifecycle == 'archived'`
- `Project.is_archived` → use `lifecycle == 'archived'`

---

## Environment Variables

```bash
# Required
DATABASE_URL=postgresql://engram:engram@localhost:5432/engram
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional
TEST_DATABASE_URL=postgresql://engram:engram@localhost:5432/engram_test
JOB_POLL_INTERVAL=5          # seconds between job queue polls
JOB_MAX_ATTEMPTS=3
CLASSIFY_CONFIDENCE_THRESHOLD=0.70
AUTOLINK_CONFIDENCE_THRESHOLD=0.92  # threshold for new entity creation
EMBED_MODEL=text-embedding-3-small
EMBED_DIMS=1536
```
