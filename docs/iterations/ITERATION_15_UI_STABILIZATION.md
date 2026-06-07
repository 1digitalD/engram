# Iteration 15 — UI Stabilization

## Goal

Close the remaining shell and navigation polish issues after the workspace-summary stack landed, so the app behaves consistently before shifting focus away from frontend work.

## Why this slice

The baseline v4 UI structure is in place, but several live issues remained:

- duplicated top bars competing for vertical space
- entity-list state leaking when switching types through the sidebar
- inbox card nesting and layout instability
- route scroll/viewport regressions on detail pages
- false empty or broken-feeling list/detail behavior caused by shell layout rather than missing data

These are not new product surfaces. They are stabilization work needed to make the existing surfaces reliable and efficient.

## Scope

- make shell quick actions route-aware instead of globally duplicated
- tighten entity-list filtering/navigation state when the shared list component changes type
- simplify and stabilize inbox note-card layout
- make route-level views use the app shell viewport instead of full-window sizing
- restore scroll on entity detail pages through the shell/container contract
- keep changes within existing `/api/v4` payloads and current UI structure

## Implementation Notes

- The shell quick-action bar is now shown on Home only.
- Route-level screens now size against the route viewport instead of `100vh`.
- The route viewport is now a flex column so list/detail screens can own scroll correctly.
- Entity lists reload persisted state per entity type when the same mounted component is reused across sidebar navigation.
- Inbox note cards no longer nest tag links inside the primary card link.
- The shared list header now uses explicit status chips and a denser control layout.

## Validation

```bash
cd ui && npm test -- --run src/App.test.jsx src/views/V4EntityScreens.test.jsx src/views/V4Inbox.test.jsx
cd ui && npm test
cd ui && npm run build
```

## Result

- duplicate shell-level controls no longer compete with list and inbox headers
- entity type switches through the sidebar no longer leak stale filters
- inbox cards render and navigate more safely
- entity detail pages regain scrolling inside the app shell
- the UI is in a better state for backend/agentic work to become the next primary focus
