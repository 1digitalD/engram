# Slice B1 — Post-filter loose links to "area" entities (attempted, reverted)

Phase: B — Reconciliation matching, follow-up to Phase A / B0
Status: REVERTED — negative result, kept for record

## Goal

B0's prompt-rule attempt to fix umbrella-area over-matching (A3: 70% →
B0: 66%) was reverted as a negative result. This slice tried a structural
fix instead: a deterministic post-filter on the model's decisions, applied
after `_call_model` returns, rather than relying on the model to follow a
textual instruction.

## What was tried

Added `_downgrade_loose_area_links(candidates, decisions)` to
`services/v4_reconciliation.py`, called at the end of `reconcile_candidates`:
for any `link`/`update` decision whose `target_id` resolves to an entity of
`type == "area"`, downgrade to `"new"` unless the candidate's title shares at
least one "significant" word (≥4 chars, excluding a stoplist of generic
words like "team", "plan", "agent", "roadmap") with the area's title.

Added `tests/unit/test_slice_b1_umbrella_link_filter.py` (5 unit tests on
the filter directly, all passing).

## Live eval result (2026-06-10)

File: `docs/iterations/replay_results/20260610_022909.json`
Score: 17/27 (62%) — **down** from A3's 70% and B0's 66%, against an 85% target.

Two findings:

1. **The filter didn't even fire on the target case.** In this run,
   "Agent Platform" was resolved by the model as a `project`-type entity
   (reason: "Exact match to existing project 'Agent Platform'"), not
   `area`. The filter only checks `Entity.type == "area"`, so it never
   applied. The umbrella-matching errors (SWAT team operating model,
   Platform Evangelism / Adoption, Conversation reinforcement learning,
   Design team grounding in customer scenarios) are unchanged.

2. **Run-to-run variance is large and likely swamps these deltas.**
   Across three live eval runs with only reconciliation-prompt/post-filter
   changes between them:
   - A3 baseline: 19/27 (70%)
   - B0 (prompt rules): 18/27 (66%)
   - B1 (post-filter): 17/27 (62%)

   But the *specific* items that flip are not stable either — e.g. "Update
   team after more time" and "Deals agent family support" were correct in
   A3/B0 and wrong in B1, despite neither change touching those decision
   paths in an obviously relevant way. "Agent Platform"'s entity *type*
   itself differed between runs (area vs. project), which suggests the
   replay fixtures or extraction step have some non-determinism (gpt-4o at
   temperature 0 is not perfectly deterministic, and/or
   `export_replay_fixtures.py`/extraction re-derives slightly different
   candidates per run).

## Conclusion

**Reverted.** `services/v4_reconciliation.py` is back to the A3 state;
`tests/unit/test_slice_b1_umbrella_link_filter.py` removed.

A single replay_eval run is too noisy to judge ±1-2 item deltas (≈ ±4-7
percentage points on this 27-item set). Before attempting another matching
fix:

1. Run `replay_eval.py` 2-3x on the **unchanged** A3 baseline first to
   measure the noise floor.
2. Any future fix needs to target the specific failure pattern more
   robustly — e.g. a filter keyed on whether the *candidate* and *target*
   are a close title match (not gated on the target's `type`, since that
   itself varies run to run for "Agent Platform").
3. Consider whether the umbrella-matching problem is better solved upstream
   in `_build_catalog_block` (e.g. excluding very broad areas from the
   catalog by default, only including them if a stronger embedding match
   exists) rather than as a decision post-filter.
