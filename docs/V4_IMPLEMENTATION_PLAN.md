# Engram v4 Clean Cutover Implementation Plan

Source of truth: GitHub issue #1, "Engram v4 clean cutover implementation plan".

## Purpose

This document records the controlling implementation plan for Engram v4.

Engram v4 is a fresh clean cutover. There is no backward compatibility requirement. There is no data migration requirement. Existing local app data can be deleted and the system can start with a fresh database.

The goal is to rebuild Engram into a stable, functional, efficient personal productivity and knowledge system for work and personal projects.

## Required v4 API Namespace

Create only:

```text
/api/v4
```

Required endpoints:

```text
GET    /api/v4/health

POST   /api/v4/capture

GET    /api/v4/entities
POST   /api/v4/entities
GET    /api/v4/entities/:id
PATCH  /api/v4/entities/:id
DELETE /api/v4/entities/:id
GET    /api/v4/entities/:id/detail
GET    /api/v4/entities/:id/events
GET    /api/v4/entities/:id/canonical

GET    /api/v4/entities/:id/relationships
POST   /api/v4/entities/:id/relationships
PATCH  /api/v4/relationships/:id
DELETE /api/v4/relationships/:id

GET    /api/v4/suggestions
POST   /api/v4/suggestions/:id/accept
POST   /api/v4/suggestions/:id/dismiss

GET    /api/v4/search
GET    /api/v4/today
GET    /api/v4/recent
```

Do not expose `/api/v1` or `/api/v2` at runtime after v4 cutover.

## Entity DTO

Every entity response should use this canonical shape:

```json
{
  "id": "uuid",
  "type": "task",
  "title": "Follow up with Henry",
  "content": "Optional body text",
  "status": "open",
  "lifecycle": "active",
  "follow_up_at": "2026-05-20T10:00:00Z",
  "source": "manual",
  "reference_url": null,
  "properties": {
    "priority": "high"
  },
  "tags": [
    {
      "id": "uuid",
      "name": "memory"
    }
  ],
  "ai": {
    "summary": "Short generated summary",
    "status": "done",
    "confidence": 0.91
  },
  "relationship_counts": {
    "incoming": 2,
    "outgoing": 5
  },
  "created_at": "...",
  "updated_at": "..."
}
```

Forbidden legacy fields in active v4 DTOs:

```text
raw_text
name
is_archived
project_id
project_ids
area_id
person_id
note_id
parent_id
due_date as alias for follow_up_at
```

## Status Values

### note

```text
active
processed
archived
```

### task

```text
open
in_progress
waiting
blocked
done
cancelled
```

### project

```text
active
on_hold
completed
cancelled
```

### area/resource/person

```text
active
archived
```

Lifecycle is separate and cross-cutting:

```text
active
archived
deleted
```

## Database and Tables

Fresh DB. No migration required.

Required tables:

```text
entities
entity_links
tags
entity_tags
entity_chunks
entity_events
ai_suggestions
jobs
change_batches
```

### entities

```text
id
type
title
content
status
lifecycle
follow_up_at
source
reference_url
properties json/jsonb
ai_meta json/jsonb
ai_status
created_at
updated_at
```

### entity_links

```text
id
source_entity_id
target_entity_id
relationship_type
source
confidence
evidence
created_at
updated_at
```

Constraints:

- Source cannot equal target.
- Duplicate relationship records are rejected.
- Relationship type must be one of the allowed v4 relationship types.

### entity_events

Every meaningful mutation writes an event:

```text
created
updated
status_changed
archived
deleted
relationship_added
relationship_removed
tag_added
tag_removed
ai_processed
suggestion_accepted
suggestion_dismissed
```

## Canonical Markdown

Every entity must be convertible into canonical markdown on demand.

This is used for:

- Semantic search embeddings.
- Future export.
- MCP retrieval.
- Future AI answer mode.
- Summarization.

Do not cache canonical markdown in v4 launch. Generate on demand.

## Capture Behavior

Endpoint:

```text
POST /api/v4/capture
```

Request:

```json
{
  "content": "raw text",
  "source": "quick_capture",
  "mode": "auto"
}
```

Modes:

```text
auto
note
task
resource
person
```

Default is `auto`.

Behavior:

1. Save a source note immediately.
2. Run quick inline extraction if available.
3. Return source note plus applied safe changes and suggestions.
4. Queue background enrichment for embeddings and deeper processing.
5. If AI fails, the source note must still be saved and the response should include a warning.

Capture result shape:

```json
{
  "source_note": {},
  "applied_changes": [],
  "suggestions": [],
  "warnings": []
}
```

## Entity Detail UX Contract

