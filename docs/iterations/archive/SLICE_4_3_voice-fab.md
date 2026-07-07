# SLICE_4_3 — Long-press FAB activates voice capture (Web Speech API + fallback)

> **Phase 4 / v5-redesign-phase4-multimodal-polish**
> **Task id:** `prd-voice-fab`
> **Risk:** low
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

V5CaptureSheet's audio flow (Slice 4.1) requires the user to tap the mic icon, then tap to start, then tap to stop. The voice FAB adds a faster path: long-press the bottom-right FAB → browser's Web Speech API starts listening → on release, the transcript is sent to the server for extraction. Falls back to Slice 4.1's mic-icon flow if Web Speech API is unavailable (Safari has limited support, Firefox doesn't have it). The long-press gesture is a primary mobile affordance; on web, it's a power-user shortcut. Both paths produce the same capture experience from the user's perspective: transcribed text in preview, edit, save.

## Acceptance criteria

- ui/src/components/VoiceFAB.jsx wraps the existing FAB with long-press detection (~600ms hold)
- On long-press: Web Speech API starts listening; visual indicator (pulsing border) shows the FAB is recording
- On release: transcript is sent via the same path as Slice 4.1's audio flow; capture sheet opens with the transcript in preview
- Fallback: if Web Speech API is unavailable, the long-press triggers Slice 4.1's mic-icon flow (MediaRecorder)
- Web Speech API is browser-feature-detected; works on Chrome/Edge, may not work on Safari/Firefox
- Storybook: VoiceFAB in 3 states (idle, recording, fallback)
- cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test && npm run build
- Manual smoke on real device: long-press FAB, speak for 10s, release, verify transcript appears in preview, save, verify capture

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && test -f src/components/VoiceFAB.jsx
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run build
```

## Files affected

api/v4_entities.py (capture route accepts content_type: text|audio|image, content_base64), services/v4_transcription.py (new — Whisper integration for audio), services/v4_vision.py (new — vision model integration for images), ui/src/views/V5CaptureSheet.jsx (audio + image input controls, preview/edit before save), ui/src/components/VoiceFAB.jsx (new — long-press FAB for voice input), ui/src/hooks/useSwipeGesture.ts (new — swipe left/right on Now rows), ui/src/views/V5Settings.jsx (new — overflow menu, profile, theme), ui/src/components/LandmarkNav.jsx (new — accessibility landmarks for screen readers), tests/integration/test_v4_capture_multimodal.py (new), tests/fixtures/multimodal_corpus/ (new — 30 voice memos + 30 whiteboard photos with ground-truth text)

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_4_3_voice-fab.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd-phase4.json` → `tasks[2]`

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
