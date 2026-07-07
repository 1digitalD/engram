# Slice E2 — Home → stats + workflow shortcuts

Status: DONE.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase E, Slice E2: remove the five
duplicate entity-list panels on Home (Review queue, Today, Stuck, Active
projects, Inbox flow) and keep just the hero stats (now sourced from
`/api/v4/summary`, added in Slice E1) plus three workflow shortcut cards.

## Changes

### Frontend (`ui/src/views/V4Home.jsx`)
- Replaced the three-call `Promise.all([v4API.inbox(...), v4API.today(),
  v4API.entities.list(...)])` fetch with a single `v4API.summary()` call.
- Removed `HomeSection`, `WorkflowLink`, `EntityList`, `entityPath`,
  `entityTitle` and the five panels they rendered (Review queue, Today,
  Stuck, Active projects, Inbox flow).
- Hero stats now show three cards driven by `/summary`:
  - "in review" → `inbox_count` → links to `/suggestions`.
  - "need attention" → `today_count` → links to `/today`.
  - "day reviewed" → `reviewed_today` ("Yes"/"No") → links to `/today`.
- New `ShortcutCard` component renders three workflow shortcuts below the
  hero (replacing the old "Inbox flow" panel's `workflowGrid`):
  - **Capture** → `/inbox`.
  - **Clear review** → `/suggestions`, detail derived from `inbox_count`.
  - **Run today** → `/today`, detail derived from `today_count`.
- `ui/src/views/V4Home.module.css`: removed all panel/list/pill/workflow-link
  styles that are no longer used; added `.shortcutGrid`/`.shortcutCard`
  (3-column grid of large link cards, matching the hero card style);
  `.heroStats` now a 3-column grid.

## Tests (TDD, red → green)

- `ui/src/views/V4Home.test.jsx`: rewritten to mock only `v4API.summary`.
  - "renders hero stats and workflow shortcuts from /summary" — asserts the
    three hero stat links (`/suggestions`, `/today`, `/today`) and their
    values, plus the three shortcut cards and their detail text.
  - "shows day reviewed as Yes when reviewed_today is true" — asserts the
    "day reviewed" stat reflects `reviewed_today`.

Full UI suite green: 44 passed (unchanged count — V4Home.test.jsx went from
1 test to 2). Build green.

## Acceptance criteria

- [x] The five duplicate entity-list panels are removed from Home.
- [x] Hero stats are sourced entirely from `/api/v4/summary` (one call).
- [x] Three workflow shortcut cards (Capture / Clear review / Run today)
      replace the old "Inbox flow" panel.
- [x] Suite + UI green.
- [x] Live verification deferred — `/api/v4/summary` (Slice E1) is not yet
      deployed to prod, so the dev-server proxy 404s to the SPA shell for
      `/api/v4/summary` until Phase E is deployed (after E4).
