# Activity Update v2 — Loopsmith Implementation Plan

Date: 2026-07-02 (revised 2026-07-02)
Status: **complete**
Companion spec: `docs/iterations/ACTIVITY_UPDATE_V2_SPEC.md`

## Working rules

Every slice follows Loopsmith coding standards:

- make the smallest coherent change that proves the behavior;
- inspect current code before editing;
- preserve existing contracts unless the slice explicitly changes them;
- keep changes surgical and reversible;
- add or update tests in the same slice as behavior changes;
- run the narrow validator first, then broader relevant suites;
- do not call a slice done until implementation, tests, and verification evidence agree.

Validators run from the main repo path unless a task-specific harness explicitly supports worktree paths.

## Slice index

| Slice | Doc | Risk | Status |
|---|---|---|---|
| AU0 | `SLICE_AU0_characterization.md` | low | **done** |
| AU1 | `SLICE_AU1_embed-and-summary.md` | low | **done** |
| AU2 | `SLICE_AU2_provenance.md` | low | **done** |
| AU3 | `SLICE_AU3_trust-policy.md` | medium | **done** |
| AU4 | `SLICE_AU4_add-update-composer.md` | low | **done** |
| AU5 | `SLICE_AU5_activity-section.md` | low | **done** |
| AU6 | `SLICE_AU6_capture-attachment-cleanup.md` | medium | **done** |
| AU7 | `SLICE_AU7_cap-and-dedup.md` | medium | **done** |

## Recommended milestone

Ship **AU0–AU5** as the first milestone. Defer AU6–AU7 until Add update is validated in daily use.

## End-to-end validation (after AU5)

```bash
cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh \
  tests/integration/test_v4_activity_updates.py \
  tests/integration/test_v4_capture_extraction.py \
  tests/integration/test_v4_suggestions.py \
  tests/integration/test_v4_timeline.py \
  tests/integration/test_v4_entity_detail.py \
  tests/integration/test_v4_today.py

cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test -- V5ThreadDetail V5CaptureSheet
cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run build
```

## Deployment smoke (after AU5)

1. Open an existing project detail page.
2. Add update: `Shipped parser fix; follow up with Mary next Tuesday.`
3. Verify: Activity section, timeline narration, follow-up only when explicit, extracted tasks suggested, update findable via search/Ask after indexing.
4. Open generic capture from Now — still broad capture, not Add update.

## Known concerns to monitor

- Direct update and capture-derived update may double-create notes if both paths fire for the same input.
- Summary refresh is async; UI must not imply instant AI summarization.
- Activity section noise if every small change is shown — keep to user-authored progress and material agent-derived updates.
- Trust-policy changes (AU3) may affect Today/attention surfaces — run Today tests.

## Continuity

Update `EXECUTION-TRACKER.md` when each slice lands. Fill **Results** sections in slice docs with commit SHA, test output, and manual smoke notes.