The detail view must support intuitive entity management and type-specific relationship sections. Do not build only a generic relationship list.

### Task detail sections

```text
Project
Area
People
Source Notes
Related Notes
Resources
Blocking / Blocked By
Related Tasks
```

### Project detail sections

```text
Area
Open Tasks
Completed Tasks
Notes
Resources
People
Related Projects
Blocked By / Blocks
```

### Area detail sections

```text
Projects
Tasks
Notes
Resources
People
```

### Note detail sections

```text
Projects
Areas
People Mentioned
Derived Tasks
Referenced Resources
Related Notes
```

### Person detail sections

```text
Assigned Tasks
Mentioned In Notes
Projects
Resources
Related People
```

### Resource detail sections

```text
Referenced By Notes
Projects
Tasks
Areas
People
Related Resources
```

## Frontend v4 Scope

Keep the existing design direction if useful, but rebuild the UI wiring against `/api/v4` only.

Initial routes:

```text
/
/inbox
/today
/search
/entities/:id
/notes
/notes/:id
/projects
/projects/:id
/tasks
/tasks/:id
/areas
/areas/:id
/people
/people/:id
/resources
/resources/:id
/suggestions
```

Defer/delete for v4 launch:

```text
/graph
/dashboard
/review
/metrics
```

## Search

v4 must have hybrid search.

Endpoint:

```text
GET /api/v4/search?q=&type=&mode=&limit=
```

Modes:

```text
keyword
semantic
hybrid
```

Default mode: `hybrid`.

Do not implement AI answer mode in v4 launch.

## MCP

v4 MCP is read-only only.

Tools:

```text
search_entities(query, type?, limit?)
get_entity(entity_id, include_relationships?)
list_recent(type?, limit?)
```

Do not expose write tools yet.

Forbidden MCP tools in v4 launch:

```text
capture
create_task
update_entity
link_entities
delete_entity
```

## Execution Process

Work on branch:

```text
v4-clean-cutover
```

Every cycle must follow:

1. Implement only scoped changes.
2. Run backend tests.
3. Run frontend build/tests where applicable.
4. Run manual smoke checks where applicable.
5. Commit.
6. Merge to the v4 branch or keep the cycle branch reviewed and merged into `v4-clean-cutover`.
7. Only then proceed to the next cycle.

## Validation Commands

Backend:

```bash
pytest
flask --app app.py routes
curl http://localhost:5001/api/v4/health
```

Frontend:

```bash
cd ui
npm install
npm run build
```

Forbidden active-code checks:

```bash
grep -R "/api/v1" .
grep -R "/api/v2" .
grep -R "raw_text" .
grep -R "project_id" .
grep -R "area_id" .
grep -R "person_id" .
grep -R "note_id" .
grep -R "parent_id" .
```

These terms may appear only in archived docs or migration notes, not active runtime code.

## Implementation Cycles

### Cycle 0 - branch and docs

Goal: create `v4-clean-cutover` and document the cutover.

Acceptance:

- Branch exists.
- Docs exist.
- No runtime behavior changed.

Codex task:

```text
Create a new branch called v4-clean-cutover. Add docs/V4_PRINCIPLES.md and docs/V4_IMPLEMENTATION_PLAN.md from this issue. Do not modify runtime code yet. Explicitly state that v4 is a clean cutover with no backward compatibility and no migration.
```

### Cycle 1 - fresh v4 schema and models

Goal: implement clean v4 schema and model serialization.

Acceptance:

- Fresh DB initializes.
- v4 tables exist.
- Canonical DTO serialization works.
- No legacy fields in canonical DTO.
- Tests pass.

Codex task:

```text
Implement the v4 data model as a clean cutover. Do not preserve legacy aliases or v1/v2 compatibility fields. Use Entity, EntityLink, Tag, EntityTag, EntityChunk, EntityEvent, AiSuggestion, Job, and ChangeBatch. Relationships must only be represented by EntityLink, never by project_id/area_id/person_id/note_id/parent_id inside properties. Add tests proving canonical serialization does not include raw_text, name, is_archived, project_id, area_id, person_id, note_id, parent_id, or due_date aliases.
```

### Cycle 2 - v4 entity API

Goal: implement canonical entity CRUD.

Acceptance:

- Create note/task/project/area/person/resource.
- Update title/content/status/follow_up_at/properties/tags.
- Archive/delete entity.
- Events written.
- Tests pass.

Codex task:

