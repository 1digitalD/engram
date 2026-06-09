# Engram v4: World Model First — Implementation Plan

Status: ACTIVE. This plan supersedes the "Engram v4: Prioritized Improvement Proposal" (June 2026).
Rationale and prod-data evidence: see plan review in session history; summary below.

## Why this plan exists

Production data (2026-05-30 → 2026-06-09, 274 entities) showed the bottleneck is the
world-model maintenance layer, not the presentation layer:

- 170/274 entities created manually; 284 user-added links vs 132 agent-added.
- AI suggestion accept rate: 15% (4 accepted / 23 dismissed). All 20 `create_*`
  suggestions dismissed; several were near-duplicates of existing projects that
  title-only embedding matching (threshold 0.60) failed to map.
- Reconciliation "update" can only set status/due_at/follow_up_at — pasted standup
  progress never lands on entities as activity updates.
- Attention is date-driven but only 20/92 active tasks have due_at; 4 `blocks` links
  exist; 60+ open tasks are invisible to Today.
- Captures are manager-shaped (per-person standup updates about team members' work);
  the product treats everything as a flat personal todo list.

Product decisions locked with Dan (2026-06-09):

1. **Team model:** tasks assigned to others are *monitored delegations* with auto
   follow-up cadence and "gone quiet" signals — distinct from Dan's own actions.
2. **Auto-apply:** aggressive auto-apply with a per-capture changelog and one-click
   undo. Review queue handles only genuinely ambiguous calls.
3. **Impact:** Dan sets priority at project level; tasks inherit; AI may *suggest*
   priority changes, never apply them.

North-star metrics, computed from real data before and after each phase:
- Suggestion accept rate (baseline 15%).
- Share of entity state-changes made by agent vs user (baseline ~30% agent).
- Count of open tasks invisible to any surface (baseline ~60).

## Non-negotiable safety rules (supersede older "clean cutover" rules)

The v4 principle "no migration, data can be deleted" is **obsolete**: production now
holds real data that must be preserved.

1. **Schema changes are additive-only** (new columns nullable or defaulted, new
   tables, new enum values). Never drop/rename columns or tables while data exists.
   Each schema change ships as an idempotent script in `scripts/migrations/`
   (numbered, e.g. `001_add_priority.sql`), applied with explicit psql invocation —
   never by re-running `init-db` (which wipes data).
2. **Snapshot before any prod schema change or deploy:**
   `pg_dump postgresql://engram:engram@localhost:5432/engram > backups/engram_$(date +%Y%m%d_%H%M%S).sql`
   `backups/` is gitignored. Verify the dump is non-empty before proceeding.
3. **Tests never touch prod.** Tests run only against the isolated test DB
   (`docker-compose.test.yml`, port 5433, tmpfs). Never export `DATABASE_URL`
   pointing at 5432 in a test context. Never run destructive SQL against 5432.
4. **Prod DB access during development is read-only** except via the running API or
   explicitly reviewed migration scripts.
5. The live launchd service keeps running against `main`. Worktree code never points
   at the prod DB.

## Working method

- **Worktree per slice.** `git worktree add ../engram-<slice-id> -b slice/<slice-id>`
  (or the EnterWorktree harness equivalent). All work happens there; `main` stays
  deployable at all times.
- **TDD.** Red: write the failing test first (unit or integration against the test
  DB). Green: minimal implementation. Refactor. New behavior without a test does not
  merge.
- **Two-tier model testing.** pytest runs fully offline: OpenAI calls are mocked
  with recorded/fixture responses (existing pattern in tests). Live model quality is
  measured separately by the replay harness (Slice A0), run manually per slice —
  never inside CI/pytest.
- **Merge gate per slice** (all must pass before merging to main):
  1. Full backend suite green (`pytest`).
  2. Frontend tests green (`cd ui && npm test`) and build passes (`npm run build`).
  3. Live manual QA on the local dev stack (Flask + Vite against the test or a
     scratch DB) exercising the slice's acceptance criteria; evidence (curl output
     and/or screenshots) recorded in the slice doc.
  4. Replay-harness metrics not regressed (for slices touching extraction or
     reconciliation).
  5. Slice doc updated with results; CHANGELOG-style entry in EXECUTION-TRACKER.md.
  Then: merge slice branch to `main` (fast-forward or merge commit), delete the
  worktree and branch. Only then start the next slice.
