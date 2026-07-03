# V5 Productivity & Trust Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the gap between backend intelligence and daily-use UI so Engram behaves like a trustworthy operating surface: activity updates change entity state visibly, suggestions are reviewable, Now surfaces full attention data, and affordances are honest.

**Architecture:** Ship in thin Loopsmith slices (same pattern as Activity Update v2 / Iteration 17). Each slice = one coherent behavior + tests + slice doc + `prd.json` task. Backend extraction and UI feedback ship together where they form one user-visible outcome. Defer Phase 4 multimodal and large relationship-editing refactors.

**Tech stack:** Flask `/api/v4`, React V5 views, Postgres test DB (5433), Loopsmith + LCS for autonomous delivery.

**Companion docs to create:** `docs/iterations/ITERATION_18_V5_PRODUCTIVITY_LOOP.md`, `SLICE_UI*.md` per slice below.

---

## Problem summary (consolidated from review)

### Confirmed bugs
1. **Duplicate Capture FAB** on entity detail — global `CaptureFab` in `App.jsx` plus thread-detail FAB in `V5ThreadDetail.jsx`.
2. **Add update drops API outcomes** — `handleUpdateSubmit` ignores `suggestions`, `extracted`, `target`; user sees no metadata changes.

### Structural gaps (AU8 + AU3 side effects)
3. **Activity update extraction is too narrow** — only `follow_up_at` + `tasks`; no `status`. Capture `progress_update` had status/blocked/priority but is **disabled when `thread_id` is set** (entity pages).
4. **Follow-up routing is wrong for closure + spin-off work** — explicit follow-up applies to the target entity even when text implies follow-up on a *new* blocker task.
5. **No suggestions review UI** — V4 inbox/suggestions removed; API + capture toast exist; no V5 surface.

### Prior review items (still relevant)
6. **Now underuses `/api/v4/today`** — missing blocked/waiting, follow-ups, recent notes, pending suggestions, coordination radar.
7. **`meeting_prep` / `current_load` not rendered** — backend ready for person detail.
8. **Recall placeholder "Search or ask…"** — search-only.
9. **Snooze / Send reminder / 👋** — all `follow_up_at += 24h` without honest labels or picker.
10. **Memory** — raw audit noise, Thread ID filter exposed, no grouping.
11. **Decisions** — count chip only; no list or manual record UI.
12. **Empty detail sections** always render (People, Related, References).

---

## Milestones

| Milestone | Slices | Ship criteria |
|-----------|--------|---------------|
| **M1 — Trust fixes** | UI-01, UI-02, UI-03 | No duplicate FAB; update save shows applied/suggested; can review pending suggestions |
| **M2 — Activity update intelligence** | AU10, AU11 | Status + spin-off follow-up routing; user's "done + security review + follow up next week" scenario covered by tests |
| **M3 — Daily surface** | UI-04, UI-05, UI-06, UI-07 | Now complete; meeting prep visible; honest action labels; Recall copy fixed |
| **M4 — Polish** | UI-08, UI-09, UI-10 | Memory digest; decisions section; collapse empty sections |

Recommend shipping **M1 + M2** before M3. M4 is optional polish once M1–M3 are in daily use.

---

## Slice index

