# Engram — Execution Tracker

Fresh-agent handoff. Read the active sources of truth below before changing
code. Full v4-era history is archived at `docs/archive/EXECUTION-TRACKER-v4-history.md`.

Last updated: 2026-07-08
Branch: `main`
Status: **v6 Phase 1 active** — Loopsmith drain `v6-phase-1-distillation` pending kickoff.

## Current program: v6 (vision-driven rebuild)

| Document | Purpose |
|---|---|
| `docs/ux-vision/UX_VISION.md` | Product vision + adopted build stance |
| `docs/v6/SOLUTION_DESIGN.md` | Architecture, schema, pipeline, trust policy |
| `docs/v6/IMPLEMENTATION_PLAN.md` | Phases 0–6, slices, deploy gates |
| `docs/v6/TEST_PLAN.md` | Use cases, test cases, edge cases, metrics |
| `docs/v6/QC_LOOP.md` | Implement → review → fix → APPROVE loop |
| `docs/iterations/ITERATION_v6_PHASE_1.md` | Active Loopsmith iteration spec |

Runtime baseline: `/api/v4` only, Postgres + pgvector, write-enabled MCP.

## Phase status

| Phase | Status |
|---|---|
| 0 Foundations | **done** (retro-reviewed 2026-07-08) |
| 1 Distillation report + trust policy | **active** — prd ready |
| 2 Workboard | pending |
| 3 Dossier + direct manipulation + pinning | pending |
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
- _Phase 1 distillation — prd ready, drain pending_
- 2026-07-08T03:40:26.901130+00:00 v6-10-report-assembler accepted via opencode
- 2026-07-08T03:56:13.379365+00:00 v6-10-code-review accepted via opencode
- 2026-07-08T04:16:42.338564+00:00 v6-11-resolve-endpoint accepted via opencode
