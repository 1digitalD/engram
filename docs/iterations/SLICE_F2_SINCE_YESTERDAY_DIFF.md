# Slice F2 — Since-yesterday diff

Status: DONE.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase F, Slice F2: surface "N new items
since yesterday" — a count of items in today's actionable set that are new
since the last check-in — computed from entity changes in the last 24h (or
since the last day-review, if more recent). This is the final slice of Phase
F; deploying it deploys Phase F.

## Changes

### Backend (`services/v4_attention.py`, `api/v4_entities.py`)
- `services/v4_attention.py`: extracted `today_attention_items(today_payload)`
  — the deduped list of entities across the actionable/stuck/high-signal-note/
  unscheduled-attention buckets (previously inlined in `today_attention_count`,
  which now just returns `len(today_attention_items(...))`).
- `_build_today_payload`: computes `since_cutoff` = `now - 24h`, or
  `last_reviewed_at` if that's more recent than 24h ago (so re-checking
  shortly after marking the day reviewed doesn't re-surface the same items as
  "new"). Counts entities from `today_attention_items(payload)` whose
  `created_at >= since_cutoff`, deduped by id.
- `/today` response gains `new_since_yesterday_count`.
- `/summary` gains `new_since_yesterday_count` (mirrors the `/today` value).

## Frontend
- `ui/src/views/V4Today.jsx`: when `new_since_yesterday_count > 0`, the
  summary strip (alongside "overdue" / "due or follow-up today" / "stuck")
  gains a "{n} new since yesterday" pill.

## Tests (TDD, red → green)

- `tests/integration/test_v4_today.py::test_v4_today_surfaces_new_since_yesterday_count`:
  creates two overdue tasks, backdates one's `created_at` to 3 days ago.
  Asserts `/today` and `/summary` both report `new_since_yesterday_count == 1`
  (only the freshly-created task counts). Marks the day reviewed, re-checks
  `/today` and asserts the count drops to 0 (the existing item is now older
  than the review). Creates a third overdue task after the review and asserts
  the count returns to 1.
- `ui/src/views/V4Today.test.jsx`: extended the existing render test with
  `new_since_yesterday_count: 3`; asserts the "3 new since yesterday" pill
  renders.

Full backend suite green: 228 passed (was 228; +1 new, no regressions).
Full UI suite green: 44 passed (unchanged count). Build green.

## Acceptance criteria

- [x] `/api/v4/today` returns `new_since_yesterday_count`: items in today's
      actionable set created in the last 24h, or since the last day-review if
      more recent.
- [x] `/api/v4/summary` returns `new_since_yesterday_count`.
- [x] Today UI surfaces the count as a pill in the summary strip when > 0.
- [x] Suite + UI green; build green.
- [ ] Phase F deployed (snapshot → `engram-deploy.sh` → smoke test) — pending.
