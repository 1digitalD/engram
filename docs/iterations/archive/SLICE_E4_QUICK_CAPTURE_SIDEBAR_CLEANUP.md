# Slice E4 — Quick capture textarea + sidebar cleanup

Status: DONE.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase E, Slice E4 (final slice of Phase E):
swap the rich-text `MarkdownEditor` in the shell `QuickActionBar` for a
plain `<textarea>`, and remove "Agent log" from the sidebar nav (route
kept for deep links). **Deploys Phase E.**

## Changes

### Frontend (`ui/src/App.jsx`)
- `QuickActionBar`'s note-capture field is now a plain `<textarea
  aria-label="Quick note content">` instead of `<MarkdownEditor>` — removes
  the now-unused `MarkdownEditor` import. Existing `.quickForm textarea`
  styling (border/radius/focus ring) already applied generically, so no new
  CSS needed.
- Removed `['/agent-activity', 'Agent log', Activity, null]` from
  `viewItems` (sidebar nav) and the now-unused `Activity` icon import.
  `<Route path="/agent-activity" element={<V4AgentActivity />} />` is
  unchanged — the page is still reachable by URL, just no longer in the
  sidebar.

## Tests (TDD, red → green)

- `ui/src/App.test.jsx`:
  - Removed the `vi.mock('./components/MarkdownEditor', ...)` mock (no
    longer imported by `App.jsx`); the quick-note test now exercises the
    real `<textarea aria-label="Quick note content">`.
  - First test: replaced the "Agent log" link assertion with
    `expect(screen.queryByRole('link', { name: /Agent log/i
    })).not.toBeInTheDocument()` (alongside the existing "Review" absence
    check from Slice E3).

Full UI suite green: 44 passed (unchanged count). Build green. Full backend
suite green: 226 passed (unchanged — no backend changes in this slice).

## Acceptance criteria

- [x] Quick-capture note field is a plain `<textarea>`.
- [x] "Agent log" removed from sidebar nav; `/agent-activity` route intact.
- [x] Suite + UI green.
- [x] Deploys Phase E.
