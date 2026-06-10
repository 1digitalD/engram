# Slice B0 — Umbrella Area Matching (attempted, reverted)

Phase: B — Reconciliation matching, follow-up to Phase A
Status: REVERTED — negative result, kept for record

## Goal

A3's live eval (70%, see `SLICE_A3_CATALOG_IN_PROMPT.md`) showed the
workspace catalog made the model over-eager to link unrelated candidates to
the broad umbrella area "Agent Platform" just because the source note
discussed that area. Goal: tighten `SYSTEM_PROMPT` matching rules in
`services/v4_reconciliation.py` to stop this over-linking without
re-introducing the false-creates A1–A3 fixed.

## What was tried

Added three rules to `MATCHING RULES` in `SYSTEM_PROMPT`:
1. Project vs. area type label is not a hard blocker for catalog matches.
2. Do not link a candidate to a broad/umbrella catalog entry just because
   the source note discusses that umbrella topic — a sub-initiative
   mentioned alongside an umbrella is a different entity.
3. Only link/update to a "person" entity if the candidate itself is a person.

Added `tests/unit/test_slice_b0_umbrella_matching_rules.py` asserting the
new rule text appears in `SYSTEM_PROMPT` (3 tests, passed).

## Live eval result (2026-06-10)

File: `docs/iterations/replay_results/20260610_001048.json`
Score: 18/27 (66%) — **down** from A3's 70%, against a target of 85%.

- 3 of the 4 "linked to umbrella area Agent Platform" errors from A3 were
  **unchanged**, with near-identical reasoning ("exact match to existing
  umbrella area 'Agent Platform'") despite the explicit rule against this.
- A new regression appeared: "Decide next focus" was incorrectly linked to
  person "Akash" (`link ≠ new`), which wasn't wrong in A3.
- "Security roadmap" is still wrong, with a different (still incorrect)
  reason ("too generic").
- "Platform Evangelism / Adoption" is still wrong, now for a different
  reason (matched to person "Danish").

## Conclusion

Prompt-level "do NOT do X" instructions are not reliably followed by the
model for this failure mode — the catalog's mere presence of "Agent
Platform" as a high-salience entry appears to dominate over textual
exclusion rules, and adding more rules to an already-long system prompt
introduced at least one new, unrelated regression (likely from rule
interaction / prompt-length effects).

**The prompt change was reverted.** `services/v4_reconciliation.py` and
`SYSTEM_PROMPT` are back to the A3 state (70% baseline,
`docs/iterations/replay_results/20260609_235658.json`).

## Recommended follow-up (Phase B, next attempt)

A structural fix is more likely to work than further prompt tuning:
- Mark broad/umbrella catalog entries explicitly (e.g. by a heuristic like
  "area with N+ linked projects/tasks") and either exclude them from the
  catalog block by default, or require a higher embedding-similarity
  threshold before they're offered to the model as candidates at all.
- Alternatively, do umbrella-area matching as a separate, narrower
  post-filter step after the model's decision: if `action == "link"` and the
  target is a known umbrella area, require a title/embedding similarity
  above a stricter threshold (e.g. 0.85) or downgrade to "new".

Re-run `scripts/replay_eval.py` against the labeled set after any structural
change and compare to the 70% A3 baseline before merging.
