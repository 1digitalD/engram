# SLICE_AU7 — Cap, pagination, and near-duplicate (deferred)

> **Activity Update v2**
> **Task id:** `au7-cap-dedup`
> **Risk:** medium
> **Status:** Done

## Goal

Replace max-30 hard 409 with pagination or graceful access to older updates. Add near-duplicate warning for recent activity updates. Keep exact-duplicate protection.

## Acceptance criteria

- Users can add updates on long-lived entities without dead-end 409.
- Near-duplicate returns warning or skip based on confidence.
- Exact-duplicate within 24h protection remains.
- `test_v4_activity_updates.py` covers long-lived entity case.

## Validation commands

```
cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_activity_updates.py
cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test -- V5ThreadDetail
```

## Files affected

- `api/v4_entities.py`
- `tests/integration/test_v4_activity_updates.py`
- `ui/src/views/V5ThreadDetail.jsx`
- `mcp_server/server.py`, `mcp_server/v4_formatters.py`

## Results

**Tests:**
```
25 passed (tests/integration/test_v4_activity_updates.py)
```

**Behavior:**
- Removed create-time max-30 block; GET supports `limit`/`offset` with `meta.total`.
- Near-duplicate (token Jaccard ≥ 0.85 within 24h) returns 200 `skipped: true, reason: near_duplicate`.
- UI shows inline error when Add update is skipped.

**Acceptance met:** [x] yes
