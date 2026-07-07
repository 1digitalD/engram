# SLICE_4_5 — Settings + profile + overflow menu + accessibility audit (LandmarkNav, a11y fixes)

> **Phase 4 / v5-redesign-phase4-multimodal-polish**
> **Task id:** `prd-settings-a11y`
> **Risk:** low
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

Add a V5Settings view (theme, model preferences, capture sheet defaults) and a profile section. Add an overflow menu (⋯) in the top bar for less-used chrome (settings, profile, help). Add LandmarkNav component for proper ARIA landmarks (screen reader navigation). Run Lighthouse a11y audit on all V5 views; fix any issues. Address: focus rings, ARIA labels, color contrast, semantic HTML, keyboard nav, screen reader announcements for live events. Frontend-only slice; no backend changes.

## Acceptance criteria

- V5Settings view: theme picker, capture sheet defaults, model preferences (extract/ask/brief/summarization); saves to localStorage + (optional) /api/v4/users/me/preferences
- Top bar overflow menu (⋯): settings, profile, help, sign-out; opens a popover on tap
- ui/src/components/LandmarkNav.jsx adds <nav> + <main> + <aside> with proper aria-labels; verified via axe-core
- All interactive elements have visible focus rings (2px outline, high contrast); verified via keyboard nav
- All icons have aria-labels; all live regions (streaming events, AI processing) have aria-live='polite' or 'assertive'
- Color contrast: every text element meets WCAG AA (4.5:1 for normal, 3:1 for large); verified via Lighthouse
- Lighthouse a11y audit on all V5 views (Now, Threads, Thread detail, Recall, Capture, Ask, Memory, Settings): score ≥95 on every view
- axe-core a11y test suite added to frontend tests; runs in CI
- cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test && npm run build
- Manual smoke: navigate the full app with keyboard only; verify every interactive element is reachable, every focus ring is visible, every screen reader announcement is appropriate

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && test -f src/views/V5Settings.jsx && test -f src/components/LandmarkNav.jsx
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run build
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && grep -nE 'aria-live|aria-label|aria-expanded' src/components/LandmarkNav.jsx
```

## Files affected

api/v4_entities.py (capture route accepts content_type: text|audio|image, content_base64), services/v4_transcription.py (new — Whisper integration for audio), services/v4_vision.py (new — vision model integration for images), ui/src/views/V5CaptureSheet.jsx (audio + image input controls, preview/edit before save), ui/src/components/VoiceFAB.jsx (new — long-press FAB for voice input), ui/src/hooks/useSwipeGesture.ts (new — swipe left/right on Now rows), ui/src/views/V5Settings.jsx (new — overflow menu, profile, theme), ui/src/components/LandmarkNav.jsx (new — accessibility landmarks for screen readers), tests/integration/test_v4_capture_multimodal.py (new), tests/fixtures/multimodal_corpus/ (new — 30 voice memos + 30 whiteboard photos with ground-truth text)

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_4_5_settings-a11y.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd-phase4.json` → `tasks[4]`

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
