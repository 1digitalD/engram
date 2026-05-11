# Engram v2 — Agent Execution Plan
> Multi-agent, TDD-first. Read docs/PRD.md + docs/TECH_SPEC.md before starting any task.
> Each task: write tests first → confirm failure → implement → confirm passing → report.

---

## How to Use This Plan

- Tasks within a **parallel block** can be assigned to separate agents simultaneously.
- Tasks in a **sequential block** must complete before the next block starts.
- Each task lists: **reads** (what to study before starting), **writes** (files to touch), **tests** (validation command), **done when** (acceptance criteria).
- File ownership is strict within a cycle. Do not touch files outside your task's **writes** list.
- After completing a task, update `EXECUTION-TRACKER.md` with status and test output.

---

## Cycle 1 — Foundation

### C1-GATE: Infrastructure (must complete first, sequential)

**Task C1-INFRA: Postgres + Docker + Schema**

- **Reads:** `docs/SCHEMA.sql`, `docs/TECH_SPEC.md` (Stack + Environment Variables sections)
- **Writes:**
  - `docker-compose.yml` — add/update Postgres 16 + pgvector service
  - `docker-compose.test.yml` — test DB service on port 5433
  - `.env.example` — updated with `DATABASE_URL`, `TEST_DATABASE_URL`
  - `scripts/apply_schema.sh` — runs `psql $DATABASE_URL -f docs/SCHEMA.sql`
  - `scripts/migrate_sqlite_to_postgres.py` — full migration script (see mapping in TECH_SPEC.md)
- **Tests:** `psql $TEST_DATABASE_URL -c "\dt"` returns all 7 tables. Migration script runs against a copy of the existing SQLite DB without errors. Row counts match pre/post.
- **Done when:** `docker compose up -d` starts Postgres. Schema applies clean. Migration script exits 0 with matching row counts.

---

### C1-PARALLEL-1: Core Backend (run after C1-INFRA, all parallel)

**Task C1-MODELS: SQLAlchemy Models**

- **Reads:** `docs/SCHEMA.sql`, `docs/TECH_SPEC.md`, `models.py` (current, for reference)
- **Writes:**
  - `models.py` — full rewrite: `Entity`, `EntityLink`, `EntityTag`, `EntityChunk`, `EntityEvent`, `Job`, `Tag`
  - `tests/unit/test_models.py` — unit tests for model construction, `to_dict()`, repr
- **Do not touch:** any API file, any service file
- **Tests:** `pytest tests/unit/test_models.py -v`
- **Done when:** All model classes instantiate correctly. `to_dict()` returns the entity response shape from `docs/API_SPEC.md`. All tests green.

Key model requirements:
```python
class Entity(db.Model):
    # All columns from SCHEMA.sql
    # to_dict() returns full API response shape including backward-compat aliases
    # (raw_text, is_archived, name aliases for Cycle 1 compatibility)

class EntityLink(db.Model): ...
class EntityChunk(db.Model): ...
class EntityEvent(db.Model): ...
class Job(db.Model): ...
class Tag(db.Model): ...
```

---

**Task C1-SERVICES-CORE: entity_service + link_service**

- **Reads:** `docs/TECH_SPEC.md` (Service Layer Contracts), `docs/PRD.md` (Lifecycle Model)
- **Writes:**
  - `services/entity_service.py` — create, update, transition_status, archive, delete_preview
  - `services/link_service.py` — create_link, delete_link, get_links, delete_preview
  - `tests/unit/test_lifecycle.py` — all transition validation cases
  - `tests/integration/test_entities.py` — CRUD + lifecycle integration tests
  - `tests/integration/test_links.py` — link creation, cascade preview, orphan detection
- **Depends on:** C1-MODELS complete
- **Do not touch:** `api/` files, AI pipeline files
- **Tests:** `pytest tests/unit/test_lifecycle.py tests/integration/test_entities.py tests/integration/test_links.py -v`
- **Done when:** All status transitions enforce correctly. `delete_preview` correctly identifies orphans. All tests green.

Critical test cases that must pass:
```
✓ task: pending → in_progress (valid)
✓ task: done → archived (invalid, 400)
✓ project: active → on_hold (valid)
✓ project: archived → active (invalid, 400)
✓ delete_preview: entity with orphan links shows safe_to_cascade
✓ delete_preview: entity with shared links shows blocked
✓ parent link: second parent rejected with 400
✓ self-link: rejected with 400
```

---

