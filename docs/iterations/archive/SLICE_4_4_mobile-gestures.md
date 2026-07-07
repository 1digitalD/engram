# SLICE_4_4 — Mobile gestures: swipe left to snooze/dismiss, swipe right to mark done, pull-to-refresh

> **Phase 4 / v5-redesign-phase4-multimodal-polish**
> **Task id:** `prd-mobile-gestures`
> **Risk:** low
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

Add the gestures called out in §10.3 of 02-fresh-pass.md: swipe left on a Now row → quick dismiss / snooze (3-arg menu); swipe right on a Now row → mark done; pull-to-refresh on Now and Threads views; long-press a card → quick actions sheet; pinch on Thread detail → collapse/expand sections. The Now row swipe actions trigger the existing /api/v4/entities/<id>/status update endpoint. Pull-to-refresh invalidates the now/threads cache and re-fetches. Frontend-only slice; no backend changes.

## Acceptance criteria

- ui/src/hooks/useSwipeGesture.ts detects horizontal swipe gestures on Now rows; left swipe shows dismiss/snooze menu, right swipe marks done
- ui/src/hooks/usePullToRefresh.ts implements pull-to-refresh on Now and Threads views; invalidates the query cache and re-fetches
- V5EntityRow accepts swipe configuration: {onSwipeLeft, onSwipeRight, dismissable, markDoneable}; V5Now wires the actions to existing /api/v4/entities/<id>/status updates
- Long-press on a card opens a quick-actions sheet (overrides the FAB temporarily); matches the gesture called out in §10.3
- Pinch gesture on V5ThreadDetail: zoom out (pinch in) collapses all sections; zoom in (pinch out) expands all sections; use a library like react-use-gesture
- Touch targets are ≥44px (WCAG 2.5.5); verified via Storybook + Lighthouse
- Storybook: useSwipeGesture with 3 states (idle, swiping-left, swiped-left), usePullToRefresh with 2 states (idle, refreshing)
- cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test && npm run build
- Manual smoke on real device: swipe-left on a Now row, swipe-right on a Now row, pull-to-refresh on Threads

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && test -f src/hooks/useSwipeGesture.ts && test -f src/hooks/usePullToRefresh.ts
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run build
```

## Files affected

api/v4_entities.py (capture route accepts content_type: text|audio|image, content_base64), services/v4_transcription.py (new — Whisper integration for audio), services/v4_vision.py (new — vision model integration for images), ui/src/views/V5CaptureSheet.jsx (audio + image input controls, preview/edit before save), ui/src/components/VoiceFAB.jsx (new — long-press FAB for voice input), ui/src/hooks/useSwipeGesture.ts (new — swipe left/right on Now rows), ui/src/views/V5Settings.jsx (new — overflow menu, profile, theme), ui/src/components/LandmarkNav.jsx (new — accessibility landmarks for screen readers), tests/integration/test_v4_capture_multimodal.py (new), tests/fixtures/multimodal_corpus/ (new — 30 voice memos + 30 whiteboard photos with ground-truth text)

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_4_4_mobile-gestures.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd-phase4.json` → `tasks[3]`

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
