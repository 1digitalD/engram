# Tasks Page Design

**Date:** 2026-07-10  
**Status:** Approved (pending user review)  
**Route:** `/tasks` (replaces legacy `V5EntityList` for tasks)

---

## 1. Problem

The operator needs a dedicated task-manager view: all commitments grouped by **project**, with explicit filters (status, assignee, due date, follow-up date), sort by create or follow-up date, and inline editing (status, assignee, dates, mark done, log update).

The legacy `/tasks` browse route uses V5 list UI with no grouping, no server-side sort/filter, and links to `V5ThreadDetail`. Workboard (`/workboard`) groups by project internally but optimizes for portfolio triage (derived states: mine, overdue, stale, at-risk) — not free-form task management. Neither surface matches this workflow.

## 2. Goals

- Group open commitments by **project** (`entities.type = 'project'`).
- Default to open statuses; always-visible status filter chips.
- Filter by assignee, due date, and follow-up date independently.
- Sort by `created_at` or `follow_up_at`.
- Inline edit: status, assignee, due date, follow-up date, mark done (checkbox or button), log update (expandable field).
- Reuse proven mutation paths; verify with backend + UI tests — no assumptions about Workboard reuse.

## 3. Non-goals (v1)

- Nudge draft affordance (Workboard-only for waiting-on).
- keep/drop/delegate actions (WRK-06).
- Pin/unpin on task rows (Dossier Space header only today).
- Person-based grouping pivot (Workboard owns that).
- Replacing `/tasks/:id` detail route (rows link to `/commitments/:id`).

## 4. Decisions (locked)

| Topic | Decision |
|-------|----------|
| Page type | Fresh v6 surface at `/tasks`; replaces `V5EntityList` on that route |
| Data layer | New `GET /api/v4/task-board` endpoint + `services/v4_task_board.py` |
| Grouping | By **project** parent link; area-only parent → group under area name; no parent → **"No project"** bucket |
| Archived projects | Excluded (same as Workboard) |
| Default statuses | `open`, `in_progress`, `waiting`, `blocked` |
| Status UI | Multi-select chips always visible; includes `done`, `cancelled` |
| Date filters | Separate controls for **due** and **follow-up** (not create date) |
| Sort | `created_at` (default) or `follow_up_at`; direction `asc` / `desc` |
| Detail navigation | Row title → `/commitments/:id` |
| Group header | Links to `/spaces/:id` (works for project and area) |

## 5. Architecture

### 5.1 Backend — `GET /api/v4/task-board`

New route in `api/v4/task_board.py`, service in `services/v4_task_board.py`.

**Query parameters**

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `status` | repeatable or comma-separated | `open,in_progress,waiting,blocked` | Valid task statuses only |
| `assignee` | string | (none = all) | Person entity ID, or `unassigned` |
| `due_before` | ISO date | — | Inclusive end of range |
| `due_after` | ISO date | — | Inclusive start of range |
| `follow_up_before` | ISO date | — | |
| `follow_up_after` | ISO date | — | |
| `sort` | `created_at` \| `follow_up_at` | `created_at` | |
| `order` | `asc` \| `desc` | `desc` for `created_at`, `asc` for `follow_up_at` | Null dates sort last |

**Grouping logic**

1. Load tasks matching filters (`lifecycle = active`, not deleted/redacted).
2. Resolve parent: prefer `parent` link to `project`; if none, use `parent` link to `area`.
3. Exclude tasks whose resolved parent has `lifecycle != active` (archived).
4. Bucket key: parent entity ID, or `__no_project__` for orphans.
5. Sort tasks within each group per `sort` / `order`.
6. Sort groups alphabetically by label; **"No project"** always last.

**Response shape**

```json
{
  "data": {
    "groups": [
      {
        "key": "project-apollo",
        "label": "Apollo",
        "kind": "project",
        "entity_id": "…",
        "counts": { "total": 4 },
        "items": [
          {
            "id": "…",
            "title": "…",
            "status": "open",
            "due_at": "…",
            "follow_up_at": "…",
            "created_at": "…",
            "owner": { "id": "…", "title": "…" },
            "space": { "id": "…", "title": "…", "type": "project" }
          }
        ]
      }
    ]
  },
  "meta": {
    "total": 12,
    "counts": { "by_status": { "open": 5, "in_progress": 3, … } },
    "filters": { "status": […], "assignee": null, … },
    "sort": "created_at",
    "order": "desc"
  }
}
```

`space` on each item mirrors Workboard payload for `CommitmentItemRow` / `WorkboardItemAffordances` compatibility.

### 5.2 Mutations (existing API — verified)

| Action | Endpoint | Notes |
|--------|----------|-------|
| Mark done | `PATCH /entities/:id` `{ status: "done" }` | Pins status per COM-06 |
| Change status | `PATCH /entities/:id` `{ status }` | |
| Due / follow-up | `PATCH /entities/:id` `{ due_at, follow_up_at }` | ISO datetime |
| Assignee | `POST /entities/:id/links` `assigned_to`, `replace_existing: true` | |
| Move project | `POST /entities/:id/links` `parent`, `replace_existing: true` | |
| Log update | `POST /entities/:id/activity_updates` `{ content }` | Creates linked note |

