# Engram v4 Principles

Source of truth: `docs/V4_WORLD_MODEL_PLAN.md` (supersedes GitHub issue #1 as of 2026-06-09).

## Production Data Safety (added 2026-06-09 — supersedes "clean cutover" clause)

The system now holds real production data that must be preserved. The original
"no migration, data deletable" stance is retired.

1. **Schema changes are additive-only.** New nullable/defaulted columns, new tables,
   new enum values only. Never drop or rename columns or tables while data exists.
2. **Every schema change ships as a numbered idempotent script** in
   `scripts/migrations/NNN_<name>.sql`. Apply with explicit psql invocation.
   Never run `flask init-db` against a database with real data.
3. **Snapshot before any prod schema change or deploy:**
   `bash scripts/backup_prod.sh` — verifies the dump is non-empty before continuing.
   Dumps go to `backups/` (gitignored).
4. **Tests never touch prod.** Tests run only against the isolated test DB
   (`docker-compose.test.yml`, port 5433, tmpfs). `TEST_DATABASE_URL` must point
   to port 5433. The conftest guards enforce this.
5. **Prod DB access during development is read-only** except via the running API
   or explicitly reviewed migration scripts.

## API and Architecture Rules

1. Do not preserve `/api/v1` or `/api/v2` behavior.
2. Do not build compatibility adapters for old response shapes.
3. Do not store relationship IDs inside `properties`.
4. All relationships must use `EntityLink` / relationship records.
5. Notes must remain source artifacts. AI can extract from notes, but must not convert notes into other entity types.
6. AI must use balanced automation: source notes are always preserved, safe metadata/linking can be auto-applied, and high-confidence entity creation may be auto-applied only with explicit guardrails and audit events.
7. Each slice must be implemented, tested, verified, committed, and merged before starting the next slice.
8. Do not improvise outside the current slice acceptance criteria.
9. Keep the implementation simple, functional, explicit, and testable.
10. Ruthlessly remove obsolete code once replacements are working.

## Product Target

Engram v4 should support:

- Capture-first input for messy thoughts, updates, notes, reminders, references, and project ideas.
- Source notes preserved exactly as source artifacts.
- First-class entities for notes, tasks, projects, areas, people, and resources.
- Intuitive manual entity management from detail pages.
- Type-specific relationship sections, not a generic catch-all relationship view.
- AI extraction and reviewable suggestions.
- Hybrid keyword + semantic search.
- Canonical markdown generation for every entity.
- Write-enabled MCP aligned with `/api/v4` for capture, review, lightweight entity management, and retrieval.

Do not implement decisions, graph view, advanced dashboarding, AI answer mode, recurring tasks, or calendar integration in the v4 baseline.

## Supported Entity Types

Only these six entity types are in v4 launch:

```text
note
task
project
area
resource
person
```

## Relationship Model

Allowed relationship types:

```text
parent
related
derived_from
mentions
assigned_to
references
blocks
activity_update
```

Examples:

```text
project parent area
task parent project
note mentions person
task derived_from note
resource references project
task assigned_to person
task blocks task
note activity_update project
```

Do not store relationships as `project_id`, `area_id`, `person_id`, `note_id`, `parent_id`, `source_note_id`, or similar fields inside `properties`. All relationships must use entity links.

## Notes and AI Policy

Notes remain source artifacts. Capture must save the original source note first. AI may extract candidate entities, links, tags, summaries, or suggestions from notes, but must not convert notes into other entity types.

Auto-apply:

- High-confidence tags.
- High-confidence links to existing entities.
- Source note summaries.
- High-confidence new entities only when reconciliation confidence is at or above the auto-create threshold and the action is recorded with an `agent:*` actor.

Create suggestions for:

- New task/project/area/person/resource candidates below the auto-create threshold.
- Lower-confidence status or date changes.
- Relationship deletion.
- Entity deletion.
- Merge/dedupe.

Never auto-apply destructive or irreversible work. Deletion, relationship deletion, merge/dedupe, and stale cleanup decisions must remain reviewable suggestions or explicit manual actions.

The current launch threshold for auto-created entities is `0.9`. This is intentionally stricter than the general safe metadata/linking threshold so ordinary extraction confidence does not silently create work.

## API and Runtime Boundary

Create only:

```text
/api/v4
```

Do not expose `/api/v1` or `/api/v2` at runtime after v4 cutover.

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

## Execution Discipline

Work must proceed cycle by cycle. Each cycle must be scoped, validated, committed, and reviewed before moving to the next cycle. Do not start Cycle 1 until Cycle 0 is complete and committed.
