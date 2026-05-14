# PRD Implementation Plan — AI-Assisted Productivity OS

## Executive Summary

The current codebase (~70% implemented) has entity reconciliation infrastructure (`entity_reconciliation_service.py`) and AI operation apply logic (`ai_operation_applier.py`) but the **classify pipeline doesn't use them**. Extracted people/tasks go to `ai_meta` instead of through reconciliation. This is the single critical gap.

**Token budget strategy:** Each iteration modifies ≤3 files, produces ≤150 net lines of diff, is validated and merged before the next starts.

---

## Phase 1 — Entity Reconciliation in Classify Pipeline

### Iteration 1: Wire extracted people through reconciliation

**Files changed:** `services/ai_pipeline.py`, `tests/unit/test_ai_pipeline.py`

**Changes:**
1. In `run_classify`: after `extract()` returns `extracted_people`, call `reconcile_person()` for each
2. For matched person: use `apply_change_plan()` with `link_entity` operation (confidence from reconciliation)
3. For new person (no match): use `apply_change_plan()` with `create_person` operation
4. Log `ai_extracted` event with `matched_entity_id` vs `created_new` distinction
5. Remove the `extracted_people` → `ai_meta` store path (no longer needed)

**Verification:**
- Unit test: existing person "Sarosh" → linked, not created
- Unit test: new person → created with `derived_from` link to source note
- Backend tests pass

---

### Iteration 2: Wire extracted tasks through reconciliation

**Files changed:** `services/ai_pipeline.py`, `services/capture_service.py`

**Changes:**
1. `run_classify` already extracts inline checkbox tasks via `inline_extract()` at line ~112
2. Add call to `reconcile_all(detected)` where `detected` includes `extracted_tasks` + `inline_tasks`
3. Build a `change_plan` from reconciled results and call `apply_change_plan()`
4. Ensure all created tasks have `derived_from` link to source note
5. In `capture_service._capture_as_note`: ensure the inline task path also uses reconciliation (it already calls `reconcile_all`)

**Verification:**
- Unit test: existing task "Send feedback to Himmat" matched when capture says "Sent feedback to Himmat"
- Integration test: capture with similar task name → matched, not duplicated
- Backend tests pass

---

### Iteration 3: Fix `suggested_project`/`suggested_area` to use full reconciliation

**Files changed:** `services/ai_pipeline.py`

**Changes:**
1. Replace `_create_or_link_project(entity, name, conf)` with:
   - Call `reconcile_project(name)` first (not just exact title filter)
   - If match with high confidence: call `apply_change_plan` with `append_context` operation
   - If no match: call `apply_change_plan` with `create_project` operation
   - Link source note with `derived_from` (not just `related`)
2. Same refactor for `_create_or_link_area` → `reconcile_area` + `apply_change_plan`
3. Ensure link type is `derived_from` for created entities, `mentions` for existing entity references
4. Store `detected_entities` list in `ai_meta` for UI display (shows match vs create decisions)

**Verification:**
- Unit test: "Agent Memory Migration" with existing project → linked, confidence shows match
- Unit test: new project name → created
- Backend tests pass

---

## Phase 2 — Missing Operations

### Iteration 4: Add `reopen_existing_task` and `add_follow_up` operations

**Files changed:** `services/ai_operation_applier.py`, `tests/unit/test_ai_pipeline.py`

**Changes:**
1. Add `_apply_reopen_task(change, actor)` — set status back to `pending`
2. Add `_apply_add_follow_up(change, actor)` — set `follow_up_at` on target entity
3. Add `_apply_change_status(change, actor)` — generic status change for projects/areas
4. Update `_apply_operation()` dispatch to handle new operations
5. Update `_infer_operation_type()` mapping
6. Add unit tests for each operation

**Verification:**
- Unit tests: `reopen_task`, `add_follow_up`, `change_status` operations
- Backend tests pass

---

## Phase 3 — UI Visibility

### Iteration 5: PostCaptureSummary shows match context

**Files changed:** `ui/src/components/capture/PostCaptureSummary.jsx` (if exists), or create it; `services/capture_service.py`

**Changes:**
1. Ensure `process_capture()` return value includes `detected_entities` with match info:
   ```json
   {
     "matched": [{"type": "person", "name": "Sarosh", "entity_id": "...", "action": "linked"}],
     "created": [{"type": "task", "title": "Ask Sanket for estimate", "entity_id": "..."}],
     "suggestions": [...]
   }
   ```
2. Wire `PostCaptureSummary` to display "Linked existing: Agent Memory Migration" vs "Created: Send note" distinctly
3. Add "Review" button → navigate to NoteDetailView with AI suggestions highlighted
4. Add "Undo" → call batch undo if implemented

**Verification:**
- Frontend build passes
- Manual: capture → PostCaptureSummary shows linked vs created with entity names

---

### Iteration 6: ProjectFocus "next action" and "no next action" warning

**Files changed:** `ui/src/views/ProjectFocus.jsx`, `ui/src/views/ProjectFocus.module.css`