| ID | Title | Risk | Files (primary) |
|----|-------|------|-----------------|
| UI-01 | Remove duplicate Capture FAB | low | `ui/src/views/V5ThreadDetail.jsx`, tests |
| UI-02 | Add update outcome panel + activity effect chips | medium | `V5ThreadDetail.jsx`, `v5.module.css`, tests |
| UI-03 | V5 Suggestions review sheet + shell badge | medium | new `V5ReviewSheet.jsx`, `App.jsx`, `TopBar.jsx`, tests |
| AU10 | Activity update status extraction + policy | medium | `services/v4_extraction.py`, `api/v4_entities.py`, `test_v4_activity_updates.py` |
| AU11 | Follow-up routing for closure + spin-off tasks | medium | `api/v4_entities.py`, extraction prompt, tests |
| UI-04 | Now — full today payload | medium | `V5Now.jsx`, `V5Now.test.jsx` |
| UI-05 | Person detail — meeting prep + current load | low | `v5ThreadDetailUtils.js`, `V5ThreadDetail.jsx`, tests |
| UI-06 | Honest follow-up actions (Snooze / Remind) | low | `V5Now.jsx`, `V5ThreadDetail.jsx`, `v5ThreadDetailUtils.js` |
| UI-07 | Recall copy + empty-state Ask handoff | low | `V5Recall.jsx`, tests |
| UI-08 | Memory — hide thread UUID filter, client digest | low | `V5Memory.jsx` |
| UI-09 | Decisions section on thread detail | low | `V5ThreadDetail.jsx`, `v4Client.js` |
| UI-10 | Collapse empty detail sections | low | `V5ThreadDetail.jsx` |

---

## Slice specifications

### UI-01 — Remove duplicate Capture FAB

**User problem:** Two identical + buttons on entity pages; confusing and error-prone on mobile.

**Change:** Set `showCaptureFab={false}` on `ThreadDetailContent` in `V5ThreadDetail.jsx` (or remove local FAB block). Global `CaptureFab` + `CaptureContext.defaultAttachment` already attach the current entity.

**Acceptance:**
- [ ] Exactly one capture entry point on `/tasks/:id`, `/projects/:id`, etc.
- [ ] Capture from entity page still pre-attaches thread context
- [ ] `CitationEntitySheet` behavior unchanged
- [ ] `npm test -- V5ThreadDetail App` passes

**Validation:**
```bash
cd ui && npm test -- V5ThreadDetail App
cd ui && npm run build
```

---

### UI-02 — Add update outcome panel

**User problem:** Saving an update feels like append-only text; applied follow-ups and suggestions are invisible.

**Change:** After successful `activityUpdates.create`, render a dismissible outcome block (below composer or as toast):

- Applied: follow-up date change, status change (after AU10)
- Suggested: list `create_task` / `update_task` suggestions with title + link to review (UI-03) or inline Accept/Dismiss if UI-03 not yet shipped
- Skipped: near-duplicate message (already partially handled via `updateError`)

Add optional chips on Activity rows when the save applied metadata (store in note `properties` or derive from linked events — prefer reading latest POST response client-side on save; persist chips via `properties.effects` on note if reload should show them).

**Acceptance:**
- [ ] Submitting update shows applied vs suggested counts when API returns them
- [ ] Reloaded detail reflects updated `follow_up_at` / status in Details chips
- [ ] Tests mock API response with `suggestions: [{...}]` and assert visible copy

**Validation:**
```bash
cd ui && npm test -- V5ThreadDetail
```

---

### UI-03 — V5 Suggestions review sheet

**User problem:** "Engram drafts, you deliver" is broken without a review surface.

**Change:** New `V5ReviewSheet` (sheet pattern like Ask/Recall):
- `GET /api/v4/suggestions?status=pending`
- Row: type, title/evidence, source note, Accept / Dismiss
- Open from: top-bar badge when `summary.suggestions_count > 0`, capture toast link, add-update outcome link
- Extend `App.jsx` to read `suggestions_count` from summary (alongside `today_count`)

**Acceptance:**
- [ ] Badge appears when pending suggestions exist
- [ ] Accept creates entity / applies update per existing API
- [ ] Capture toast links to review when `suggested > 0`
- [ ] Frontend tests for list + accept path (mocked API)

**Validation:**
```bash
cd ui && npm test -- V5ReviewSheet App TopBar V5CaptureSheet
TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/integration/test_v4_suggestions.py -q
```

---

### AU10 — Activity update status extraction

**User problem:** "This is done for now" does not close the task.

**Change:** Extend `ACTIVITY_UPDATE_SYSTEM_PROMPT` and schema:

