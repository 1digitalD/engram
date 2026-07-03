# Engram — Execution Tracker

Fresh-agent handoff for the current v4 baseline. Use this to get oriented quickly,
then read the active source docs before changing code.

Last updated: 2026-07-03
Branch: `main`
Status: **Iteration 19 in progress** — M0-M2 (SQ-00..SQ-06) shipped via direct sub-agent
worktrees 2026-07-02/03; M3-M4 (SQ-07..SQ-11) running via Loopsmith drain.

Runtime baseline: `/api/v4` only, fresh Postgres + pgvector schema, write-enabled MCP
aligned with the active API.

## Current loop: Iteration 19 — Signal Quality & Capture Intelligence (2026-07-02)

- Contract/Plan: `docs/iterations/ITERATION_19_SIGNAL_QUALITY_PLAN.md`
- Loopsmith overlay: `prd.json` (iteration `v5-signal-quality-loop`, SQ-07..SQ-11 only)
- Archived prd: `docs/iterations/archive/prd-v5-productivity.json`

### Milestones

| Milestone | Slices | Status |
|-----------|--------|--------|
| M0 Model reallocation | SQ-00 | done (`.env`, not in git) |
| M1 Broken trust primitives | SQ-01, SQ-02, SQ-03, SQ-04 | done (`8433f2cb`, `5c986f5c`, `dd448bca`, `feaf3b15`) |
| M2 Route by intent | SQ-05, SQ-06 | done (`88d4f53d`, `4c991732`) |
| M3 Precision extraction | SQ-07, SQ-08, SQ-09 | running via Loopsmith drain |
| M4 Learning loop | SQ-10, SQ-11 | queued behind M3 |

M0-M2 were delivered directly via `Agent` tool sub-agents in isolated git worktrees
(TDD, fast-forward merge to main), not via Loopsmith — orchestrated inline per explicit
instruction rather than through `prd.json`. M3-M4 use the standard Loopsmith + LCS drain
pattern below, with tasks chained serially (`dependencies`) since they share
`api/v4_entities.py`.

### Known pre-existing failures (not in scope)

- `tests/integration/test_v4_search.py::test_semantic_search_with_mocked_embeddings`,
  `::test_semantic_search_filters_weak_matches`, `::test_hybrid_search_uses_rrf` — fail
  identically on unmodified main (environmental/pgvector quirk), confirmed via
  stash-and-rerun during SQ-02. Do not attempt to fix as part of Iteration 19.

## Previous loop: Iteration 18 — V5 Productivity & Trust (2026-07-02) — complete

- Contract: `docs/iterations/ITERATION_18_V5_PRODUCTIVITY_LOOP.md`
- Plan: `docs/iterations/V5_PRODUCTIVITY_IMPLEMENTATION_PLAN.md`
- Full plan: `docs/superpowers/plans/2026-07-02-v5-productivity-trust-loop.md`
- Loopsmith overlay: `prd.json` (iteration `v5-productivity-trust-loop`)
- Archived prd: `docs/iterations/archive/prd-v5-hardening.json`
- Slice docs: `SLICE_UI01_duplicate-fab.md` … `SLICE_UI10_collapse-empty-sections.md`, `SLICE_AU10_status-extraction.md`, `SLICE_AU11_follow-up-routing.md`

### Milestones

| Milestone | Tasks | Status |
|-----------|-------|--------|
| M1 Trust fixes | UI-01, UI-02, UI-03 | done |
| M2 Activity intelligence | AU10, AU11 | done |
| M3 Daily surface | UI-04 – UI-07 | done |
| M4 Polish | UI-08 – UI-10 | done |

### Iteration 18 outcome

- Drain completed 2026-07-02 (UI-04→UI-10 in one clean-tree drain after M1–M2).
- Head: `76db4896` (ui-10). Deploy after iteration: backup `engram_20260702_172910.sql`.
- Retrospective: harness + product notes captured in chat; LCS/Loopsmith improvements queued.

### Delivery model