- **Deploy cadence:** at the end of each *phase* (not each slice): snapshot prod DB,
  run any pending migration scripts, `./scripts/engram-deploy.sh`, then smoke-test
  `GET /api/v4/health`, `GET /api/v4/today`, and one capture round-trip. If the smoke
  test fails: restore the LaunchAgent to the previous commit and investigate.

### Per-slice artifacts

| Artifact | Location |
|---|---|
| Slice doc (goal, acceptance criteria, QA evidence, metrics) | `docs/iterations/SLICE_<ID>_<NAME>.md` |
| Tests (written first) | `tests/unit/`, `tests/integration/`, `ui/src/**/*.test.jsx` |
| Migration script (if schema changes) | `scripts/migrations/NNN_<name>.sql` |
| Prod snapshot (before migration/deploy) | `backups/` (gitignored) |
| Tracker update | `EXECUTION-TRACKER.md` |

---

## Phase A — Reconciliation matching (fix the clutch)

### Slice A0 — Safety net + replay harness (no behavior change)
The TDD baseline for the whole plan.
- Add `backups/` to `.gitignore`; add `scripts/backup_prod.sh` (pg_dump + non-empty check).
- Add `scripts/export_replay_fixtures.py`: reads prod (read-only) and freezes to
  `tests/fixtures/replay/`: the 23 dismissed + 4 accepted suggestions, their source
  notes' content, and the entity catalog (id/type/title/content snippet) as of export.
  Labels: each dismissed `create_*` whose title near-duplicates an existing entity is
  labeled `expected: update|link`; genuinely-new ones labeled `expected: new`;
  accepted ones labeled with their accepted action. Labels reviewed by hand once,
  committed.
- Add `scripts/replay_eval.py`: runs extraction+reconciliation (live model) over the
  fixture notes against the frozen catalog, scores decisions vs labels, prints
  accept-rate-proxy metrics, writes `docs/iterations/replay_results/<timestamp>.json`.
- Record the baseline run.
- Amend `AGENTS.md` + `docs/V4_PRINCIPLES.md`: data-preservation rules above replace
  the "no migration / data deletable" clauses.
- Acceptance: baseline metrics recorded; backup script produces a restorable dump
  (verified by restoring into the test DB); full suite green.

### Slice A1 — Batch embeddings in reconciliation (behavior-preserving perf)
- Red: test asserting one embeddings API call (mocked) for N candidates, identical
  match output to the per-candidate path.
- Refactor `_find_similar` → batch: embed all candidate titles in one call; load each
  entity type's chunk set once per capture and reuse across candidates.
- Acceptance: capture with 8 candidates makes 1 embedding call; replay metrics
  unchanged; suite green.

### Slice A2 — Richer matching context
- Match on candidate title + content + evidence sentence against entity title +
  content + recent activity-update text (embed a composed document, not bare title).
