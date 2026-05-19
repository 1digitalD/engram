# Engram v4 UI/UX Design Guide

Engram v4 is an action-first personal workspace, not a generic database UI. The interface must optimize for fast capture, clear daily review, type-specific relationships, and low-friction updates while preserving the v4 clean-cutover rules.

## Product Feel

- Minimal chrome, maximum context.
- Capture first, sort later.
- Every entity detail screen should answer: what is this, what needs action, what is linked, and what can I do next?
- Relationship management must feel specific to the entity type, not like a generic graph editor.
- AI should be visible as assistance: safe metadata and linking can apply automatically; creation, status changes, deletion, merging, and risky edits must remain suggestions or explicit user actions.

## Research-Informed Principles

- Show system state immediately. Saves, captures, links, removals, and errors need visible inline feedback.
- Prefer recognition over recall. Users should see available actions, valid relationships, statuses, due dates, and linked entities without remembering IDs or schemas.
- Support multiple action paths. Beginners need buttons and inline forms; experienced users need fast quick-add, search, keyboard shortcuts, and contextual actions.
- Keep primary content minimal. Rare metadata belongs in compact disclosures, not always-open panels.
- Prevent errors before they happen. Disable invalid submits, use type-specific pickers, and never ask users to paste relationship IDs.
- Keep relationship context visible. Linked entities should show type, status, relationship type, due date, and priority in compact rows.

## App-Wide Interaction Model

### Capture

- The fastest path in the app is always freeform capture.
- Notes are source artifacts. Any note creation entry point must use `/api/v4/capture`, not raw entity conversion.
- Capture can safely produce metadata, tags, and links. It can suggest risky creates or mutations.

### Quick Add

- List pages should have a one-line quick-add path above the list.
- Notes allow content-only creation.
- Tasks/projects/areas/people/resources require a title, with optional details hidden behind a compact details control.
- Task quick-add should surface due date and priority with the fewest clicks.

### Entity Detail

- Keep basic info above the fold on a typical laptop screen.
- Header area should be compact: title, body, status, due date/follow-up, priority, tags, save/archive.
- Relationship sections should be vertical segments with:
  - Segment title and count.
  - Inline create/link controls.
  - Linked rows underneath.
  - Remove/status actions close to each linked row.
- Default action rows should be short. Advanced content/date fields should be hidden until requested.

### Relationship UX

- Do not expose raw relationship IDs.
- Do not store relationship IDs in properties.
- Every relationship change must call the v4 relationship API and create `EntityLink` records.
- Relationship actions must be named in user language:
  - Project: add task, link task, add note, link person/resource.
  - Task: move/link project or area, assign person, attach source note/resource, add blocker.
  - Note: create derived task, link project/area/person/resource.
  - Person: assign task, add note about person, link project/resource.
  - Resource: link reference notes, projects, tasks, areas, people.

## Visual System

- Use the existing v4 tokens in `ui/src/index.css`: IBM Plex Sans/Mono, OKLCH colors, compact type scale, subtle borders.
- Pills are metadata, not primary actions. They should stay small, low-height, and color-coded by meaning.
- Primary actions use green for creation/save. Secondary link actions use accent. Destructive actions use red.
- Dense rows should favor scanability: title first, metadata second, actions at the edge.
- Prefer compact panels with clear grouping over large cards that force scrolling.

## Validation Checklist

- Notes can be created from content-only input.
- Note creation paths use `/api/v4/capture`.
- Entity creation paths use `/api/v4/entities` only for non-note entities.
- Relationship add/remove paths use `/api/v4/entities/:id/relationships` or `/api/v4/relationships/:id`.
- No UI asks for raw IDs.
- Detail basic info and first relationship segment fit above the fold on desktop.
- Frontend tests, lint, and build pass after UI changes.
