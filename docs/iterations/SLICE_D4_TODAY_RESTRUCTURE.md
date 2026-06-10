# Slice D4 — Today restructure + day reviewed

Status: DONE.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase D, Slice D4: regroup Today into
**Your actions**, **Delegations needing a nudge** (from C2), **Deadlines
ahead** (due tomorrow / this week, collapsed), plus existing overdue/due-today
on top. Add a "Mark day reviewed" button writing review state, with the FK
question (nullable column vs singleton system entity) resolved additively.
This slice deploys Phase D.

## Changes

### Backend (`api/v4_entities.py`)
- New `_set_app_setting(key, value)` — upsert helper for the existing
  `app_settings` key/value table (no schema migration needed; resolves the
  "FK question" from the plan by avoiding `EntityEvent` entirely — day-review
  state is a singleton app setting, not tied to any entity).
- New query in `GET /api/v4/today`: `upcoming_due_tasks` — active, non-done
  tasks with `due_at` in `(end_of_today, end_of_week]`. Threaded through the
  same `with_priority` (staleness/impact/inherited-priority) pipeline as the
  other buckets and included in `all_tasks` for batched scoring.
- `/today` response gains:
  - `"upcoming_due_tasks"` — new bucket (mirrors `upcoming_follow_ups` but for
    `due_at`).
  - `"last_reviewed_at"` — ISO timestamp from `app_settings["last_reviewed_at"]`,
    or `null` if never reviewed.
  - `"reviewed_today"` — `true` iff `last_reviewed_at >= start_of_today` (UTC).
- New `POST /api/v4/today/review`: sets `app_settings["last_reviewed_at"] =
  now()`, returns `{last_reviewed_at, reviewed_today}`. Calling it again later
  the same day just bumps the timestamp (still `reviewed_today: true`); after
  midnight UTC, `reviewed_today` naturally becomes `false` again until called.

### Frontend
- `ui/src/api/v4Client.js`: `v4API.today` is now a callable function with an
  attached `.review()` method (`Object.assign`), so `v4API.today()` (GET) and
  `v4API.today.review()` (POST `/today/review`) both work.
- `ui/src/utils/today.js`:
  - `getTodayActionItems(today)` — merges `overdue_follow_ups`, `follow_ups`,
    `blocked_tasks`, `waiting_tasks`, and `unscheduled_attention_tasks` into a
    single deduped list of `{entity, reason}`, preserving each item's reason
    pill (`overdue_follow_up` / `follow_up_today` / `blocked` / `waiting` /
    `needs_attention`).
  - `getTodayDeadlinesAhead(today)` — deduped union of `upcoming_follow_ups`
    and `upcoming_due_tasks`.
- `ui/src/views/V4Today.jsx`:
  - Removed the separate "Overdue follow-ups", "Follow up today", "Blocked",
    "Waiting", "Needs attention (no date set)", and "Upcoming follow-ups"
    sections.
  - Added a single **"Your actions"** panel rendering `getTodayActionItems`
    (each row keeps its original reason pill).
  - Added a collapsed **"Deadlines ahead"** `<details>` section rendering
    `getTodayDeadlinesAhead` (due/follow-up items due tomorrow through end of
    week).
  - "Overdue", "Due today", "Focus now", and "Delegations needing a nudge"
    are unchanged.
  - New **"Mark day reviewed"** button in the date header: calls
    `v4API.today.review()` then reloads; shows "Day reviewed" and disables
    itself once `today.reviewed_today` is true.

## Tests (TDD, red → green)

- `tests/integration/test_v4_today.py`:
  - `test_v4_today_includes_upcoming_due_tasks` — a task due in 3 days appears
    in `upcoming_due_tasks` and not in `overdue`/`due_today`; a task due in 3
    weeks does not appear.
  - `test_v4_today_day_reviewed_flow` — `/today` starts with
    `last_reviewed_at: null`, `reviewed_today: false`; `POST /today/review`
    returns a timestamp with `reviewed_today: true`; a subsequent `/today`
    call reflects the same state; backdating the stored `app_settings` row to
    yesterday flips `reviewed_today` back to `false` while
    `last_reviewed_at` remains set (the "resets at midnight" behavior).
- `ui/src/views/V4Today.test.jsx` — extended fixture with `upcoming_due_tasks`,
  `last_reviewed_at: null`, `reviewed_today: false`; asserts "Your actions",
  "Deadlines ahead", and "Mark day reviewed" all render.

Full backend suite green: 223 passed (was 221; +2 new). Frontend: 43 passed,
build green. Live-checked against prod `/today` via the Vite dev server
(proxies to the live API on :5001) — "Your actions", "Deadlines ahead", and
"Mark day reviewed" all present in the rendered page. The review button was
*not* clicked during verification, since doing so would write to the live
prod `app_settings` table.

## Acceptance criteria

- [x] Sections render from one `/today` call (no new endpoints needed for
      rendering; only the new `/today/review` action endpoint).
- [x] Reviewed state persists across reloads (`app_settings.last_reviewed_at`)
      and resets at midnight (`reviewed_today` derived from
      `start_of_today` comparison).
- [x] Suite + UI green.
- [x] Deploys Phase D.
