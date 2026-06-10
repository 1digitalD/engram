# Slice F1 — Stale projects + suggested archival

Status: DONE.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase F, Slice F1: surface active projects
with no recent activity in `/today` and the Home stat. `stale_projects` =
active projects with no activity-update note, non-creation `EntityEvent`, or
field change in 14+ days. `suggested_archival` = the same at 30+ days.
Archival is a suggestion only — nothing is applied automatically.

## Changes

### Backend (`api/v4_entities.py`)
- New constants `STALE_PROJECT_DAYS = 14`, `ARCHIVAL_SUGGESTION_DAYS = 30`.
- New `_project_staleness_days(entities, now)`: maps `entity_id -> days`
  since the most recent of: `created_at`, latest `activity_update`-linked
  note (`_latest_activity_updates`, reused from D3), or latest non-`created`
  `EntityEvent` (`_latest_event_at`, new). The `created` event is excluded
  because `created_at` already covers it — including it would make every
  newly created entity look "active" at staleness 0 forever via its
  creation event alone, but more importantly excluding it lets
  `created_at` (settable, untouched by the `entities_updated_at` DB
  trigger) serve as the staleness floor in tests.
- `_build_today_payload`: queries active projects (`type=project`,
  `lifecycle=active`, `status=active`), computes staleness via
  `_project_staleness_days`, and splits them into `stale_projects` (14-29
  days) and `suggested_archival` (30+ days), each entry annotated via
  `_entity_with_attention` plus a `stale_days` field. Both lists sorted by
  `stale_days` descending.
- `/today` response gains `stale_projects` and `suggested_archival` keys.
- `/summary` gains `stale_projects_count` = `len(stale_projects) +
  len(suggested_archival)`.

Note: `Entity.updated_at` could not be used as a staleness signal — the
`entities_updated_at` Postgres trigger forces it to `now()` on every row
UPDATE, so it can't reflect "time since last meaningful change" the way
`created_at` + activity-update/event timestamps can.

### Frontend
- `ui/src/views/V4Today.jsx`: new `StaleProjectRow` component; new
  collapsible "Stale projects" section (after "Recent notes", before
  "Backlog hygiene") rendering `suggested_archival` items first (tagged
  "consider archiving") then `stale_projects`, each showing `stale_days`.
  Section only renders when either list is non-empty.
- `ui/src/views/V4Home.jsx` + `V4Home.module.css`: hero stats gain a fourth
  card, "stale projects" (`summary.stale_projects_count`), linking to
  `/today`. `.heroStats` grid changed from `repeat(3, ...)` to
  `repeat(4, ...)` (and the `900px` breakpoint to `repeat(2, ...)`).

## Tests (TDD, red → green)

- `tests/integration/test_v4_today.py::test_v4_today_surfaces_stale_and_archival_projects`:
  creates a fresh project, a project backdated (`created_at`) 15 days, one
  backdated 31 days, and a `completed` project backdated 60 days. Asserts
  the 15-day project is in `stale_projects` only, the 31-day project is in
  `suggested_archival` only, the fresh and completed projects are in
  neither, `stale_days` is correct on each, and `/summary`'s
  `stale_projects_count` equals the combined count.
- `ui/src/views/V4Today.test.jsx`: extended the existing render test with
  `stale_projects`/`suggested_archival` fixtures; asserts the "Stale
  projects" section, both project titles, their `stale_days` text, and the
  "consider archiving" tag for the archival item.
- `ui/src/views/V4Home.test.jsx`: extended `summary` mock with
  `stale_projects_count: 2`; asserts the new "2 stale projects" hero card
  links to `/today`.

Full backend suite green: 227 passed (was 227; +1 new, no regressions).
Full UI suite green: 44 passed (unchanged count — both edited specs kept
their existing test count). Build green.

## Acceptance criteria

- [x] `/api/v4/today` returns `stale_projects` (14-29 days inactive) and
      `suggested_archival` (30+ days inactive), each active project entry
      with `stale_days` and `attention`.
- [x] `/api/v4/summary` returns `stale_projects_count`.
- [x] Today UI surfaces both lists in a "Stale projects" section; archival
      items are visually flagged but nothing is archived automatically.
- [x] Home hero stats show the stale-projects count, linking to `/today`.
- [x] Suite + UI green; build green.
- [x] Not deployed — Phase F deploys after F2 (per plan).