```json
{
  "status": "done" | "waiting" | "blocked" | "in_progress" | null,
  "follow_up_at": "...",
  "tasks": [...]
}
```

In `create_activity_update` handler, mirror capture `progress_update` policy:
- **Auto-apply status** when explicit language + confidence ≥ `AUTO_APPLY_CONFIDENCE` (same threshold as capture)
- **Else** emit `update_task` suggestion with `fields.status`
- Valid statuses per entity type from existing `VALID_STATUS`

**Characterization tests (user scenario):**
```python
def test_activity_update_done_for_now_closes_task(client, app, mock_extraction):
    # task open → update text with "done for now" → status done (or suggestion if low confidence)

def test_activity_update_security_review_becomes_task_suggestion(client, app, mock_extraction):
    # extraction returns task "Clear security review" → suggestion, not auto-create
```

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/integration/test_v4_activity_updates.py -q
```

---

### AU11 — Follow-up routing for spin-off work

**User problem:** Follow-up on new blocker should not land on a task being closed.

**Policy:**
- If extracted `status` is `done` (or `cancelled`), do **not** set `follow_up_at` on target
- Put `follow_up_at` / `due_at` on the **task suggestion payload** when follow-up language refers to new work ("follow up next week on that" after introducing security review)
- Update extraction prompt with one-shot example matching user scenario

**Acceptance:**
- [ ] Integration test: done + new task + follow-up → target status done, no target follow_up, suggestion carries due/follow-up
- [ ] Explicit follow-up on open task still updates target (existing test preserved)

---

### UI-04 — Now full today payload

**Change:** Extend `transformTodayResponse` to map:
- `blocked_tasks`, `waiting_tasks`
- `overdue_follow_ups`, `follow_ups`, `upcoming_follow_ups`
- `recent_notes` (compact section)
- `pending_suggestions` → row linking to review sheet
- Subtitle uses `new_since_yesterday_count` from summary if useful

Keep three-band layout (needs / waiting / ambient) but enrich sources; don't flatten everything into one list.

**Validation:**
```bash
cd ui && npm test -- V5Now
TEST_DATABASE_URL=... ./venv/bin/pytest tests/integration/test_v4_today.py -q
```

---

### UI-05 — Meeting prep + current load

**Change:** In `v5ThreadDetailUtils.js`, add `buildMeetingPrep(detail)` and `buildCurrentLoad(detail)` for `entity.type === 'person'`. Render sections after Summary, before Add update:
- **Meeting prep:** headline, agenda items, recent notes
- **Current load:** assigned open tasks with last-heard context

**Validation:**
```bash
cd ui && npm test -- V5ThreadDetail
TEST_DATABASE_URL=... ./venv/bin/pytest tests/integration/test_v4_today.py::test_v4_person_detail_includes_runtime_meeting_prep -q
```

---

### UI-06 — Honest follow-up actions

**Change:** Replace opaque labels:
- `Snooze` → `Follow up tomorrow` (or date picker popover — start with honest label)
- `Send reminder` / `👋` → `Bump follow-up to tomorrow`
- Tooltip explaining the 24h behavior until picker ships

**Validation:** `npm test -- V5Now V5ThreadDetail`

---

### UI-07 — Recall copy + Ask handoff

**Change:** Either:
- (Minimal) Placeholder → `Search your workspace…`; empty results show "Ask Engram instead" button opening Ask sheet
- (Better) Detect question-shaped queries (`?`, who/what/when) and offer Ask

**Validation:** `npm test -- V5Recall`

---

### UI-08 — Memory digest (M4)

- Remove or hide Thread ID text field; optional thread name autocomplete later
- Collapse consecutive identical narrations on same entity
- Filter toggle: "Hide bookkeeping events"

---

### UI-09 — Decisions section (M4)

- `GET /api/v4/decisions?thread_id=` for current entity
- Section below Activity; header chip links to section
- Manual "Record decision" → `POST /api/v4/decisions`

---

### UI-10 — Collapse empty sections (M4)

- Do not render People / Related threads / References sections when empty (remove emptyHint paragraphs)

---

## End-to-end manual QA (after M1 + M2)

1. Open task detail → confirm **one** Capture button.
2. Add update with user scenario text → see outcome panel (status done, security task suggested, follow-up on suggestion not parent).
3. Open Review sheet → accept security task suggestion.
4. Verify task status `done`, new task exists, parent has no spurious follow-up.

---

## Loopsmith + LCS delivery setup

### What you already have

| Artifact | Location | Status |
|----------|----------|--------|
| Loopsmith source | `/Volumes/lex1t/dev/shared/repos/loopsmith` | Installed (venv + CLI) |
| LCS (coding standards) | `/Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards` | Repo present |
| LCS patch in Loopsmith | `loopsmith/src/loopsmith/executors/common.py` | **Already patched** (LCS compose hooks present) |
| Engram policy | `coding-loop-policy.yaml` | Present (1800s executor timeout for UI tasks) |
| Engram runtime | `.codloop/` | Present; last iteration **completed** (6/6 hardening tasks) |
| Operational wrapper | `~/.openclaw/.../loopsmith-coding/scripts/loopsmithctl.py` | Ready; doctor shows OpenCode **ready** |
| Recovery helper | `scripts/loopsmith_recover.sh` | Present |

You do **not** need a greenfield Loopsmith install for Engram. You need a **new iteration contract** (`prd.json` + slice docs) and optionally confirm LCS env is enabled for executor prompts.

### Installing / enabling LCS (if not already sourced)

LCS is a **prompt composition layer** on top of Loopsmith — it injects `PREAMBLE.md` + selected skills (TDD, incremental-implementation, git-workflow) into each executor launch.

```bash
# One-time (or after Loopsmith upgrade): patch Loopsmith to compose LCS prompts
cd /Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards
LOOPSMITH_REPO=/Volumes/lex1t/dev/shared/repos/loopsmith \
  bash install/install-loopsmith.sh

