# SLICE_UICTX01 — Recall search fix + density/color

> **Task id:** `ui-ctx-01-recall-search` | **Risk:** low | **Status:** done (2026-07-03)

Fix Recall API parsing (P0). Add match snippets, entity-type color accents, semantic status pills.

## Problem

`V5Recall` used `response.data`; `/api/v4/search` returns `{ results: [{ entity, match }] }`.
Tests mocked `{ data: [...] }`, masking production failure.

## Changes

- `ui/src/utils/searchResults.js` — `normalizeSearchResults()`
- `ui/src/api/v4Client.js` — search wrapper adds `data`
- `ui/src/views/V5Recall.jsx` — snippet, type borders, status colors, group counts
- `ui/src/views/V5Recall.module.css` — entity color treatment

## Validation

```bash
cd ui && npm test -- searchResults V5Recall && npm run build
```

Manual smoke: ⌘K → search a known entity title → result appears with snippet line.

## Acceptance

- [x] Recall parses real `{ results: [...] }` API payloads
- [x] Match snippet shown under title when present
- [x] Entity-type left border + group dot color
- [x] Blocked/waiting status uses semantic color
- [x] All UI tests pass
