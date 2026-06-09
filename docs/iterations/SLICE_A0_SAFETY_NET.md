# Slice A0 — Safety Net + Replay Harness

Phase: A — Reconciliation matching
Status: COMPLETE

## Goal

Establish the safety and measurement infrastructure that all subsequent slices depend on:
1. Prod DB backup mechanism
2. Frozen replay fixtures from real production data
3. A scoring harness to measure pipeline quality across slices
4. Updated AGENTS.md + V4_PRINCIPLES.md replacing the now-obsolete "no migration" stance

No behavior changes in this slice.

## Changes

### New files
- `scripts/backup_prod.sh` — pg_dump with non-empty check; exits non-zero on failure
- `scripts/export_replay_fixtures.py` — reads prod (read-only), writes fixtures to `tests/fixtures/replay/`
- `scripts/replay_eval.py` — scores extraction+reconciliation pipeline against labels
- `scripts/migrations/` — directory for future additive schema migration scripts
- `tests/fixtures/replay/` — frozen catalog, suggestions, notes, labels from prod
- `tests/fixtures/replay/labels.json` — 27 hand-labeled suggestion decisions
- `tests/unit/test_slice_a0_safety_net.py` — 14 tests verifying infrastructure
- `docs/iterations/replay_results/` — eval output directory
- `docs/V4_WORLD_MODEL_PLAN.md` (on main) — the active implementation plan

### Updated files
- `.gitignore` — added `backups/`
- `AGENTS.md` — updated active docs table, rules, validation commands, prod-safety warning
- `docs/V4_PRINCIPLES.md` — added Production Data Safety section, retired clean-cutover clause

## Fixture data summary

- 27 suggestions labeled (dismissed: 23, accepted: 4)
- 9 labeled "should have been link" — the false-create set for Slices A2–A3
  - 'Agent Platform' → area 'Agent Platform'
  - 'Toolkit robustness and flexibility' → project same name
  - 'Security roadmap' → project 'Agent Security'
  - 'Deals agent family support' → project 'GTM agent family support'
  - 'Admin agent family support' → project 'GTM agent family support'
  - 'Agent memory utilization' → project 'Agent Memory / Canonical Memory'
  - 'Agentic SDLC' → project same name
  - 'Conversation history search functionality' → project 'Agent Memory / Conversation History'
  - 'Agent memories collaboration' → project 'Agent Memory / Canonical Memory'
- 14 labeled "new" (genuinely new entities, create was correct)
- 4 labeled "accept" (accepted link_existing suggestions)

## Baseline eval results

File: `docs/iterations/replay_results/20260609_220603.json`
Score: 14/27 (51%) — offline run without OPENAI_API_KEY; all wrong answers are
`no_candidates` (extraction never ran). This is the expected offline baseline.

Live baseline (with OPENAI_API_KEY): to be recorded when running replay_eval.py
with model access. Target after A3: ≥ 85% (reduce false-creates to ≤ 2).

## Pre-existing test failures

3 search tests (`test_v4_search.py`) fail when `OPENAI_API_KEY` is absent:
`embed_query()` returns `None` behind the API key guard before the `_embed_texts`
mock is checked. These fail identically on the main branch in the same environment.
Not caused by this slice. Fix is `OPENAI_API_KEY=fake` in the test fixture (deferred).

## Acceptance criteria — all met

- [x] Backup script produces a non-empty dump (manual verify: dump was ~200KB)
- [x] Export script reads prod read-only and writes all fixture files
- [x] 27 labels written and validated by schema test
- [x] Replay eval runs to completion and writes results JSON
- [x] AGENTS.md and V4_PRINCIPLES.md updated
- [x] 14 new A0 tests pass; no regressions in 149-passing suite
- [x] Frontend build passes (no changes)