**Changes:**
1. Add "Next action" section — find the first `pending` task linked to this project via `parent` relationship, ordered by `created_at`
2. If active project has no open tasks: show warning banner "No next action — add one to keep project visible in Today"
3. Add "Add task" button pre-linked to this project
4. Show completion count vs total count prominently

**Verification:**
- Frontend build passes
- Manual: project with tasks shows next action; project without tasks shows warning

---

## Phase 4 — Testing and Integration

### Iteration 7: Backend integration tests for entity reconciliation

**Files changed:** `tests/integration/test_closed_loops.py` (extend)

**Tests to add:**
1. `test_capture_reuses_existing_person` — capture "Met Sarosh today" → Sarosh linked, not created
2. `test_capture_reuses_existing_project` — capture mentions existing project → linked
3. `test_capture_reuses_existing_resource_by_url` — capture with URL → resource reused
4. `test_capture_completes_existing_task` — capture "Sent feedback" → existing task completed or suggestion
5. `test_capture_creates_new_when_no_match` — capture with truly new entities → created with `derived_from` link
6. `test_classify_pipeline_reconciles_extracted_people` — verify people go through reconciliation not ai_meta only

**Verification:**
- All new tests pass
- No regressions in existing test suite

---

### Iteration 8: End-to-end test for task completion flow

**Files changed:** `tests/integration/test_closed_loops.py`

**Tests:**
1. Create task "Send feedback to Himmat"
2. Capture "Sent feedback to Himmat. Waiting for response."
3. Verify original task status changed OR suggestion created
4. Verify waiting-on task created or suggested
5. Verify Himmat linked to source note

**Verification:**
- Tests pass
- Backend full suite passes

---

## Phase 5 — Edge Cases and Polish

### Iteration 9: Task completion interpretation in capture

**Files changed:** `services/capture_service.py`, `services/extractor.py`

**Changes:**
1. In `_capture_as_note` flow: detect task completion language ("sent", "completed", "finished", "done")
2. For detected completion: call `reconcile_task()` to find matching pending task
3. If match found: use `apply_change_plan` with `complete_task` operation
4. Also create follow-up task "Waiting on X" if capture implies waiting state
5. Add `reopen_existing_task` for "undo" detection in future capture

**Verification:**
- Integration test for task completion capture
- Backend tests pass

---

### Iteration 10: Suggestion acceptance wires full change plan

**Files changed:** `api/proposals.py`, `services/ai_operation_applier.py`

**Changes:**
1. When user accepts a suggestion, call `apply_change_plan()` with the suggestion's payload
2. Ensure all acceptance paths (from NoteDetailView, Review view, PostCaptureSummary) use consistent apply logic
3. Record `ai_suggestion_accepted` event with actor and source note
4. Verify the accepted change creates proper `derived_from` link to source note

**Verification:**
- Manual: accept suggestion → entity created with `derived_from` link
- Backend tests pass

---

## Not in Scope (defer to future sprints)

- Semantic embedding similarity for matching (uses embeddings API, needs separate iteration)
- `change_batches` table for batch undo (medium complexity, can use entity_events chain)
- User correction history as matching signal (needs data collection first)
- Separate full Review queue view (embedded suggestions sufficient for now)
- ResourceDetail "why useful" field (needs summarization API)

---

## Validation Commands (per iteration)

Each iteration must pass before merging:
```bash
# Backend
PYTHONPATH=. python3 -m pytest tests/unit/test_ai_pipeline.py -q

# Integration
PYTHONPATH=. python3 -m pytest tests/integration/test_closed_loops.py -q

# Full suite
PYTHONPATH=. python3 -m pytest -q --cov=. --cov-report=term-missing 2>&1 | tail -5

# Frontend
cd ui && npm run build
```

---

## File Ownership Map

| File | Owner iteration |
|---|---|
| `services/ai_pipeline.py` | Iterations 1, 2, 3 |
| `services/entity_reconciliation_service.py` | Iterations 1, 2, 3 |
| `services/ai_operation_applier.py` | Iterations 4, 10 |
| `services/capture_service.py` | Iterations 2, 9 |
| `api/proposals.py` | Iteration 10 |
| `ui/src/views/ProjectFocus.jsx` | Iteration 6 |
| `ui/src/components/capture/PostCaptureSummary.jsx` | Iteration 5 |
| `tests/unit/test_ai_pipeline.py` | Iterations 1, 2, 3, 4 |
| `tests/integration/test_closed_loops.py` | Iterations 7, 8, 9 |

---

## Execution Order

```
Iteration 1  →  Iteration 2  →  Iteration 3  →  Iteration 4  →
Iteration 5  →  Iteration 6  →  Iteration 7  →  Iteration 8  →
Iteration 9  →  Iteration 10
```

Each step: implement → test → build → merge to `v3.5-ai-productivity-os` → PR → verify main passes → next.

**Estimated total**: 10 iterations. Each iteration targets 1-2 hours of work + validation.