**Task C1-JOBS: Job Worker**

- **Reads:** `docs/TECH_SPEC.md` (job_worker.py section), `docs/SCHEMA.sql` (jobs table)
- **Writes:**
  - `services/job_worker.py` — polling loop, get_next_job, process_job, exponential backoff
  - `tests/integration/test_jobs.py` — enqueue, poll, retry, backoff, max_attempts
- **Depends on:** C1-MODELS complete
- **Do not touch:** AI pipeline files, API files
- **Tests:** `pytest tests/integration/test_jobs.py -v`
- **Done when:** Job enqueues and processes. Failed jobs retry with backoff. Jobs past max_attempts are skipped. All tests green.

Worker behavior spec:
```python
def get_next_job():
    # SELECT * FROM jobs
    # WHERE status IN ('pending','failed')
    # AND attempts < max_attempts
    # AND run_after <= now()
    # ORDER BY created_at ASC
    # LIMIT 1
    # FOR UPDATE SKIP LOCKED   ← prevents double-pickup

def process_job(job):
    job.status = 'running'; job.attempts += 1; commit()
    try:
        dispatch[job.job_type](job.entity_id, job.payload)
        job.status = 'done'; commit()
    except Exception as e:
        job.status = 'failed'
        job.error = str(e)
        job.run_after = now() + timedelta(seconds=10 * 2**job.attempts)  # backoff
        commit()
```

---

**Task C1-AI-PIPELINE: Unified AI Pipeline**

- **Reads:** `docs/TECH_SPEC.md` (AI Pipeline Design), `services/ingestion.py`, `services/extractor.py` (current)
- **Writes:**
  - `services/ai_pipeline.py` — enqueue_classify, enqueue_embed, enqueue_autolink, run_classify, run_embed, run_autolink
  - `services/extractor.py` — update to use temperature=0, no other changes to extraction logic
  - `tests/integration/test_ingestion.py` — full pipeline tests (OpenAI mocked)
  - `tests/unit/test_ai_pipeline.py` — confidence threshold logic, entity creation gates
- **Depends on:** C1-MODELS, C1-JOBS complete
- **Do not touch:** `api/` files, `services/ingestion.py` (keep as thin wrapper), `services/embeddings.py` internals
- **Tests:** `pytest tests/unit/test_ai_pipeline.py tests/integration/test_ingestion.py -v`
- **Done when:** Capture is async (entity returned before AI runs). AI events logged in entity_events. Confidence < 0.92 does not auto-create new entities. All tests green.

Critical test cases:
```
✓ POST /notes returns in < 200ms (AI is async)
✓ job enqueued: classify + embed after create
✓ confidence >= 0.92: new project auto-created + entity_event written
✓ confidence 0.70-0.91: existing entity linked, new entity NOT created
✓ confidence < 0.70: stored in ai_meta only, no mutations
✓ run_classify writes entity_event(ai_classified, actor='agent:classify')
✓ run_classify with extraction failure: entity.ai_status = 'failed', job retried
```

---

**Task C1-API: Update API Routes**

- **Reads:** `docs/API_SPEC.md`, current `api/` files, `docs/TECH_SPEC.md` (API Compatibility section)
- **Writes:**
  - `api/notes.py` — rewrite to use entity_service + ai_pipeline.enqueue_*
  - `api/tasks.py` — rewrite to use entity_service, add `PATCH /tasks/:id/status`
  - `api/projects.py` — rewrite to use entity_service, add `PATCH /projects/:id/status`
  - `api/areas.py` — rewrite to use entity_service
  - `api/resources.py` — rewrite to use entity_service
  - `api/people.py` — rewrite to use entity_service
  - `api/tags.py` — minimal changes (tags table unchanged)
  - `api/jobs.py` — new: `GET /jobs`, `POST /jobs/:id/retry`
  - `api/events.py` — new: `GET /entities/:id/events`
  - `tests/integration/test_api_compat.py` — verify all existing API shapes still work
- **Depends on:** C1-MODELS, C1-SERVICES-CORE, C1-AI-PIPELINE complete
- **Tests:** `pytest tests/integration/test_api_compat.py -v`
- **Done when:** All existing frontend API calls return valid responses. New `ai_status`, `lifecycle`, `follow_up_at` fields present. Backward-compat aliases work. All tests green.

---

**Task C1-SEARCH: Update Search Service**

