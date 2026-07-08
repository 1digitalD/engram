# Engram — Execution Tracker

Fresh-agent handoff. Read the active sources of truth below before changing
code. Full v4-era history is archived at `docs/archive/EXECUTION-TRACKER-v4-history.md`.

Last updated: 2026-07-08
Branch: `main`
Status: **v6 Phase 3 drain active** — Dossier + pinning + manipulation.

## Current program: v6 (vision-driven rebuild)

| Document | Purpose |
|---|---|
| `docs/ux-vision/UX_VISION.md` | Product vision + adopted build stance |
| `docs/v6/SOLUTION_DESIGN.md` | Architecture, schema, pipeline, trust policy |
| `docs/v6/IMPLEMENTATION_PLAN.md` | Phases 0–6, slices, deploy gates |
| `docs/v6/TEST_PLAN.md` | Use cases, test cases, edge cases, metrics |
| `docs/v6/QC_LOOP.md` | Implement → review → fix → APPROVE loop |
| `docs/iterations/ITERATION_v6_PHASE_2.md` | Phase 2 iteration (archived) |
| `docs/iterations/ITERATION_v6_PHASE_3.md` | Phase 3 iteration (active) |

Runtime baseline: `/api/v4` only, Postgres + pgvector, write-enabled MCP.

## Phase status

| Phase | Status |
|---|---|
| 0 Foundations | **done** (retro-reviewed 2026-07-08) |
| 1 Distillation report + trust policy | **done** (2026-07-08) |
| 2 Workboard | **done** (2026-07-08) |
| 3 Dossier + direct manipulation + pinning | **in progress** (drain started 2026-07-08) |
| 4 Today + markers + nudges | pending |
| 5 Themes + insights | pending |
| 6 Cutover + legacy UI deletion | pending |

## Phase 0 retro review (2026-07-08)

Overseer re-ran 5-pass review; formal verdicts:
- `docs/v6/reviews/v6-01-api-package-split.md` — APPROVE (+ dead import cleanup)
- `docs/v6/reviews/v6-02-operator-identity.md` — APPROVE

Phase 0 Loopsmith review tasks had passed on validation output only; Phase 1+
enforces `v6_check_review_verdict.sh`.

## Validation baseline

```bash
TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest -q   # serial
cd ui && npm test && npm run build
bash scripts/iteration_preflight.sh
bash scripts/v6_check_review_verdict.sh <implement-task-id>   # review tasks
```

## Slice log (v6)

- 2026-07-07 V6-00 archive & docs — done
- 2026-07-08 Phase 0 Loopsmith drain — done (API split, operator setting)
- 2026-07-08 Phase 0 retro review — done (verdict files, QC loop tightened)
- 2026-07-08 Phase 1 Loopsmith drain — done (distillation, Review UI, metrics)
- 2026-07-08T06:48:45.485346+00:00 v6-phase-1-gate accepted via codex
- _Phase 2 workboard — prd ready, drain starting_
- 2026-07-08T09:08:38.887966+00:00 v6-20-code-review accepted via codex
- 2026-07-08T15:35:10.583653+00:00 v6-21-code-review accepted via codex
- 2026-07-08T15:44:26.587607+00:00 v6-22-stream-surface accepted via codex
- 2026-07-08T15:48:22.353456+00:00 v6-22-code-review accepted via codex
- 2026-07-08 Phase 2 gate — done (overseer)
- _Phase 3 dossier — prd ready, drain starting_
- 2026-07-08T18:32:37.724981+00:00 v6-31-code-review accepted via claude
- 2026-07-08T18:37:05.753325+00:00 v6-32-amend-archive-redact-delete accepted via cursor
- 2026-07-08T18:45:49.635358+00:00 v6-32-code-review accepted via cursor