All mutations use `createActionQueue()` + silent reload pattern from `WorkboardSurface`.

### 5.3 Frontend — `TasksSurface`

**Files**

- `ui/src/next/TasksSurface.jsx` + `TasksSurface.module.css`
- `ui/src/next/tasksBoardUtils.js` — param builders, date presets
- `ui/src/next/TasksSurface.test.jsx`
- Update `NextApp.jsx`: `/tasks` → `TasksSurface` (remove tasks from `BROWSE_ROUTES` or override)
- Update `ui/src/api/v4Client.js`: `taskBoard(params)`

**Reused components (with tests)**

- `CommitmentItemRow` — checkbox/done, title, affordance shell
- `WorkboardItemAffordances` — status, owner, dates, move, log update
- `createActionQueue`, `friendlyApiError`, `statusTheme`

**New UI behavior**

- **Checkbox** on row: toggles done; unchecking from done filter sets status back to `open`.
- **Expandable update field**: single-line input default; expands to textarea on focus; Enter submits, Shift+Enter newline. Extract to `ExpandableUpdateField` in `TypedAffordances.jsx` if needed for test isolation.
- **Created age**: show relative age per row (`formatRelativeAge` from existing util or new small helper).
- **Filter bar**: status chips, assignee `<select>`, due preset `<select>` (+ optional custom range), follow-up preset `<select>`, sort field + direction.

**Date filter presets (client → query params)**

| Preset | Due param | Follow-up param |
|--------|-----------|-----------------|
| Any | — | — |
| Overdue | `due_before=today` | — |
| This week | `due_after=today`, `due_before=end_of_week` | same pattern |
| Next 30 days | `due_after=today`, `due_before=+30d` | same pattern |
| No date | filter tasks where field is null (client-side or `due_none=1` param) |

If "no date" complicates v1, ship preset filters only and add custom range in v1.1.

## 6. Navigation

- Browse rail: **Tasks** → `/tasks` (unchanged label).
- Workboard unchanged.
- `/tasks/:id` can remain `V5ThreadDetail` for direct URLs or redirect to `/commitments/:id` (prefer redirect in v1 for consistency).

## 7. Verification plan

### Backend unit — `tests/unit/test_v4_task_board.py`

- Default status filter returns only open-family tasks.
- Status chip changes alter result set.
- Assignee filter (person ID, unassigned).
- Due / follow-up date range filters.
- Sort `created_at` asc/desc, `follow_up_at` asc/desc; nulls last.
- Grouping by project; area fallback; no-project bucket.
- Archived project exclusion.

### Backend integration — `tests/integration/test_v4_task_board.py`

- Full HTTP round-trip: create project + tasks + links, call `GET /api/v4/task-board`, assert groups and counts.
- Filter + sort query param combinations.

### UI — `TasksSurface.test.jsx`

- Renders groups from mocked `v4API.taskBoard`.
- Status chip toggles refetch with updated params.
- Sort control changes params.
- Mark done calls `entities.update`.
- Log update calls `activityUpdates.create`.
- Expandable update field expands on focus and submits on Enter.

### Affordances — extend `TypedAffordances.test.jsx`

- Expandable update field behavior if extracted.

### Manual smoke

1. Open `/tasks` — default open tasks, grouped by project.
2. Toggle `done` chip — closed tasks appear.
3. Filter by assignee — list narrows.
4. Sort by follow-up ascending.
5. Mark done via checkbox; log update via expanded field.
6. Task with area-only parent appears under area name.

## 8. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Reused affordances behave differently on Tasks vs Workboard | Same handler signatures; shared tests; smoke both surfaces |
| 200+ tasks | Task-board loads all matching tasks (no 200 cap on dedicated endpoint); paginate later if needed |
| Area-only tasks rare but untested | Explicit test case in unit + integration |
| Legacy `/tasks/:id` bookmarks | Redirect to `/commitments/:id` for `type=task` |

## 9. Implementation order

1. `services/v4_task_board.py` + unit tests
2. `api/v4/task_board.py` + integration tests
3. `v4Client.taskBoard` + `tasksBoardUtils.js`
4. `TasksSurface` + styles
5. Wire route in `NextApp.jsx`; optional `/tasks/:id` redirect
6. `TasksSurface.test.jsx` + affordance tests
7. Manual smoke

---

## Appendix: Relationship to requirements

| Req | Coverage |
|-----|----------|
| COM-04 Age visible | Row shows relative `created_at` age |
| COM-05 Inline status, due, owner, parent | Via `WorkboardItemAffordances` |
| COM-09 Logged update | Expandable update field → `activity_updates` |
| WRK-02 owner, project, age, due | Row shows owner, dates, age; project via group header |