```text
Build /api/v4/entities CRUD using only the v4 canonical Entity DTO. All create/update/archive/delete operations must write EntityEvent rows. Reject properties containing relationship IDs such as project_id, area_id, person_id, note_id, source_note_id, parent_id, or related entity IDs. Do not use or modify /api/v1 or /api/v2 endpoints except for later deletion. Add API tests for create, update, archive, delete, and event creation.
```

### Cycle 3 - v4 relationship API

Goal: implement relationship management.

Acceptance:

- Task parent project.
- Project parent area.
- Note mentions person.
- Task derived_from note.
- Duplicate rejection.
- Relationship delete.
- Tests pass.

Codex task:

```text
Implement the v4 relationship API. Use EntityLink only. Supported relationship types are parent, related, derived_from, mentions, assigned_to, references, and blocks. Prevent self-links and duplicates. Relationship creation/removal must write EntityEvent entries. Add tests for task-parent-project, project-parent-area, note-mentions-person, task-derived_from-note, duplicate rejection, and relationship deletion.
```

### Cycle 4 - canonical markdown service

Goal: generate canonical markdown for every entity.

Acceptance:

- Canonical output includes type, title, status, lifecycle, follow_up_at, content, tags, properties, relationships, source, timestamps.
- Relationship titles included.
- No caching yet.
- Tests pass.

Codex task:

```text
Create a canonical document service that generates markdown for any Entity. Include title, type, status, lifecycle, follow_up_at, content, tags, properties, and named relationships. Add GET /api/v4/entities/:id/canonical. Do not cache canonical documents yet. Add tests verifying relationship titles are included in canonical output.
```

### Cycle 5 - v4 search foundation

Goal: implement hybrid search.

Acceptance:

- Keyword search works.
- Semantic search works with mocked embeddings.
- Hybrid RRF works.
- Filters work.
- Tests pass.

Codex task:

```text
Implement /api/v4/search with keyword, semantic, and hybrid modes. Use canonical markdown for embedding chunk text. Add type/status/lifecycle filters. Use RRF fusion for hybrid mode. Mock embedding generation in tests. Do not implement AI answer mode.
```

### Cycle 6 - v4 capture basic

Goal: save source note first, no risky AI mutations.

Acceptance:

- Capture saves note.
- AI failure does not lose note.
- Embedding job queued.
- Stable response shape.
- Tests pass.

Codex task:

```text
Implement /api/v4/capture. It must always save the raw content as a note first. It should return a CaptureResult with source_note, applied_changes, suggestions, and warnings. If AI/extraction fails, the note must still be saved and a warning returned. Queue embedding generation. Do not auto-create tasks, projects, people, areas, or resources in this cycle.
```

### Cycle 7 - extraction and suggestions

Goal: add AI extraction/reconciliation/suggestions.

Acceptance:

- Task creation suggestions from note.
- Person creation suggestions.
- High-confidence links to existing project/person.
- Suggestions include source note and evidence.
- No blind entity creation.
- Mocked tests pass.

Codex task:

```text
Extend /api/v4/capture with AI extraction and reconciliation. The extractor should produce candidates only. Reconciliation must check existing entities before suggestions are created. Auto-apply only high-confidence tags and links to existing entities. New task/project/area/person/resource creation must be stored as AiSuggestion, not auto-created. Add tests using mocked extraction output.
```

### Cycle 8 - suggestion accept/dismiss

Goal: user-reviewed AI changes.

Acceptance:

- Accept create_task suggestion.
- Created task links to source note using derived_from.
- Accept create_person/create_project/create_area/create_resource.
- Dismiss suggestion without mutation.
- Events written.
- Tests pass.

Codex task:

```text
Implement v4 suggestions review. Add list, accept, and dismiss endpoints. Accepting a create_task suggestion must create the task and link it to the source note using derived_from. Accepting create_person/create_project/create_area/create_resource should create the entity and link it to the source note appropriately. Dismiss must not mutate entities. All actions must write EntityEvent rows. Add tests.
```

### Cycle 9 - relationship-aware detail payloads

Goal: support intuitive detail screens.

Acceptance:

- Task detail has Project, Area, People, Source Notes, Resources, Blocking.
- Project detail has Area, Tasks, Notes, Resources, People.
- Note detail has Projects, Areas, People, Derived Tasks, Resources.
- Tests pass.

Codex task:

```text
Implement /api/v4/entities/:id/detail. It should return the canonical entity plus type-specific relationship sections. Do not return only a generic flat links list. Add relationship section definitions for task, project, area, note, person, and resource. Add tests for task, project, and note detail payloads.
```

### Cycle 10 - frontend v4 API client and shell

Goal: rebuild frontend against v4 only.

Acceptance:

- Frontend builds.
- No `/api/v1` calls remain.
- No `/api/v2` calls remain.
- Navigation works.

