# SLICE_AU5 — V5 Activity section

> **Activity Update v2**
> **Task id:** `au5-activity-section`
> **Risk:** low
> **Status:** Done

## Goal

Render recent activity updates as a first-class V5 section from existing detail payload (`sections` key `activity_updates`). Timeline remains provenance; Activity is the human-readable progress log.

## Acceptance criteria

- Project/task/area detail renders Activity section when updates exist in `detail.sections`.
- Update text and timestamp visible without opening timeline.
- Empty state compact or omitted (document choice in test).
- Timeline section unchanged (still narration events).
- Fixtures include `activity_updates` section sample data.
- Backend entity detail tests pass if section payload extended (source link fields optional).

## Validation commands

```
cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test -- V5ThreadDetail
cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_entity_detail.py tests/integration/test_v4_activity_updates.py
```

## Files affected

- `ui/src/views/V5ThreadDetail.jsx`
- `ui/src/views/V5ThreadDetail.fixtures.js`
- `ui/src/views/V5ThreadDetail.test.jsx`
- `ui/src/views/v5ThreadDetailUtils.js`

## Results

**Tests:**
```
15 passed (V5ThreadDetail.test.jsx includes Activity section coverage)
```

**Empty state:** Activity section omitted when `activity_updates` section has no items.

**Acceptance met:** [x] yes
