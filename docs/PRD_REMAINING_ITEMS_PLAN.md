# Remaining Items Plan — AI Productivity OS

**Branch:** `v3.5-ai-productivity-os`
**Base:** After 10 iterations complete (`b8446f88`)
**Updated:** 2026-05-14

---

## What's Done (Iterations 1–10)

| # | What | Commit |
|---|---|---|
| 1 | Wire extracted_people through reconcile_all + apply_change_plan | `742cd783` |
| 2 | Wire extracted_tasks through reconcile_all + apply_change_plan | `e012fe49` |
| 3 | Wire suggested_project/area through reconcile_all + apply_change_plan | `c55c791b` |
| 4 | Add create_area, reopen_task, add_follow_up, change_status operations | `501ea8cf` |
| 5 | PostCaptureSummary shows "Linked existing" vs "Created" label + type | `2f18e81d` |
| 6 | ProjectFocus next action indicator + no-next-action warning | `bfa0f020` |
| 7 | Backend integration tests for entity reconciliation | `0b9424d0` |
| 8 | End-to-end test for task completion capture flow | `f7739489` |
| 9 | Task completion detection in capture_service._capture_as_note | `1e45e7e8` |
| 10 | Suggestion acceptance wires through apply_change_plan | `b17b9c67` |

**Test suite:** 378 passed, 2 skipped, all clean

---

## Remaining Items — Ranked by Priority

### Phase A — Backend Infrastructure (enabling features)

**A1: `change_batches` table + undo API** *(Section 10.6 / 13.5)*
- Add `change_batches` table
- Wire `change_batch_id` into `apply_change_plan` results
- Add `POST /api/v2/change-batches/:id/undo` endpoint
- `batch_undo` function exists but is stub — implement properly

**A2: Universal search API** *(Section 10.3)*
- `GET /api/v1/entities/search?q=` — cross-entity search
- Returns grouped results: projects, areas, tasks, notes, resources, people

**A3: `append_context` for projects and areas** *(Section 5.3)*
- `_apply_append_context` currently only works for tasks
- Projects and areas need a way to append note content as context
- Could be: append to `content` field, or store in `ai_meta.context_history`

---

### Phase B — UI: Missing Display Sections

**B1: NoteDetailView — "Extracted from this note" section** *(Section 8.11)*
- Show entities created from the note (tasks, people, projects)
- Show "Linked existing" (projects/areas that were matched and linked)
- Show "Suggestions" (pending AiSuggestions from this note)
- Uses `entity_events` + `entity_links` filtered by `derived_from` + source_note_id

**B2: Today view — "Projects with no next action" + "Waiting on people"** *(Section 8.2)*
- Add section: Projects with no pending/in_progress tasks
- Add section: People with tasks waiting on them (tasks where they're assigned, but blocked/waiting)

**B3: Review — AI Suggestions tab** *(Section 7.1 / 8.3)*
- Add "AI Suggestions" section/tab in Review.jsx
- Fetch pending `AiSuggestion` records
- Show accept/edit/dismiss actions
- Show source note, proposed operation, confidence, reason

**B4: AreaFocus — Maintenance-oriented sections** *(Section 8.7 / 12.8)*
- Area standard / purpose statement field (add to Area model if missing)
- Maintenance/routine tasks section
- "Needs attention" signals (no recent activity, overdue follow-ups, no active projects)
- Active projects list

**B5: PersonFocus — Open loops / Waiting on** *(Section 8.15 / 12.9)*
- "What do I owe this person?" — tasks assigned to this person that are pending
- "Waiting on from this person" — tasks where this person is linked but not assigned, and status is waiting
- Projects involving this person

**B6: ResourceDetail — Usefulness section** *(Section 8.13 / 12.10)*
- AI-generated or user-written "why this is useful" summary field
- Quick-create task from resource
- Quick-create note from resource

---

### Phase C — Operation Fixes

**C1: `assigned_to` links when creating tasks from capture**
- When `run_classify` creates tasks, people mentioned should get `assigned_to` links, not just `related`
- Fix in `ai_operation_applier._apply_create_task` — add `assigned_to` link for person_id if present

**C2: Improve `append_context` for projects/areas**
- When project/area is matched in capture, append captured content to the project's area's context
- Could store in `entity.ai_meta.context_history` as a list of {note_id, content, date}

---

## Iteration Plan (8 iterations)

| # | Name | Files | What |
|---|---|---|---|
| 11 | `change_batches` table + undo API | schema, applier, API | Add table, wire batch_id, implement undo endpoint |
| 12 | Universal entity search API | search API | `GET /api/v1/entities/search` grouped by type |
| 13 | NoteDetailView — Extracted from this note | NoteDetailView, service | Show created entities, linked existing, suggestions from note |
| 14 | Today — Projects with no next action + Waiting on people | Today.jsx | Add two new sections to Today |
| 15 | Review — AI Suggestions tab | Review.jsx, store | Fetch and display pending AiSuggestions with accept/dismiss |
| 16 | AreaFocus — maintenance-oriented refactor | AreaFocus.jsx | Add area standard, maintenance tasks, needs-attention signals |
| 17 | PersonFocus — open loops + waiting on | PersonFocus.jsx | Add "What do I owe" + "Waiting on" sections |
| 18 | Fix assigned_to links in task creation + append_context for projects | applier, extractor | C1 + C2 above |

---

## Files to Modify

### Backend
- `docs/SCHEMA.sql` — add `change_batches` table
- `services/ai_operation_applier.py` — wire batch_id, implement batch_undo properly
- `api/proposals.py` or new `api/change_batches.py` — undo endpoint
- `api/entities.py` — universal search endpoint
- `services/entity_service.py` — area standard field if needed

### Frontend
- `ui/src/views/NoteDetailView.jsx` — Extracted from this note section
- `ui/src/views/Today.jsx` — no-next-action projects + waiting-on-people sections
- `ui/src/views/Review.jsx` — AI Suggestions tab
- `ui/src/views/AreaFocus.jsx` — maintenance sections
- `ui/src/views/PersonFocus.jsx` — open loops sections
- `ui/src/stores/useStore.js` — add fetchSuggestions if needed

### Tests
- `tests/integration/test_closed_loops.py` — add tests for new endpoints/behaviors
- `tests/unit/test_ai_operation_applier.py` — add tests for batch_undo, append_context

---

## If Session Resets

1. Read this file
2. Check current iteration from ITERATIONS.md
3. Run `git status` to confirm clean state
4. Start the next iteration

## Validation Commands

```bash
# Backend tests
PYTHONPATH=. python3 -m pytest tests/unit/ tests/integration/ -q

# Frontend build
cd ui && npm run build

# Apply schema
psql $TEST_DATABASE_URL -f docs/SCHEMA.sql
```

## Commit Protocol

After each iteration:
```bash
git add <changed_files>
git commit -m "Iter N: <description>"
git push origin v3.5-ai-productivity-os
```
Update ITERATIONS.md after each commit.