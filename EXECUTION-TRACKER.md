# Engram — Execution Tracker

Fresh-agent handoff. Read the active sources of truth below before changing
code. Full v4-era history (iterations 0–21, deploy log, harness notes) is
archived at `docs/archive/EXECUTION-TRACKER-v4-history.md`.

Last updated: 2026-07-07
Branch: `claude/engram-ux-vision-aad07p`
Status: **v6 planning complete** — awaiting Phase 0 kickoff.

## Current program: v6 (vision-driven rebuild)

| Document | Purpose |
|---|---|
| `docs/ux-vision/UX_VISION.md` | Product vision + adopted build stance (§10) |
| `docs/v6/SOLUTION_DESIGN.md` | Architecture, schema, pipeline, trust policy |
| `docs/v6/IMPLEMENTATION_PLAN.md` | Phases 0–6, slices, deploy gates |
| `docs/v6/TEST_PLAN.md` | Use cases, test cases, edge cases, metrics |

Runtime baseline (unchanged): `/api/v4` only, Postgres + pgvector with real
production data (additive-only migrations — see `docs/V4_PRINCIPLES.md`),
write-enabled MCP at `mcp_server/server.py`.

## Phase status

| Phase | Status |
|---|---|
| 0 Foundations (archive ✓, API split, operator setting) | V6-00 done; V6-01/02 pending |
| 1 Distillation report + trust policy | pending (measured gate — see plan) |
| 2 Workboard | pending |
| 3 Dossier + direct manipulation + pinning | pending |
| 4 Today + markers + nudges | pending |
| 5 Themes + insights | pending |
| 6 Cutover + legacy UI deletion | pending |

## What a fresh agent must know

- Never `flask init-db` against prod (port 5432). Tests only on :5433.
  `bash scripts/backup_prod.sh` before any schema change or deploy.
- `api/v4_entities.py` is a 7.6k-line monolith until V6-01 splits it; after
  V6-01, new routes go in the owning `api/v4/` module.
- The legacy UI strata (`ui/src/views/`, `ui/src/lab/`) are scheduled for
  deletion in Phase 6 — do not extend them; new UI work goes in
  `ui/src/next/`.
- `prd.json` at repo root is the Loopsmith overlay slot for the active
  iteration; superseded PRDs live in `docs/iterations/archive/`.
- Replay eval: `scripts/replay_eval.py`, results in
  `docs/iterations/replay_results/` (path intentionally unchanged).
- Known debt: post-Iteration-19 prod metrics never re-run; `engram.log` at
  repo root is ignored but ~550MB — rotate/truncate locally when convenient.

## Validation baseline

```bash
TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest -q   # serial
cd ui && npm test && npm run build
```

## Slice log (v6)

- 2026-07-07 V6-00 archive & docs — done (this change series).
