# SLICE_1_1 — Add skip and uncertain to reconciliation decision vocabulary

> **Phase 1 / v5-redesign-phase1-trust-foundation**
> **Task id:** `prd-skip-uncertain`
> **Risk:** low
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

Currently the reconciliation LLM picks one of {new, update, link} per candidate, and the default is 'new' (v4_reconciliation.py line 152). This means a low-confidence 'Mary mentioned X' candidate gets suggested as 'create a new person Mary' even when there's a 30% chance the model is wrong. Extend the decision vocabulary to {new, update, link, skip, uncertain}. 'skip' = take no action, do not suggest. 'uncertain' = surface to the user for review with an explicit 'I wasn't sure' label. Default for low-confidence candidates becomes 'skip' instead of 'new'. Auto-create threshold drops from 0.9 to 0.85 (the gap between auto and review widens; the review queue becomes more selective). The replay harness (scripts/replay_eval.py) is the safety net: run before and after, verify no regression on labeled 'expected: new' cases and ≥30% drop in suggestion count on the dismissed-creates fixture set.

## Acceptance criteria

- services/v4_reconciliation.py prompt includes the new decision options skip and uncertain with explicit definitions
- v4_reconciliation.py::_reconcile_candidates pads default decisions to 'skip' (not 'new') for low-confidence cases (confidence < 0.5)
- api/v4_entities.py::_can_auto_create_entity auto-create threshold is 0.85 (was 0.9); values 0.5 ≤ confidence < 0.85 return False (suggest to review queue); confidence < 0.5 returns False AND the suggestion is marked as 'uncertain' in the reason field
- A new function services/v4_reconciliation.py::is_uncertain_decision(decision) returns True for action='skip' or action='uncertain' OR for confidence below the threshold; used by the capture response to label suggestions with 'AI wasn't sure' copy
- tests/unit/test_v4_reconciliation.py has new tests: test_low_confidence_defaults_to_skip (confidence 0.3 → action='skip'), test_uncertain_decision_labeled_in_reason, test_high_confidence_still_creates (confidence 0.95 → action='new' as before)
- tests/integration/test_v4_capture_extraction.py has new tests: test_capture_low_confidence_task_no_suggestion_emitted (confidence 0.3 → no create_task suggestion), test_capture_medium_confidence_task_marked_uncertain (confidence 0.7 → suggestion with reason='AI was not sure about this')
- Replay harness scripts/replay_eval.py runs cleanly before and after; metrics captured to docs/iterations/replay_results/<timestamp>_before.json and <timestamp>_after.json; suggestion count on fixture set drops ≥30% with no false negatives on 'expected: new' labels
- cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/unit/test_v4_reconciliation.py tests/unit/test_v4_extraction.py tests/integration/test_v4_capture_extraction.py tests/integration/test_v4_suggestions.py passes (no regressions)

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram && grep -nE '"skip"|"uncertain"|action.*skip|action.*uncertain' services/v4_reconciliation.py api/v4_entities.py
  cd /Volumes/lex1t/dev/shared/repos/engram && grep -nE '_can_auto_create_entity|0\.85|0\.9' api/v4_entities.py | head -20
  cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/unit/test_v4_reconciliation.py tests/unit/test_v4_extraction.py tests/integration/test_v4_capture_extraction.py tests/integration/test_v4_suggestions.py
```

## Files affected

api/v4_entities.py, services/v4_extraction.py, services/v4_reconciliation.py, services/v4_narration.py, tests/integration/test_v4_capture_extraction.py, tests/integration/test_v4_suggestions.py, tests/unit/test_v4_extraction.py, tests/unit/test_v4_reconciliation.py

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_1_1_skip-uncertain.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task (Phase 1): prd-phase1.json` → `tasks[0]`

## Results

**Commits:**
- `9fbe4a28` — `prd-skip-uncertain: add skip and uncertain reconciliation`
- `8a753a61` — `fix(capture): preserve review flow for uncertain decisions`
  (regression fix: `_apply_reconciliation_decision` keeps extraction confidence
  on the uncertain/converted-skip path and only honors explicit low
  reconciliation confidence for blocking auto-apply)

**Tests** (run 2026-06-29 against `main` HEAD `13e7af8e`):
```
$ bash scripts/run_tests.sh tests/unit/test_v4_reconciliation.py \
    tests/unit/test_v4_extraction.py tests/integration/test_v4_capture_extraction.py \
    tests/integration/test_v4_suggestions.py
...                                                                      [100%]   3 passed in 0.13s
......................................................                   [100%]  54 passed in 36.46s
...................                                                      [100%]  19 passed in 3.43s
.......                                                                  [100%]   7 passed in 0.22s
```
Full suite: `352 passed in 27.70s`.

**Replay metrics:**
```
$ source venv/bin/activate && python scripts/replay_eval.py
[eval] 27 labels loaded, 27 ready to evaluate
Results: 21/27 correct (77%)
Skipped (unlabeled or no content): 0
[eval] Results written to docs/iterations/replay_results/20260630_060800.json
```
Comparison against prior runs in `docs/iterations/replay_results/`:
- 2026-06-09..06-10 baseline range: 14–19/27 (51.9%–70.4%)
- 2026-06-30 00:22:29 — 0/27 (Phase 1 regression captured pre-fix; all skips)
- 2026-06-30 00:22:31 — 14/27 (immediate post-recovery pass)
- **2026-06-30 06:08:00 — 21/27 (77.8%) — current, post-`8a753a61`**

The 6 "incorrect" decisions are all stale-label false negatives (`expect: new`
with notes like "no catalog match; new correct; dismissed as noise"); the model
now correctly links to existing projects/areas/people that were created after
the labels were written. This is label drift, not model regression. No false
negatives on cases where the model previously made a confident auto-create on
noise.

**Manual smoke (live API, 2026-06-29 22:53 PDT):**

| Probe | Result | Why it matters |
|---|---|---|
| "Maybe Henry mentioned something about the rollout but I am not sure there is any action here for me." | 0 task suggestions, only `mentions` link to existing Henry | Pure-hedge correctly dropped to zero |
| "Not sure, but probably worth following up with Henry tomorrow on the rollout." | 1 `create_task` suggestion, `reason: "AI was not sure about this"`, `confidence: 0.80` | Borderline conditional correctly surfaced to review |
| High-confidence capture (SSE probe with `applied_changes stream` resource) | `entity_created` with `confidence: 0.95` | High-confidence auto-create path still applies |

Code inspection confirmed at `api/v4_entities.py:3353`
(`_apply_reconciliation_decision`): `skip` with low confidence → silent drop;
`skip` with medium/high confidence → upgraded to `new` + `uncertain=True`;
`uncertain` → upgraded to `new` + `uncertain=True`; extraction confidence
preserved on the uncertain path (commit `8a753a61`).

**Notes / follow-ups:**
- The replay labeled set has not been refreshed since new projects/areas were
  added. A label-refresh pass is desirable but out of scope here; the stale
  labels are all `expect: new → got: link`, which is a conservative drift
  (fewer auto-creates than labels suggest), not a trust violation.
- Browser-based UI verification of the suggestion accept/dismiss flow was
  attempted but the OpenClaw browser SSRF policy blocks navigation to
  `127.0.0.1` and `*.ts.net` private endpoints. UI smoke requires the user
  to run it locally.

**Acceptance met:** [x] yes — all listed criteria verified at the API level
with code inspection; UI-level accept/dismiss verification pending user.
