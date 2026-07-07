# Engram — Execution Tracker

Fresh-agent handoff. Read the active sources of truth below before changing
code. Full v4-era history (iterations 0–21, deploy log, harness notes) is
archived at `docs/archive/EXECUTION-TRACKER-v4-history.md`.

Last updated: 2026-07-07
Branch: `main`
Status: **v6 Phase 0 active** — Loopsmith drain `v6-phase-0-foundations`.

## Current program: v6 (vision-driven rebuild)

| Document | Purpose |
|---|---|
| `docs/ux-vision/UX_VISION.md` | Product vision + adopted build stance (§10) |
| `docs/v6/SOLUTION_DESIGN.md` | Architecture, schema, pipeline, trust policy |
| `docs/v6/IMPLEMENTATION_PLAN.md` | Phases 0–6, slices, deploy gates |
| `docs/v6/TEST_PLAN.md` | Use cases, test cases, edge cases, metrics |
| `docs/v6/QC_LOOP.md` | Implement → review → green loop (every slice) |
| `docs/iterations/ITERATION_v6_PHASE_0.md` | Active Loopsmith iteration spec |

Runtime baseline (unchanged): `/api/v4` only, Postgres + pgvector with real
production data (additive-only migrations — see `docs/V4_PRINCIPLES.md`),
write-enabled MCP at `mcp_server/server.py`.

## Phase status

| Phase | Status |
|---|---|
| 0 Foundations (API split, operator setting) | **active** — Loopsmith drain |
| 1 Distillation report + trust policy | pending |
| 2 Workboard | pending |
| 3 Dossier + direct manipulation + pinning | pending |
| 4 Today + markers + nudges | pending |
| 5 Themes + insights | pending |
| 6 Cutover + legacy UI deletion | pending |

**Delivery stance:** continuous build across phases. Phase 1 quality metrics
(review time, acceptance rate) are tracked in parallel via V6-14 — not a
calendar-blocking gate.

## What a fresh agent must know

- Never `flask init-db` against prod (port 5432). Tests only on :5433.
  `bash scripts/backup_prod.sh` before any schema change or deploy.
- After V6-01: new routes go in the owning `api/v4/` module — the monolith
  must not regrow.
- New UI work goes in `ui/src/next/` (starts Phase 1). Do not extend
  `ui/src/views/`, `ui/src/lab/`.
- `prd.json` is the Loopsmith overlay for the active phase iteration.
- **QC loop:** every implement task is followed by a `kind: review` task —
  see `docs/v6/QC_LOOP.md`.
- Preflight: `bash scripts/iteration_preflight.sh`
- Validation: `bash scripts/v6_validate_slice.sh` (per slice);
  `CHECK_ROUTES=1` when touching routes.
- Replay eval: `scripts/replay_eval.py`

## Validation baseline

```bash
TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest -q   # serial
cd ui && npm test && npm run build
bash scripts/iteration_preflight.sh    # before drain
bash scripts/loopsmith_poll_status.sh  # while drain runs
```

## Slice log (v6)

- 2026-07-07 V6-00 archive & docs — done
- 2026-07-07 Phase 0 kickoff — prd `v6-phase-0-foundations`, QC loop, route baseline
- 2026-07-07 V6-01 API package split — done
- 2026-07-07 V6-02 Operator identity — pending
- 2026-07-07T23:24:04.880417+00:00 v6-01-api-package-split accepted via opencode
- 2026-07-07T23:29:53.575719+00:00 v6-01-code-review accepted via opencode
- 2026-07-07T23:37:54.779401+00:00 v6-01-code-review re-verified via opencode
- 2026-07-07T23:40:35.144825+00:00 v6-01-code-review accepted via opencode