- **Reads:** `docs/TECH_SPEC.md` (search_service.py section), `services/search.py` (current)
- **Writes:**
  - `services/search.py` — rewrite to use Postgres FTS (tsvector) + pgvector; remove SQLite FTS5 and sqlite-vec
  - `services/embeddings.py` — update storage layer to use entity_chunks + pgvector
  - `tests/integration/test_search_api.py` — search returns results, hybrid mode works
- **Depends on:** C1-MODELS complete
- **Do not touch:** search API route (handled by C1-API)
- **Tests:** `pytest tests/integration/test_search_api.py -v`
- **Done when:** FTS search returns relevant results. Semantic search works (embeddings mocked). Hybrid RRF fusion works. All tests green.

---

### C1-GATE: Cycle 1 Integration Validation (sequential, all of C1-PARALLEL-1 must pass)

**Task C1-VALIDATE: Full Suite + Migration Validation**

- **Runs:** `pytest -q --cov=. --cov-report=term-missing`
- **Runs:** Migration script against production SQLite backup, validates row counts
- **Runs:** `cd ui && npm run build` — frontend must still build
- **Done when:** All tests green. Coverage ≥ 80% for `services/`, `api/`. Frontend builds. Migration script produces valid Postgres data.

---

## Cycle 2 — Relationships + UX

All tasks parallel after C1-VALIDATE passes.

**Task C2-LINKS-API: Universal Entity Links API**

- **Reads:** `docs/API_SPEC.md` (Entity Links section), `services/link_service.py`
- **Writes:**
  - `api/entity_links.py` — `GET /entities/:id/links`, `POST /entity-links`, `DELETE /entity-links/:id`, `GET /entities/:id/delete-preview`
  - `tests/integration/test_links_api.py`
- **Tests:** `pytest tests/integration/test_links_api.py -v`
- **Done when:** Can create any-to-any link via API. Delete preview returns correct orphan analysis. All tests green.

---

**Task C2-EDITOR: TipTap Note Editor**

- **Reads:** `docs/PRD.md` (Cycle 2 section), TipTap 2 docs
- **Writes:**
  - `ui/src/components/NoteEditor.jsx` — replace textarea with TipTap, live markdown rendering
  - `ui/src/components/SelectionMenu.jsx` — placeholder for text selection actions (Cycle 3)
  - `ui/package.json` — add `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-*`
- **Do not touch:** API files, backend files
- **Tests:** `cd ui && npm run build && npm run test` (vitest)
- **Done when:** Notes render markdown live as user types. Headings, bold, italic, lists, code blocks work. Saves on blur. Build succeeds.

---

**Task C2-KANBAN: Task Kanban Board**

- **Reads:** current `ui/src/pages/TasksPage.jsx`
- **Writes:**
  - `ui/src/pages/TasksPage.jsx` — kanban layout, columns by status, drag-and-drop
  - `ui/src/components/KanbanColumn.jsx`
  - `ui/src/components/KanbanCard.jsx`
  - `ui/package.json` — add `@dnd-kit/core`, `@dnd-kit/sortable`
- **Tests:** `cd ui && npm run build && npm run test`
- **Done when:** Tasks display in PENDING / IN_PROGRESS / DONE columns. Drag card between columns updates status via `PATCH /tasks/:id/status`. Build succeeds.

---

**Task C2-SURFACING: Proactive Surfacing**

- **Reads:** `docs/TECH_SPEC.md` (find_related section), `services/search.py`
- **Writes:**
  - `services/search.py` — add `find_related(entity_id, limit, exclude_linked)` function
  - `api/search.py` — add `GET /entities/:id/related` route
  - `ui/src/components/RelatedEntities.jsx` — panel shown on project/area/note detail pages
  - `tests/integration/test_surfacing.py`
- **Tests:** `pytest tests/integration/test_surfacing.py -v && cd ui && npm run build`
- **Done when:** Opening a project shows ≤ 5 semantically related entities not already linked. Backend test uses mocked embeddings. Build succeeds.

---

### C2-VALIDATE: Cycle 2 Integration Validation

- **Runs:** `pytest -q` + `cd ui && npm run build`
- **Done when:** Full suite green. No regressions from Cycle 1.

---

## Cycle 3 — AI Reliability

**Task C3-SELECTION: Text Selection → AI Proposal**

- **Reads:** `docs/PRD.md` (Cycle 3), `ui/src/components/NoteEditor.jsx` (from C2-EDITOR)
- **Writes:**
  - `ui/src/components/SelectionMenu.jsx` — selection context menu with AI actions
  - `api/ai_actions.py` — `POST /ai/propose-from-selection` (text + context → proposal)
  - `services/ai_pipeline.py` — add `propose_from_selection(text, entity_id)` function
  - `tests/integration/test_ai_actions.py`
