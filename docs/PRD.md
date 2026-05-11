# Engram — Product Requirements Document
> Version 2.0 | Supersedes SPEC.md

---

## Vision

Engram is a self-hosted personal workspace where capture is instant, recall is excellent, and AI handles organization automatically. It serves two modes simultaneously: a **project and task runner** for active work, and a **knowledge base** for long-term retention and recall.

The organizing principle is PARA (Projects, Areas, Resources, Archives) as one lens among several — not as the architectural backbone. The product wins when a user can capture anything in seconds and find exactly what they need months later without having maintained any filing system.

**Target user:** Single user, self-hosted. Technical enough to run Docker.

---

## What This Is Not

- Not a Notion replacement (no collaborative editing, no infinite nesting)
- Not a task manager (no time tracking, no sprints, no team assignment)
- Not a search engine (no web crawl, no external indexing)
- Not trying to replace Linear, Obsidian, or Notion individually — it sits between them

---

## Core Principles

1. **Capture is sacred.** Nothing should interrupt the act of capture. AI processing happens after, never during.
2. **Recall over organization.** The system should find things; the user should not have to file things.
3. **AI actions are visible and correctable.** No silent mutations. Every AI write is logged with confidence and actor.
4. **Stable, boring infrastructure.** Choose proven tools. Avoid clever abstractions that need maintenance.

---

## Entity Model

Every object in the system is an **entity** with a `type`. Types share a common lifecycle and relationship model. Type-specific fields are stored in a `properties` JSON column.

| Type | Primary use | Key type-specific fields |
|---|---|---|
| `note` | Capture surface, knowledge record | `bucket`, `note_type` |
| `task` | Action items | `priority`, `due_date`, `inline_title_hash` |
| `project` | Active work with an outcome | `priority`, `deadline`, `color` |
| `area` | Ongoing responsibility | `color` |
| `resource` | Reference material | `resource_type`, `url`, `author`, `is_read`, `rating` |
| `person` | Contact / collaborator | `email`, `external_ids`, `last_contacted_at` |

All entities share: `title`, `content`, `status`, `lifecycle`, `follow_up_at`, `source`, `reference_url`, `ai_meta`, `created_at`, `updated_at`.

---

## Lifecycle Model

Every entity has two orthogonal state fields:

**`lifecycle`** — where the entity is in its existence:
```
active → archived → deleted
active → paused   (projects, areas only)
```

**`status`** — operational state, type-specific valid values:

| Type | Valid statuses |
|---|---|
| task | `pending`, `in_progress`, `done`, `cancelled` |
| project | `active`, `on_hold`, `completed`, `cancelled` |
| note | `active`, `archived` |
| area | `active`, `archived` |
| resource | `active`, `archived` |
| person | `active`, `archived` |

Invalid transitions are rejected by the service layer. Every status change is recorded in `entity_events`.

---

## Relationship Model

Any entity can link to any other entity via `entity_links`. Structural ownership (task belongs to project) uses `link_type='parent'`. Associative links (note mentions person) use semantic link types.

**Canonical link types:**
- `parent` — structural ownership (one parent max per entity)
- `related` — general association
- `references` — entity cites another as a source
- `blocks` — entity cannot proceed until target is resolved
- `mentions` — entity names/discusses target
- `derived_from` — entity was created from target (e.g. task from note)
- `assigned_to` — task/project involves a person

**Cascade delete rule:** When deleting an entity, check `entity_links` for linked entities whose only connection is to the entity being deleted. Offer to delete those too. All others remain.

---

## AI Pipeline

**Classification and extraction run asynchronously after capture.** The entity is created immediately and returned to the caller. AI enrichment fills in within seconds via the background job queue.

**Confidence thresholds:**
- `≥ 0.92` — auto-apply, log in entity_events
- `0.70–0.91` — auto-apply links/tags to *existing* entities; queue new entity *creation* for review
- `< 0.70` — store in `ai_meta` only, no mutations

**Every AI action writes to `entity_events`** with `actor='agent:<pipeline>'`, `confidence`, and `reason`. This is the audit trail and the basis for future correction signals.

---

## Cycles

### Cycle 1 — Foundation (2 weeks)
Backend only. No visible UI change. Fixes the infrastructure.

- Postgres + pgvector replaces SQLite + sqlite-vec
- `entities` single-table schema with `entity_links`, `entity_tags`, `entity_chunks`, `entity_events`, `jobs`
- Data migration from existing SQLite
- Status transition enforcement
- Unified AI pipeline (one code path, async)
- Background job worker with retry
- All existing API routes keep their response shapes

**Done when:** All existing tests pass against Postgres. Migration script runs clean. Capture is instant (AI is async).

### Cycle 2 — Relationships + UX (2 weeks)
Closes the biggest product gaps.

- Universal `entity_links` API (link any entity to any entity)
- "Link to..." action in all detail views
- Graph-aware delete (orphan detection)
- TipTap note editor (live markdown, not textarea + preview)
- Kanban task board (drag-and-drop by status)
- Proactive surfacing: top 5 semantically related entities on project/area open

**Done when:** Can link a task to a person from the UI. Notes render markdown live. Tasks have drag-and-drop kanban.

### Cycle 3 — AI Reliability (1.5 weeks)
Makes AI interactions trustworthy.

- Text selection → AI proposal flow in the note editor
- Universal search (all entity types, not just notes)
- Confidence calibration: new entity creation requires `≥ 0.92` or explicit user confirmation
- Correction feedback: user overrides recorded in `entity_events` as `ai_correction`

**Done when:** Can select text in a note and create a task from it. Search returns results from all entity types.

---

## Non-Goals (explicitly deferred)

- MOC generation
- Health snapshot metrics
- Graph visualization (replace with linked-entities panel)
- Link proposal review queue
- Progressive summarization jobs
- Multi-user support
- Mobile app