- Threshold/TOP_K re-tuned against the replay set.
- Acceptance: replay harness shows the labeled duplicate-creates ("Conversation
  history search functionality", "Agent memory utilization", "Deals/Admin agent
  family support", …) now match their existing entities; no regression on
  `expected: new` labels; suite green.

### Slice A3 — Full project/area catalog in the reconciler prompt
- For `project` and `area` candidates, include the complete active catalog
  (id + title + one-line summary; ~50 rows) in the reconciliation prompt instead of
  relying solely on embedding hits. (Deliberately inverts the old proposal's 4b.)
- Token budget guard: cap catalog block at ~2k tokens, truncate by recency.
- Acceptance: replay duplicate-create rate for projects/areas → 0 on labeled set;
  suite green. **Deploy Phase A** (snapshot → deploy → smoke).

---

## Phase B — Progress propagation + undo (the missing primitive)

### Slice B1 — `progress_update` reconciliation action, end to end
- Reconciler may return `action: "progress_update"` with `target_id` and a concise
  `update_text` for note segments describing an existing entity's state.
- Capture applies it auto (additive, safe): creates an activity-update entity linked
  `activity_update` → target (reuse the existing activity-update machinery from
  `create_activity_update`), writes an EntityEvent, surfaces in the entity detail
  `activity_updates` section (UI already renders these).
- Red first: integration test — pasted standup fixture fans out into activity
  updates on the matched project/person; nothing created as a suggestion.
- Acceptance: replaying one real standup note produces ≥3 activity updates on
  existing entities and 0 `create_project` suggestions; suite green.

### Slice B2 — Auto-apply state changes carried by updates
- `update` decisions with confidence ≥ 0.8 auto-apply status/due_at/follow_up_at
  (today they do; extend to status changes arriving via `progress_update`, e.g.
  "delivered" → done, "waiting on X" → waiting) with EntityEvents recording old/new.
- Guard: status transitions validated against the existing status vocabulary.
- Acceptance: fixture note "shipped the HITL piece" moves the matched task to done
  automatically with an auditable event; low-confidence cases still become
  suggestions; suite green.

### Slice B3 — Capture changelog + one-click undo
- Backend: `GET /api/v4/entities/:id/capture-changes` (everything the agent applied
  for a capture, from EntityEvents) and `POST /api/v4/events/:id/revert` — inverts
  one applied change using the event's old/new values (status/date/title revert,
  link removal, activity-update archival, entity creation → lifecycle deleted).
- Frontend: "What the agent did" panel on the note detail + capture response toast;
  each row has Revert.
- Red first: revert round-trip tests per change type.
- Acceptance: every auto-applied change type can be reverted in one click and the
  revert is itself event-logged; suite + UI tests green. **Deploy Phase B.**

---

## Phase C — Delegation model (manager-shaped core)

### Slice C1 — Delegation detection + cadence
- Migration `NNN_owner_identity.sql`: none needed for entities; add a small
  `app_settings` table (key/value) storing the owner identity ("Dan"/aliases) and
  per-person cadence overrides.
- Tasks with `assigned_to` linking to a person who is not the owner are delegations:
  on creation/assignment, auto-set `follow_up_at = now + cadence` (default 3 working
  days) unless explicitly dated. Activity update touching the task pushes
  `follow_up_at` forward by the cadence.
- Acceptance: capture "Akash: design GTM trigger doc" yields a task assigned to
  Akash with follow_up_at ≈ +3 working days; an activity update refreshes it; suite
  green.

### Slice C2 — "Gone quiet" surfacing in /today
- `/api/v4/today` gains `delegations_quiet`: delegations whose follow_up_at has
  passed with no activity update since, with `days_silent` and `last_update`
  preview. Computed with batched queries (no N+1).
- Today UI: "Delegations needing a nudge" section.
- Acceptance: a delegation with no update past cadence appears with correct
  days_silent; one with a fresh update does not; suite + UI green.

### Slice C3 — Person workspace: load + last-heard
- Person detail gains `current_load`: open tasks assigned to them, each with last
  activity-update timestamp and preview ("last heard").
- Acceptance: Akash's page lists his open tasks with last-heard timestamps; suite +
  UI green.

### Slice C4 — Blocks links from updates
- Extraction/reconciliation: "waiting on X" / "blocked by Y" statements produce
  `blocks` links (target task/person's task) and status `blocked`/`waiting` where
  confident; semantic relationship validation (old proposal 4d) enforced on both
  manual and auto-apply paths, including `blocks` cycle detection.
- Acceptance: fixture standup with a blocker statement yields a blocks link +
  blocked status; invalid/cyclic links rejected with clear errors; suite green.
  **Deploy Phase C.**

---

## Phase D — Impact + the real spotlight

### Slice D1 — Project priority, inherited by tasks
- Priority already lives in `properties.priority`; formalize: UI control on project
  workspace (urgent/high/medium/low), tasks inherit parent project's priority for
  ranking when they lack their own.
- One-time assist: a small script listing active projects for Dan to set initial
  priorities quickly (UI bulk-edit on Projects list).
- Acceptance: task with no own priority ranks using its project's; suite + UI green.

### Slice D2 — AI priority nudges (suggestions only)
- During capture, if update language signals escalation ("P1", leadership ask,
  deadline pulled in) for an entity whose priority is lower, emit a
  `change_priority` suggestion. Never auto-applied.
- Acceptance: escalation fixture produces a pending suggestion; accepting it updates
  priority with an event; suite green.

### Slice D3 — Server-side attention v2
- Attention computed in `/today` with batched relationship context passed through
  the existing `context` parameter of `attention_for_entity` (no DB queries inside
  the pure function). Inputs: inherited impact, urgency (dates), staleness
  (delegation silence, last activity), blockage (blocks chains). Undated tasks rank
  via impact + staleness, so the ~60 invisible open tasks participate.
- Acceptance: unit tests pin the scoring table; an undated high-priority stale task
  outranks a dated low-priority one per spec; /today p95 latency within 2x of
  baseline on prod-sized data; suite green.

### Slice D4 — Today restructure + day reviewed
- Today regroups to: **Your actions**, **Delegations needing a nudge** (from C2),
  **Deadlines ahead** (due tomorrow / this week, collapsed), plus existing
  overdue/due-today on top. "Mark day reviewed" button → EntityEvent
  `day_reviewed` (resolve the entity_id FK question: nullable column or a singleton
  system entity — decide in-slice, additively).
- Acceptance: sections render from one /today call; reviewed state persists across
  reloads and resets at midnight; suite + UI green. **Deploy Phase D.**

---

## Phase E — Shell simplification (kept from original proposal)

### Slice E1 — `/api/v4/summary` + sidebar counts
Single endpoint returning sidebar/Home counts (incl. `last_reviewed_at`); replace
`useSidebarCounts`'s 3 calls. Server-side count logic is the single source of truth
(port the dedupe logic from `ui/src/utils/today.js`, with a parity test).

### Slice E2 — Home → stats + workflow shortcuts
Remove the five duplicate entity-list panels; keep hero stats (from /summary) +
three shortcut cards.

### Slice E3 — Inbox + Review merge
Inbox = capture form + needs-review queue + recent captures. `/suggestions` stays
as deep-link route, leaves the sidebar.

### Slice E4 — Quick capture textarea + sidebar cleanup
Plain `<textarea>` in QuickActionBar; Agent Activity out of the sidebar (route
kept). **Deploy Phase E.**

---

## Phase F — Proactive monitoring

### Slice F1 — Stale projects + suggested archival
`stale_projects` (no activity update/event in 14 days) and `suggested_archival`
(30+ days) in /today + Home stat; archival is a suggestion, never automatic.

### Slice F2 — Since-yesterday diff
"N new items since yesterday" banner computed from entity changes in the last 24h
(or since last `day_reviewed`) intersecting today's actionable set. **Deploy
Phase F**, then re-run north-star metrics and compare to baseline.

---

## Explicitly deferred

- Intent decay and intent-based boosts (intents barely fire in prod; revisit after
  Phase B changes capture behavior).
- Correction-feedback into the extraction prompt (old 6a): dismissals are too noisy
  a signal today; revisit once accept rate is healthy and B3 gives clean
  override events to learn from.
- Removing EXISTING_ENTITIES from the extraction prompt (old 4b): inverted by A3.
- Inline editing on Today (old 6b) and dependency badges (old 6c): nice-to-have
  polish after D4 settles.