# Verify integration
bash scripts/validate-lcs-integration.sh
```

Enable for each run:

```bash
# Option A: wrappers (recommended)
bash /Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards/scripts/loopsmithctl-lcs.sh \
  doctor --repo /Volumes/lex1t/dev/shared/repos/engram --strict

# Option B: manual env
export LCS_ENABLED=1
export LCS_REPO_ROOT=/Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards
python3 ~/.openclaw/.../loopsmith-coding/scripts/loopsmithctl.py host-run --repo .../engram
```

Disable for one command: `LCS_ENABLED=0`.

### How a Loopsmith iteration works for this plan

```mermaid
flowchart LR
  A[Write prd.json tasks] --> B[Slice docs SLICE_UI*.md]
  B --> C[loopsmithctl doctor --strict]
  C --> D[host-run or host-run --drain]
  D --> E[Executor in git worktree]
  E --> F[validationCommands in prd task]
  F --> G{pass?}
  G -->|yes| H[passes: true + commit on main]
  G -->|no| I[recover / repair / next executor]
  H --> J[Update EXECUTION-TRACKER.md]
```

**Step-by-step for Iteration 18:**

1. **Archive** completed hardening overlay — copy `prd.json` to `docs/iterations/archive/prd-v5-hardening.json` (optional); don't delete history.

2. **Write iteration contract** — `docs/iterations/ITERATION_18_V5_PRODUCTIVITY_LOOP.md` using repo template.

3. **Replace `prd.json`** with new tasks (UI-01 … AU11 …). Each task needs:
   - `id`, `title`, `description`, `risk`
   - `acceptanceCriteria` (testable bullets)
   - `validationCommands` (exact bash — test DB port 5433 for pytest)
   - `passes: false`, `blocked: false`
   - Optional LCS: `"skills": ["tdd", "incremental-implementation", "git-workflow"]` per task

4. **Create slice docs** — `docs/iterations/SLICE_UI01_duplicate-fab.md`, etc. (mirror AU0–AU9 format).

5. **Validate PRD + skills:**
   ```bash
   bash /Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards/scripts/validate-prd-lcs.sh \
     /Volumes/lex1t/dev/shared/repos/engram/prd.json
   ```

6. **Readiness check:**
   ```bash
   bash .../loopsmithctl-lcs.sh doctor --repo /Volumes/lex1t/dev/shared/repos/engram --strict
   ```

7. **Run one slice at a time** (recommended for medium-risk AU10/AU11):
   ```bash
   bash .../loopsmithctl-lcs.sh host-run --repo /Volumes/lex1t/dev/shared/repos/engram --task-id ui-01-duplicate-fab
   ```

8. **Or drain M1** after UI-01–UI-03 + AU10–AU11 tasks are defined:
   ```bash
   bash .../loopsmithctl-lcs.sh host-run --repo /Volumes/lex1t/dev/shared/repos/engram --drain
   ```

9. **Inspect / recover** if stuck:
   ```bash
   bash .../loopsmithctl-lcs.sh status --repo /Volumes/lex1t/dev/shared/repos/engram
   bash scripts/loopsmith_recover.sh /Volumes/lex1t/dev/shared/repos/engram inspect
   ```

10. **Publish** (when policy enables — currently `pushEnabled: false`):
    ```bash
    bash .../loopsmithctl-lcs.sh publish --repo ... <attempt-id> --push --pr
    ```

### prd.json task shape (example for UI-01)

```json
{
  "id": "ui-01-duplicate-fab",
  "title": "Remove duplicate Capture FAB on thread detail",
  "kind": "fix",
  "skills": ["tdd", "git-workflow"],
  "risk": "low",
  "acceptanceCriteria": [
    "Entity detail pages show exactly one capture entry point",
    "Capture from entity route still attaches default thread context",
    "V5ThreadDetail and App tests pass"
  ],
  "validationCommands": [
    "cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test -- V5ThreadDetail App",
    "cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run build"
  ],
  "passes": false,
  "blocked": false
}
```

### What Loopsmith does *not* do

- Does not replace product decisions (e.g. auto-apply vs suggest thresholds) — encode those in slice specs first.
- Does not run against production DB — tests must use port 5433.
- Does not deploy — manual `scripts/engram-deploy.sh` after milestone validation + backup.

---

## Suggested execution order

1. UI-01 (5 min, unblocks UX confusion)
2. UI-02 (feedback loop — pairs with backend work)
3. AU10 + AU11 (backend — can be one Loopsmith task or two)
4. UI-03 (review surface — unlocks value from AU10/11 suggestions)
5. UI-04, UI-05, UI-06, UI-07 (daily surface — parallelizable)
6. M4 slices as time permits

---

## Non-goals (this iteration)

- Phase 4 multimodal capture (audio/image/voice FAB)
- Full relationship create/link UI on detail pages
- `V5Settings` / Lighthouse a11y audit
- Schema migrations (additive-only if ever needed; prefer extraction + suggestion payloads)
- Re-enabling capture `progress_update` on thread-attached capture (keep Add update as sole activity path; port semantics instead)

---

## Tracker updates

When starting Iteration 18, update `EXECUTION-TRACKER.md`:
- Active loop: V5 Productivity & Trust
- Milestone progress: M1 → M2 → M3
- Link this plan and `ITERATION_18_*.md`

---

## Self-review (spec coverage)

| Requirement | Slice |
|-------------|-------|
| Duplicate FAB | UI-01 |
| Update metadata visibility | UI-02, AU10, AU11 |
| User scenario (done + security + follow-up) | AU10, AU11 + tests |
| Suggestions review | UI-03 |
| Now completeness | UI-04 |
| Meeting prep | UI-05 |
| Honest snooze/remind | UI-06 |
| Recall copy | UI-07 |
| Memory noise | UI-08 |
| Decisions | UI-09 |
| Empty sections | UI-10 |
| Loopsmith delivery | This section + new prd.json |
