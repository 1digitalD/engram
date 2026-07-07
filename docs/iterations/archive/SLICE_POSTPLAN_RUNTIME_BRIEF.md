# Post-plan Slice — Runtime-only Brief + Coordination-aware Snapshot

Date: 2026-06-17
Status: implemented and validated locally

## Goal

Move the Home daily brief closer to the product direction agreed in planning:

- `brief` should behave like a runtime artifact, not durable world state.
- the system should still produce something useful when model generation is
  unavailable, as long as the workspace already contains enough signal.
- model-backed brief generation should see the newer runtime coordination and
  dependency signals, not just raw projects/tasks/updates.

## Changes

- `services/v4_brief.py`
  - removed the `app_settings.daily_brief` persistence path
  - added an in-process TTL cache (`_BRIEF_CACHE`) for the generated brief
  - added `_heuristic_brief(now)` fallback that assembles a ranked brief from:
    - overdue / due-today work
    - dependency interventions
    - quiet delegations
    - blocked work
    - unscheduled attention tasks
    - stale / archival-project signals
    - coordination radar people/projects
  - enriched `_snapshot()` with compact `today` and `coordination_radar`
    sections so model-backed ranking can use the newer runtime surfaces
  - updated the brief prompt to explicitly consider coordination risk

- `tests/integration/test_v4_brief.py`
  - verifies in-process cache behavior
  - verifies no `daily_brief` row is persisted to `app_settings`
  - verifies heuristic fallback returns a useful brief when model generation is
    unavailable but the workspace has real signal
  - verifies `_snapshot()` now includes `today` and `coordination_radar`

- `ui/src/views/V4EntityScreens.test.jsx`
  - hardened an existing flaky note-detail revert test by waiting for the
    `Revert` control before clicking it

## Acceptance

- [x] Brief no longer depends on persisted `app_settings` state
- [x] Brief returns useful runtime output without model generation when the
      workspace has actionable signals
- [x] Model-backed snapshot includes today/dependency/coordination context
- [x] Full backend integration suite passed
- [x] Full frontend suite passed
- [x] Frontend build passed

## Validation

```bash
TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test PYTHONPATH=. ./venv/bin/pytest tests/integration/test_v4_brief.py -q
# 5 passed

TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test PYTHONPATH=. ./venv/bin/pytest tests/integration/ -q
# 173 passed

cd ui && npm test
# 60 passed

cd ui && npm run build
# passed
```

## Notes

- Full frontend tests still emit the pre-existing `act(...)` warnings in
  `App.test.jsx`; this slice did not introduce them.
- Build still emits the existing large-chunk warning from Vite.
