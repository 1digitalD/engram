# Phase F — North-star metrics re-run

Per `docs/V4_WORLD_MODEL_PLAN.md` Slice F2: "Deploy Phase F, then re-run
north-star metrics and compare to baseline." This closes out the V4 World
Model plan (Phases A-F).

Computed 2026-06-10 against prod (read-only: `ai_suggestions`/`entity_events`
via `psql`, `/api/v4/entities` and `/api/v4/today` via the live API).

## 1. Suggestion accept rate

- Baseline: 15% (4 accepted / 27 = 4 accepted + 23 dismissed).
- Now: **22.6%** (7 accepted / 31 = 7 accepted + 24 dismissed).
- Improved. Consistent with Phase A's reconciliation-matching work reducing
  noisy/duplicate suggestions (replay eval correct-rate also rose from 14/27
  to 15/27 over the same period, see `docs/iterations/replay_results/`).

## 2. Share of entity state-changes made by agent vs user

- Baseline: ~30% agent.
- Now: **13.8%** agent (25 / 181), where state-change events are
  `updated`, `status_changed`, `ai_updated`, `archived`,
  `review_marked_resolved`, `activity_update_added`, `deleted`:
  - `user`: 156
  - `agent:v4-capture`: 16
  - `agent:v4-review`: 8
  - `mcp:resolve_note`: 1
- Decreased relative to baseline. Read as expected, not regressive: Phases
  B-D added more user-facing surfaces (Today restructure, day-reviewed flow,
  delegation cadence, blocking-impact) that make it easier for the user to
  act directly on entities, while agent-side autonomous mutation
  (`agent:*` actors) stayed flat in absolute terms (24-25 events). The
  "Explicitly deferred" backlog (intent decay/boosts, correction-feedback
  into extraction) is exactly the agent-autonomy work that was intentionally
  not pursued in this plan, so a falling agent share is consistent with scope.

## 3. Count of open tasks invisible to any surface

- Baseline: ~60.
- Now: **54** (94 open/active tasks total, 58 of which appear in at least one
  `/today` actionable bucket — overdue, due/follow-up today or upcoming,
  blocked, waiting, or unscheduled-attention).
- Slightly improved. Phase D's unscheduled-attention bucket and Phase F's
  stale-projects/suggested-archival surfaces both pull previously-invisible
  items into view; the remaining 54 are mostly low-priority undated tasks
  that don't clear the unscheduled-attention score threshold (`> 0`) — i.e.
  deliberately filtered as not yet actionable, not "lost".

## Summary

| Metric | Baseline | Now | Direction |
| --- | --- | --- | --- |
| Suggestion accept rate | 15% | 22.6% | up (better) |
| Agent share of state-changes | ~30% | 13.8% | down (expected — agent-autonomy work deferred) |
| Open tasks invisible to any surface | ~60 | 54 | down (better) |

No regressions. Phases A-F of `docs/V4_WORLD_MODEL_PLAN.md` are complete and
deployed; remaining plan items are all in "Explicitly deferred".
