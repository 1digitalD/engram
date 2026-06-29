# Phase T2 Archive — v4-noise-reduction-tier2

> **Archived 2026-06-29** when the v5 redesign PRDs replaced the previous
> Tier 2 PRD as the active planning artifact. This file preserves the Tier 2
> work summary for future reference. The original PRD JSON is in git history
> (commit `441c362f`) under `prd.json` (v4-noise-reduction-tier2).

## What was Tier 2?

Tier 2 was the second phase of the v4 noise-reduction work, building on
Tier 1 (2026-06-26: untitled-fallback + gpt-5.4-nano switch). The goal was to
reduce agent noise at the source by changing AI behavior, not just display.

## Tasks (all completed, deployed 2026-06-27)

1. **`tasks-suggest-only-on-capture`** — add `"task"` to
   `SUGGEST_ONLY_CREATION_TYPES` so extracted tasks go to the review queue
   instead of auto-creating. Resolved: live 7-day correction_rate dropped
   from 0.123 → 0.092 (-25%).

2. **`extraction-prompt-sees-active-tasks`** — add top-15 active open tasks
   to the `EXISTING_ENTITIES` block in the extraction prompt so the model
   can suppress duplicates at the source.

3. **`last-mile-exact-title-dedup`** — `_auto_create_entity` calls
   `_find_existing_entity` first to catch exact-title matches the embedding
   similarity misses.

4. **`capture-derived-from-on-link`** — overrides the reconciliation LLM's
   `relationship_type` choice for tasks to always use `derived_from`
   (preserves note→task provenance on link path, not just new path).

5. **`activity-update-zombies-stop`** — sets `ai_status="done"` on
   activity-update notes at creation so they don't accumulate as `pending`
   zombies.

## Live metrics after Tier 2 (from MEMORY.md)

- 7-day `correction_rate`: **0.092** (down from 30-day baseline 0.123, -25%)
- 7-day `acceptance_rate`: **0.25** (stable)
- 184 integration + 127 unit tests pass
- All 5 tasks deployed and stable in production

## Why this matters for the v5 redesign

Tier 2 closed the most pressing noise problems. The v5 redesign (Phases
1-4) builds on top of Tier 2's foundation: the `skip | uncertain` decision
types in Phase 1.1 extend the conservative extraction pattern Tier 2
established. The streaming capture in Phase 1.2 makes the new
gating visible to the user. The decisions extraction in Phase 3.1
inherits the "always to suggestions, never auto-apply" discipline that
Tier 2 used for tasks.

The "Engram drafts, you deliver" principle in the v5 redesign is the
design-level expression of Tier 2's behavioral lesson: the AI's
authority stops at the suggestion queue.

## Lessons carried forward (from MEMORY.md)

- **Loopsmith verifier `no_changes` is unreliable.** When the verifier
  says `blocked: no_changes` but the worktree has a valid commit, the
  fix is cherry-pick + manual merge + mark `passes: true`. Do NOT spawn
  a new attempt. Tier 2 used this pattern for the
  `capture-derived-from-on-link` task.
- **Test postgres retains rows across test files.** Order-dependent
  failures are real. Workaround: rerun the failing file alone, or
  accept that isolation between files is not enforced.
- **Watchdog cron `delivery.mode="announce"`** is required; `"none"`
  suppresses alerts. Phase 1+ will need the same watchdog setup.
- **Recovery script** is the codification of the manual recovery
  steps. Tier 2 used the inline Python (`StateStore.set_active_attempt(None)`)
  pattern; v5 adds `scripts/loopsmith_recover.sh` for repeatability.

## Reference

- **Tier 1 PR**: merged 2026-06-26 (untitled-fallback + nano switch)
- **Tier 2 PRs**: merged 2026-06-27 (5 tasks above)
- **Tier 2 deploy**: `441c362f` (chore(prd): close tier-2 deploy task)
- **Tier 2 PRD (in git)**: `prd.json` v4-noise-reduction-tier2, commit `441c362f`
- **MEMORY.md section**: "Engram noise reduction Tier 2" (live metrics + tasks)