Codex task:

```text
Rebuild the frontend API layer for v4 only. Create ui/src/api/v4Client.js and remove usage of old /api/v1 and /api/v2 clients. Set up the v4 route shell for inbox, today, search, entity detail, notes, projects, tasks, areas, people, resources, and suggestions. Do not implement all screens fully yet. Ensure npm build passes.
```

### Cycle 11 - capture inbox UI

Goal: primary capture experience.

Acceptance:

- Capture text.
- Note appears in inbox.
- Suggestions appear if returned.
- AI warning shown but note remains.
- Frontend build passes.
- Manual smoke test passes.

Codex task:

```text
Implement the v4 Capture Inbox UI. It should call POST /api/v4/capture, display the saved source note, show applied changes and suggestions, and list recent notes. It must not use legacy note APIs. Add basic UI tests if the project has a test setup; otherwise ensure build passes and provide manual smoke test steps.
```

### Cycle 12 - entity list and detail views

Goal: manual management screens.

Acceptance:

- Create task manually.
- Assign task to project via relationship section.
- Add area relationship.
- Add linked note.
- Remove linked note.
- Update task status.
- Edit note metadata and relationships.
- Manage project/area relationships.
- Frontend build passes.

Codex task:

```text
Build v4 entity list and detail screens. Detail views must include type-specific relationship sections, not a generic catch-all relationship list. Users must be able to create, update, archive/delete entities and add/remove relationships from detail pages. Start with task, project, area, and note details as priority. Ensure no v1/v2 APIs are used.
```

### Cycle 13 - search UI

Goal: hybrid search interface.

Acceptance:

- Search works across entity types.
- Filters work.
- Result opens detail.
- Build passes.

Codex task:

```text
Implement the v4 search UI using GET /api/v4/search. Support query, type filter, and mode selection for hybrid, keyword, and semantic. Results should open the corresponding entity detail page. Do not implement AI answer mode.
```

### Cycle 14 - Today view

Goal: execution cockpit.

Acceptance:

- Today shows overdue/today follow-ups.
- Today shows open blocked/waiting tasks.
- Today shows projects without open tasks.
- Today shows recent notes and pending suggestions.
- Links open detail pages.
- Build/tests pass.

Codex task:

```text
Implement /api/v4/today and the Today UI. It should show overdue/today follow-ups, open blocked/waiting tasks, projects without open tasks, recent notes, and pending suggestions. Keep it simple and functional. Do not add dashboards or analytics.
```

### Cycle 15 - read-only MCP

Goal: stable read-only agent access.

Acceptance:

- MCP search returns v4 search results.
- MCP get_entity returns canonical entity with relationships.
- MCP list_recent returns recent active entities.
- No write tools exposed.
- Smoke tested locally.

Codex task:

```text
Update the MCP server to use v4 read-only APIs only. Expose search_entities, get_entity, and list_recent. Do not expose capture, create, update, delete, or link tools. Add simple smoke documentation and tests/mocks where practical.
```

### Cycle 16 - cleanup and deletion

Goal: remove obsolete code.

Delete:

```text
/api/v1 modules
/api/v2 modules once fully replaced
old ingest endpoint
old notes/projects/tasks compatibility APIs
old graph view
old dashboard view
old API client
old store files no longer used
old specs that contradict v4
legacy tests
```

Acceptance:

- App registers only `/api/v4`.
- No frontend references to v1/v2.
- Backend tests pass.
- Frontend build passes.
- Search summary proves no active legacy references.

Codex task:

```text
Ruthlessly remove obsolete v1/v2 code and frontend legacy wiring after v4 functionality is implemented. Delete unused routes, services, views, API clients, and tests that reference legacy DTOs. Ensure the app registers only /api/v4. Run backend tests and frontend build. Provide a grep/search summary proving no active code references /api/v1, /api/v2, raw_text, project_id relationship properties, area_id relationship properties, person_id relationship properties, note_id relationship properties, or parent_id relationship properties.
```

## Final Completion Definition

Engram v4 is complete when:

- Fresh DB initializes cleanly.
- Only `/api/v4` is active.
- UI uses only `/api/v4`.
- Six entity types work: note, task, project, area, resource, person.
- Notes remain source artifacts.
- Relationships are all managed through entity links.
- No relationship IDs are stored inside properties.
- Capture saves original note first.
- AI suggestions are reviewable.
- Manual entity management works from detail pages.
- Type-specific relationship sections work.
- Hybrid search works.
- Canonical markdown generation works.
- Read-only MCP works.
- Obsolete v1/v2 code is deleted or fully removed from runtime.
