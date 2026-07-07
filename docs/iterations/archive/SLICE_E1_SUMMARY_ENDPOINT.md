# Slice E1 — `/api/v4/summary` + sidebar counts

Status: DONE.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase E, Slice E1: a single endpoint
returning the sidebar/Home counts (including `last_reviewed_at` /
`reviewed_today`), replacing `useSidebarCounts`'s 3 separate calls
(`/inbox`, `/today`, `/suggestions`). Server-side count logic is the single
source of truth — the "today" dedupe logic from `ui/src/utils/today.js`
(`getTodayAttentionCount`) is ported to Python with a parity test.

## Changes

### Backend (`api/v4_entities.py`, `services/v4_attention.py`)
- `services/v4_attention.py`: new `today_attention_count(today_payload)` —
  pure function that dedupes by entity id across the actionable, stuck,
  high-signal-note (`HIGH_SIGNAL_NOTE_INTENTS = {"blocker", "follow_up",
  "delegation"}`), and unscheduled-attention buckets of a `/today` payload.
  Direct port of `getTodayAttentionCount` (`ui/src/utils/today.js`).
- `today()` refactored: extracted `_build_today_payload(now)` returning the
  plain dict (same contract as before), with `today()` just
  `jsonify(_build_today_payload(...))`.
- `/inbox` refactored: extracted `_needs_review_query()` /
  `_needs_review_count()` (the "notes needing review" filter), reused by
  both `/inbox` and the new `/summary`.
- New `GET /api/v4/summary`:
  ```json
  {
    "inbox_count": <int>,
    "today_count": <int>,
    "suggestions_count": <int>,
    "last_reviewed_at": <iso8601 | null>,
    "reviewed_today": <bool>
  }
  ```
  `inbox_count` and `suggestions_count` both come from
  `_needs_review_count()` (same underlying query); `today_count` is
  `today_attention_count(_build_today_payload(now))`; `last_reviewed_at` /
  `reviewed_today` are passed through from the today payload.

### Frontend
- `ui/src/api/v4Client.js`: new `v4API.summary = () =>
  v4Request('GET', '/summary')`.
- `ui/src/App.jsx`: `useSidebarCounts` now makes a single `v4API.summary()`
  call instead of 3 (`v4API.inbox`, `v4API.today`, `v4API.suggestions.list`
  via `Promise.allSettled`). Removed the now-unused `getTodayAttentionCount`
  import (still used by `V4Today.jsx` directly).

## Tests (TDD, red → green)

- `tests/unit/test_v4_attention.py`:
  - `test_today_attention_count_dedupes_across_buckets` — an item shared
    across `overdue`, `overdue_follow_ups`, and
    `unscheduled_attention_tasks` counts once; a "fyi"-intent recent note is
    excluded, a "blocker"-intent one counts.
  - `test_today_attention_count_handles_missing_buckets` — `{}` → `0`.
- `tests/integration/test_v4_today.py`:
  - `test_v4_summary_matches_today_and_inbox_counts` — `/summary`'s
    `today_count` equals `today_attention_count(/today response)`,
    `inbox_count`/`suggestions_count` equal `len(/inbox needs_review)`, and
    `last_reviewed_at`/`reviewed_today` match `/today`.
- `ui/src/App.test.jsx`: mock `v4API.summary`; new test "renders sidebar
  counts from the summary endpoint" asserts Today/Inbox/Review badge counts
  come from a single `v4API.summary()` response.

Full backend suite green: 226 passed (was 223; +3 new). Frontend: 43 passed,
build green.

## Acceptance criteria

- [x] Single `/api/v4/summary` endpoint returns sidebar counts +
      `last_reviewed_at`/`reviewed_today`.
- [x] Server-side `today_count` logic matches the client's
      `getTodayAttentionCount` exactly (parity unit + integration tests).
- [x] `useSidebarCounts` makes one call instead of three.
- [x] Suite + UI green.
- [x] Not yet deployed — Phase E deploys after E4.