- **Loopsmith drain** runs slices from `prd.json` in isolated worktrees.
- **LCS** via `loopsmithctl-lcs.sh` (PREAMBLE + TDD skills).
- **Cursor overseer** monitors status, fixes harness drift, manual smoke at plan deploy gates, **takeover via pause-and-resume only** (see Harness notes).
- **Retrospective** done (2026-07-02).

### Overseer commands

```bash
bash /Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards/scripts/loopsmithctl-lcs.sh \
  status --repo /Volumes/lex1t/dev/shared/repos/engram

bash /Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards/scripts/loopsmithctl-lcs.sh \
  host-run --repo /Volumes/lex1t/dev/shared/repos/engram --task-id ui-01-duplicate-fab

# After M1 canary succeeds:
bash .../loopsmithctl-lcs.sh host-run --repo .../engram --drain
```

### Harness notes (carry forward)

- Strict doctor ~41s; do not block drain on strict probe timeout alone.
- UI tasks: `coding-loop-policy.yaml` sets `executorLaunchTimeoutSeconds: 1800`.
- Tests: `TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test` only.
- Recovery: `bash scripts/loopsmith_recover.sh /Volumes/lex1t/dev/shared/repos/engram inspect`
- **Overseer takeover (policy A):** pause drain — do not implement product code on `main` in parallel with an active attempt on the same `task-id`. Wait for attempt to finish/fail, or `reset-state`; land overseer commit; mark task `passes: true` in `prd.json`; resume drain.
- **Deploy gates:** defined per iteration in the plan (milestone and/or end-of-cycle); not per slice. See `V5_PRODUCTIVITY_IMPLEMENTATION_PLAN.md` § Deploy gates.
- **Loopsmith wrapper:** must resolve `LOOPSMITHCTL` portably (not OpenClaw-specific); any agent uses the same LCS wrapper.

## Previous loop: Activity Update v2 (2026-07-02) — complete

AU0–AU9 shipped. See `docs/iterations/ACTIVITY_UPDATE_V2_SPEC.md`.

## Previous loop: Iteration 17 V5 Hardening (2026-07-01) — complete

All 6 prd tasks passed. See archived `docs/iterations/archive/prd-v5-hardening.json`.

## Active Sources of Truth

| Document | Purpose |
|---|---|
| `AGENTS.md` | Repo-wide working rules |
| `docs/V4_PRINCIPLES.md` | Product and architecture rules |
| `docs/V4_WORLD_MODEL_PLAN.md` | Active implementation plan |
| `prd.json` | Loopsmith task graph (Iteration 18) |
| `EXECUTION-TRACKER.md` | This file |

## Deploy + Validation Baseline

- Backup before deploy: `bash scripts/backup_prod.sh`
- Backend tests serial on port 5433
- Frontend: `cd ui && npm test && npm run build`
- 2026-07-02T22:05:51.027347+00:00 ui-02-update-outcome-panel accepted via opencode
- 2026-07-02T22:33:44.232614+00:00 au10-status-extraction accepted via cursor
- 2026-07-02T22:35:20.042541+00:00 au11-follow-up-routing accepted via cursor
- 2026-07-02T22:41:02.617279+00:00 ui-04-now-full-today accepted via cursor
- 2026-07-02T22:42:26.816202+00:00 ui-05-meeting-prep accepted via cursor
- 2026-07-02T22:43:50.416230+00:00 ui-06-honest-follow-up-actions accepted via cursor
- 2026-07-02T22:50:30.120585+00:00 ui-07-recall-copy accepted via opencode
- 2026-07-02T22:54:08.012460+00:00 ui-08-memory-digest accepted via opencode
- 2026-07-02T23:02:55.342522+00:00 ui-09-decisions-section accepted via opencode
- 2026-07-02T23:05:34.066365+00:00 ui-10-collapse-empty-sections accepted via opencode
- 2026-07-03T16:24:55.538327+00:00 sq-07-precision-task-extraction accepted via opencode
- 2026-07-03T16:51:49.198698+00:00 sq-08-person-hygiene accepted via opencode
