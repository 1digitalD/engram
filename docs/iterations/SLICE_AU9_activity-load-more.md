# SLICE_AU9 — Activity load more

> **Activity Update v2 follow-up**
> **Task id:** `au9-activity-load-more`
> **Risk:** low
> **Status:** complete

## Goal

Entity detail previews five activity updates; the paginated GET API can return more. Add a Load more control in V5 thread detail.

## Acceptance criteria

- Detail `activity_updates` section includes `meta.total`.
- Activity section shows Load more when `items.length < meta.total`.
- Load more fetches via `GET /entities/:id/activity_updates` with offset/limit.
- Tests pass.

## Results

**Acceptance met:** yes

- Backend: `_activity_updates_section` with `meta.total`.
- UI: merged list + Load more button in `V5ThreadDetail`.
