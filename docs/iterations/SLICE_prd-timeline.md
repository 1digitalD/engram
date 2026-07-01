# Slice: prd-timeline — `/api/v4/timeline` + V5Memory view

## Goal
Add a chronological, episodic event stream across all entities via `GET /api/v4/timeline`, backed by `entity_events`, and surface it in the new V5Memory view.

## Acceptance criteria
- `GET /api/v4/timeline?from=&to=&thread_id=&actor=&entity_type=&limit=&offset=` returns `{events: [...], next_offset: ...}` ordered by `occurred_at` DESC.
- Each event includes `id`, `entity_id`, `entity_type`, `event_type`, `occurred_at`, `actor`, `narration`, and derived `thread_id`.
- Migration `scripts/migrations/005_timeline_index.sql` adds `(created_at DESC)` index idempotently; `docs/SCHEMA.sql` updated.
- V5Memory view shows a vertical timeline with date headers, entity-type/actor/thread filters, search, and lazy infinite scroll.
- Mobile: single column, full-width cards, pull-to-refresh, infinite scroll.
- Integration tests in `tests/integration/test_v4_timeline.py` cover ordering, thread/actor filters, pagination, narration, and a 1000-event <500ms performance check.

## Implementation
- Added `/api/v4/timeline` route in `api/v4_entities.py` with batched thread_id derivation and narration.
- Added `v4API.timeline` client method.
- Added `V5Memory.jsx`, `V5Memory.module.css`, and `V5Memory.test.jsx`.
- Wired `/memory` route into `App.jsx` and `TopBar.jsx` lens navigation.

## Validation
```bash
bash scripts/run_tests.sh /Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/prd-timeline-opencode-a003-opencode tests/integration/test_v4_timeline.py tests/integration/test_v4_entity_detail.py
```
Result: 8 passed.

UI tests (`cd ui && npm test`) and build (`cd ui && npm run build`) pass.

## Notes
- Search tests in `test_v4_search.py` fail pre-existing on this environment (pgvector semantic search returns empty) and are unrelated to this slice.