- **Tests:** `pytest tests/integration/test_ai_actions.py -v && cd ui && npm run build`
- **Done when:** Selecting text in TipTap editor shows menu. AI proposal returned (not auto-applied). User confirms before entity is created. Event logged with `actor='agent:selection'`.

---

**Task C3-SEARCH-UNIVERSAL: Universal Search**

- **Reads:** `docs/API_SPEC.md` (Search section), `services/search.py`, current `ui/src/components/CommandPalette.jsx`
- **Writes:**
  - `services/search.py` — ensure `search()` covers all entity types (likely already works after C1-SEARCH; validate and add type filters)
  - `api/search.py` — ensure `type` query param filters work
  - `ui/src/components/CommandPalette.jsx` — add type filter chips, show entity type badges in results
  - `tests/integration/test_search_universal.py`
- **Tests:** `pytest tests/integration/test_search_universal.py -v && cd ui && npm run build`
- **Done when:** Search returns tasks, projects, areas, resources, people — not just notes. Type filter works. All tests green.

---

**Task C3-AI-QUALITY: Confidence Calibration + Correction Signals**

- **Reads:** `docs/TECH_SPEC.md` (AI Pipeline Design — confidence thresholds), `services/ai_pipeline.py`
- **Writes:**
  - `services/ai_pipeline.py` — enforce ≥ 0.92 for new entity creation (not just linking)
  - `api/notes.py`, `api/tasks.py` — detect when user overrides AI field, write `entity_event('ai_correction')`
  - `tests/unit/test_ai_quality.py`
- **Tests:** `pytest tests/unit/test_ai_quality.py -v`
- **Done when:** New entities only auto-created at ≥ 0.92. Manual override writes ai_correction event. All tests green.

---

### C3-VALIDATE: Cycle 3 Final Validation

- **Runs:** `pytest -q --cov=. --cov-report=term-missing` (must show ≥ 80% on all service files)
- **Runs:** `cd ui && npm run build`
- **Done when:** Full suite green. Coverage gates met. System ready for production use.

---

## File Ownership Map

Prevents merge conflicts when agents work in parallel.

| File / Directory | Owner task |
|---|---|
| `docker-compose.yml` | C1-INFRA |
| `docs/SCHEMA.sql` | READ-ONLY after creation |
| `scripts/` | C1-INFRA |
| `models.py` | C1-MODELS |
| `services/entity_service.py` | C1-SERVICES-CORE |
| `services/link_service.py` | C1-SERVICES-CORE |
| `services/job_worker.py` | C1-JOBS |
| `services/ai_pipeline.py` | C1-AI-PIPELINE, C3-SELECTION, C3-AI-QUALITY |
| `services/extractor.py` | C1-AI-PIPELINE |
| `services/embeddings.py` | C1-SEARCH |
| `services/search.py` | C1-SEARCH, C3-SEARCH-UNIVERSAL |
| `api/notes.py` | C1-API |
| `api/tasks.py` | C1-API |
| `api/projects.py` | C1-API |
| `api/areas.py` | C1-API |
| `api/resources.py` | C1-API |
| `api/people.py` | C1-API |
| `api/entity_links.py` | C2-LINKS-API |
| `api/ai_actions.py` | C3-SELECTION |
| `api/search.py` | C1-API, C3-SEARCH-UNIVERSAL |
| `ui/src/components/NoteEditor.jsx` | C2-EDITOR |
| `ui/src/components/SelectionMenu.jsx` | C2-EDITOR (placeholder), C3-SELECTION (impl) |
| `ui/src/pages/TasksPage.jsx` | C2-KANBAN |
| `ui/src/components/RelatedEntities.jsx` | C2-SURFACING |
| `ui/src/components/CommandPalette.jsx` | C3-SEARCH-UNIVERSAL |
| `tests/conftest.py` | SHARED — coordinate before changing |

---

## EXECUTION-TRACKER.md Updates

After each task, add a row:

```markdown
| Task | Agent | Status | Tests | Coverage | Notes |
|---|---|---|---|---|---|
| C1-INFRA | - | done | schema applies | - | migration: 847 notes, 203 tasks migrated |
| C1-MODELS | - | done | 24/24 pass | 91% | - |
```
