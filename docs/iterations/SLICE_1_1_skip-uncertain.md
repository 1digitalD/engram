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

## Results (filled in by Loopsmith on completion)

<!-- Loopsmith agent: fill in below. Replace each placeholder with actual evidence.
     Required: test output (last 10-20 lines), commit SHA, replay metrics diff (if AI-touching).
-->

**Commit:** `<sha>`

**Tests:**
```
<paste test output>
```

**Replay metrics (if applicable):**
```
<paste replay_eval.py output>
```

**Manual smoke:**
<describe what you tested, what passed, what didn't>

**Notes / follow-ups:**
<any caveats, follow-up slices, or things the next slice should know>

**Acceptance met:** [ ] yes / [ ] no (if no, document what's missing)
