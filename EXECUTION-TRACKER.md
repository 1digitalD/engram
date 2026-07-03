# Engram — Execution Tracker

Fresh-agent handoff for the current v4 baseline. Use this to get oriented quickly,
then read the active source docs before changing code.

Last updated: 2026-07-03
Branch: `main`
Status: **Iteration 20 in progress (UI-CTX-01)** — Recall search fix + UI context density loop.
Previous: Iteration 19 complete + post-review hardening deployed (2026-07-03).

Runtime baseline: `/api/v4` only, fresh Postgres + pgvector schema, write-enabled MCP
aligned with the active API.

## Active loop: Iteration 20 — UI Context, Density & Color (2026-07-03)

- Plan: `docs/iterations/ITERATION_20_UI_CONTEXT_DENSITY.md`
- Slice docs: `SLICE_UICTX01_recall-search-fix.md` … (see plan)

| Slice | Status | Notes |
|-------|--------|-------|
| UI-CTX-01 Recall fix + color | **done** | P0 parse bug fixed; snippet + type accents |
| UI-CTX-02 Backend task context | pending | detail + search `_attach_task_context` |
| UI-CTX-03 Detail + Recall chips | pending | depends UI-CTX-02 |
| UI-CTX-04 Assignee chips | pending | uses existing `people[]` |
| UI-CTX-05 List metadata | pending | task_counts, linked_counts |
| UI-CTX-06 Shared row chrome | pending | color system rollout |
| UI-CTX-07 Project parent area | blocked | needs backend helper |
| UI-CTX-08 TopBar nav | **deferred** | user: leave TopBar as-is |

## Previous loop: Iteration 19 — Signal Quality & Capture Intelligence (2026-07-02) — complete

- Contract/Plan: `docs/iterations/ITERATION_19_SIGNAL_QUALITY_PLAN.md`
- Loopsmith overlay: archived `docs/iterations/archive/prd-v5-signal-quality.json` (was `prd.json`, iteration `v5-signal-quality-loop`)
- Archived prd: `docs/iterations/archive/prd-v5-productivity.json`

### Milestones

| Milestone | Slices | Status |
|-----------|--------|--------|
| M0 Model reallocation | SQ-00 | done (`.env`, not in git) |
| M1 Broken trust primitives | SQ-01, SQ-02, SQ-03, SQ-04 | done (`8433f2cb`, `5c986f5c`, `dd448bca`, `feaf3b15`) |
| M2 Route by intent | SQ-05, SQ-06 | done (`88d4f53d`, `4c991732`) |
| M3 Precision extraction | SQ-07, SQ-08, SQ-09 | done (`7a98e70e`, `3a3046f3`, `4ef7078c`) |
| M4 Learning loop | SQ-10, SQ-11 | done (`16ef2906`, `741b0607`) |

M0-M2 were delivered directly via `Agent` tool sub-agents in isolated git worktrees
(TDD, fast-forward merge to main), not via Loopsmith — orchestrated inline per explicit
instruction rather than through `prd.json`. M3-M4 used the standard Loopsmith + LCS drain
pattern (run-id `20260703T160154Z-f9737036`), with tasks chained serially (`dependencies`)
since they share `api/v4_entities.py`. Each slice was independently code-reviewed against
its `prd.json` acceptanceCriteria after landing.

### Final validation (2026-07-03, post-drain)

- Backend: `TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test
  ./venv/bin/pytest -q` → 472 passed, 20 skipped, 0 failed.
- UI: `cd ui && npm test` → 147 passed. `npm run build` → succeeds.
- The 3 tests previously flagged as pre-existing failures (`test_v4_search.py` —
  `test_semantic_search_with_mocked_embeddings`, `test_semantic_search_filters_weak_matches`,
  `test_hybrid_search_uses_rrf`) now pass; the underlying pgvector/schema quirk appears to
  have cleared after repeated schema rebuilds during the drain. No longer a known issue.

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
| `prd.json` | Loopsmith idle stub (no active loop; last overlay archived) |
| `docs/iterations/ITERATION_20_UI_CONTEXT_DENSITY.md` | **Active UI iteration plan** |
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
- 2026-07-03T17:18:16.256581+00:00 sq-09-retire-confidence-gating accepted via opencode
- 2026-07-03T17:28:39.004645+00:00 sq-09-retire-confidence-gating accepted via opencode
- 2026-07-03T17:36:58.436365+00:00 sq-09-retire-confidence-gating accepted via opencode
- 2026-07-03T17:45:54.269108+00:00 sq-10-semantic-dismissal-memory accepted via opencode
- 2026-07-03T18:01:44.723132+00:00 sq-11-dismissal-reasons accepted via opencode
- 2026-07-03T18:07:23.327702+00:00 sq-11-dismissal-reasons accepted via opencode

## Post-Iteration 19 review fix (2026-07-03)

- PR [#7](https://github.com/1digitalD/engram/pull/7): Bugbot-driven capture/suggestion hardening (negated status guard, update_unresolved dedup apply, task-cap structural ranking, semantic-memory cap overflow, intent-route decisions, work-carrying persons).
- Deploy: `backup engram_20260703_114953.sql` → `./scripts/engram-deploy.sh` (smoke green).

## Known tech debt (carry forward)

- `api/v4_entities.py` (~7k lines): capture, reconciliation apply, and suggestion paths remain monolithic; split when the next loop touches this area heavily.
- Post-Iteration 19 prod metrics not yet re-run (acceptance rate / agent-deletion SQL in `ITERATION_19_SIGNAL_QUALITY_PLAN.md` § Measurement).
- Replay eval last run 2026-06-30 (`docs/iterations/replay_results/`); re-run after the next extraction change.
- Code-default chat model is `gpt-5.4-nano`; prod `.env` overrides judgment paths to `-mini` (SQ-00). `.env.example` documents the intended prod policy.
