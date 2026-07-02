# Engram — Execution Tracker

Fresh-agent handoff for the current v4 baseline. Use this to get oriented quickly,
then read the active source docs before changing code.

Last updated: 2026-07-02
Branch: `main`
Status: **Iteration 18 in progress** — M1 + M2 done (5/12). **Drain running** UI-04 → UI-10.

Runtime baseline: `/api/v4` only, fresh Postgres + pgvector schema, write-enabled MCP
aligned with the active API.

## Current loop: Iteration 18 — V5 Productivity & Trust (2026-07-02)

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
| M3 Daily surface | UI-04 – UI-07 | drain in progress |
| M4 Polish | UI-08 – UI-10 | drain in progress |

### Delivery model

- **Loopsmith drain** runs slices from `prd.json` in isolated worktrees.
- **LCS** via `loopsmithctl-lcs.sh` (PREAMBLE + TDD skills).
- **Cursor overseer** monitors status, fixes harness drift, manual smoke after M2.
- **Retrospective** planned after M1–M3 drain completes.

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
