# Slice E3 — Inbox + Review merge

Status: DONE.

## Goal

Per `docs/V4_WORLD_MODEL_PLAN.md` Phase E, Slice E3: Inbox = capture form +
needs-review queue + recent captures (already the shape of `V4Inbox.jsx`).
`/suggestions` stays as a deep-link route but leaves the sidebar nav.

## Changes

### Frontend (`ui/src/App.jsx`)
- Removed the `['/suggestions', 'Review', Sparkles, 'suggestions']` entry
  from `viewItems` — "Review" no longer appears in the sidebar nav.
- Removed the now-unused `Sparkles` icon import.
- `useSidebarCounts` no longer tracks/returns a `suggestions` count (only
  `inbox` and `today` remain — both still sourced from the single
  `/api/v4/summary` call from Slice E1).
- The `/suggestions` route (`<Route path="/suggestions" element={<V4Suggestions />} />`)
  and the `V4Suggestions` view are unchanged — still reachable via deep
  links from `V4Inbox` ("Open review queue") and from capture-result
  suggestion counts.

### `ui/src/views/V4Inbox.jsx`
No changes — it already merges the capture form, "Needs review" queue, and
"Captured recently" list in one view, satisfying the Slice E3 shape.

## Tests (TDD, red → green)

- `ui/src/App.test.jsx`:
  - First test: added `expect(screen.queryByRole('link', { name: /^Review$/i
    })).not.toBeInTheDocument()`.
  - Second test ("renders sidebar counts from the summary endpoint"):
    removed the `Review` link assertion (the link no longer exists).

Full UI suite green: 44 passed (unchanged count). Build green.

## Acceptance criteria

- [x] "Review" removed from the sidebar nav.
- [x] `/suggestions` route still works as a deep link (unchanged).
- [x] Inbox already merges capture form + needs-review queue + recent
      captures — no further changes needed there.
- [x] Suite + UI green.
- [x] Not yet deployed — Phase E deploys after E4.
