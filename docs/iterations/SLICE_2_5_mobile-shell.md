# SLICE_2_5 — Mobile responsive layouts for Now, Threads, Thread detail (final pass + delete V4)

> **Phase 2 / v5-redesign-phase2-composition**
> **Task id:** `prd-mobile-shell`
> **Risk:** low
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

After 2.1-2.4 land, do a mobile-responsive pass on the full app: V5Recall (search/ask palette as bottom sheet), V5ThreadDetail (single column), all the modals (bottom sheets on mobile). Verify the V4 views are no longer used; delete V4Home, V4Today, V4Inbox, V4EntityList, V4EntityDetail, V4Suggestions, V4AgentActivity, V4Search from ui/src/views/. Remove the feature flag in App.jsx; V5 is the only path. This is the cleanup that makes Phase 2 actually shippable. If V4 deletion reveals a gap in V5 (e.g. a view that wasn't migrated), add the missing slice to Phase 2 and re-validate before moving to Phase 3.

## Acceptance criteria

- V5Recall implemented as a bottom sheet on mobile (full-screen modal on desktop) — reuses the ⌘K palette logic
- All modals (capture, ask, decision) render as bottom sheets on mobile (was: centered modals on desktop)
- V4 views deleted from ui/src/views/: V4Home, V4Today, V4Inbox, V4EntityList, V4EntityDetail, V4Suggestions, V4AgentActivity, V4Search
- App.jsx feature flag removed; V5 is the only path
- Lighthouse mobile audit: performance ≥85, a11y ≥95, best-practices ≥90, PWA (basic installability) optional
- Manual smoke on real device (Safari iOS, Chrome Android) for: Now render, Thread detail scroll, capture sheet open/close, search palette open
- cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test && npm run build
- cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run lint (if configured)

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && ! test -f src/views/V4Home.jsx && ! test -f src/views/V4Today.jsx && ! test -f src/views/V4Inbox.jsx && ! test -f src/views/V4EntityDetail.jsx
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run build
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && grep -nE 'FEATURE_FLAG_V5|useV5|V5_ENABLED' src/App.jsx || echo 'no feature flag (good)'
```

## Files affected

ui/src/App.jsx, ui/src/views/V5Now.jsx (new), ui/src/views/V5Threads.jsx (new), ui/src/views/V5ThreadDetail.jsx (new), ui/src/views/V5EntityRow.jsx (new), ui/src/views/V5Recall.jsx (new), ui/src/views/V5CaptureSheet.jsx (new), ui/src/components/XGlyph.jsx (new), ui/src/components/AIInspector.jsx (new), ui/src/components/Sheet.jsx (new), ui/src/components/TopBar.jsx (new), ui/src/api/v5Client.js (new), ui/src/styles/v5.module.css (new), ui/src/views/V4*.jsx (delete after V5 verified), api/v4_entities.py (new /api/v4/threads endpoint)

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_2_5_mobile-shell.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd-phase2.json` → `tasks[4]`

## Results (filled in by Loopsmith on completion)

<!-- Loopsmith agent: fill in below. Replace each placeholder with actual evidence.
     Required: test output (last 10-20 lines), commit SHA, replay metrics diff (if AI-touching).
-->

**Commit:** `<sha>`

**Tests:**
```
<paste test output>
```

**Replay metrics (if applicable):**
```
<paste replay_eval.py output>
```

**Manual smoke:**
<describe what you tested, what passed, what didn't>

**Notes / follow-ups:**
<any caveats, follow-up slices, or things the next slice should know>

**Acceptance met:** [ ] yes / [ ] no (if no, document what's missing)
