# Engram v4 Principles

Source of truth: GitHub issue #1, "Engram v4 clean cutover implementation plan".

## Clean Cutover

Engram v4 is a fresh clean cutover. There is no backward compatibility requirement and no data migration requirement. Existing local app data can be deleted, and the system can start with a fresh database.

The only target runtime API for v4 is `/api/v4`. Existing `/api/v1` and `/api/v2` behavior is obsolete for v4 and must not be preserved.

## Non-Negotiable Rules

1. Do not preserve `/api/v1` or `/api/v2` behavior.
2. Do not build compatibility adapters for old response shapes.
3. Do not implement migration.
4. Do not store relationship IDs inside `properties`.
5. All relationships must use `EntityLink` / relationship records.
6. Notes must remain source artifacts. AI can extract from notes, but must not convert notes into other entity types.
7. AI must use balanced automation: source notes are always preserved, safe metadata/linking can be auto-applied, and high-confidence entity creation may be auto-applied only with explicit guardrails and audit events.
8. Each cycle must be implemented, tested, verified, committed, and merged before starting the next cycle.
9. Do not improvise outside the current cycle acceptance criteria.
10. Keep the implementation simple, functional, explicit, and testable.
11. Ruthlessly remove obsolete code once v4 replacements are working.

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
