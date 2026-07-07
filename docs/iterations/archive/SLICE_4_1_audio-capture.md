# SLICE_4_1 — Audio capture via Whisper integration (with preview/edit before save)

> **Phase 4 / v5-redesign-phase4-multimodal-polish**
> **Task id:** `prd-audio-capture`
> **Risk:** medium
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

POST /api/v4/capture accepts content_type='audio' + content_base64. The server writes the audio to a temp file, runs Whisper (CLI: `whisper <temp> --model base --output_format txt`), reads the transcript, and proceeds through the existing extraction + reconciliation pipeline as if the user had typed the transcript. The capture sheet (V5CaptureSheet) gains an audio input control (mic icon); on tap, the browser's MediaRecorder API captures audio; on stop, the audio is sent to the server. The transcribed text is shown in a preview/edit area BEFORE the user confirms save. The user can correct transcription errors before extraction runs. This is critical because Whisper is ~85-95% accurate; uncorrected errors propagate to entity creation.

## Acceptance criteria

- services/v4_transcription.py exists with transcribe_audio(audio_bytes: bytes) -> str that calls the local whisper CLI and returns the transcript
- POST /api/v4/capture accepts content_type='audio' + content_base64 (and content_type='text' + content for backward compat)
- V5CaptureSheet audio flow: tap mic → MediaRecorder captures → stop → server transcribes → preview shown → user edits if needed → user taps Save → extraction runs
- Preview/edit area is editable; user MUST confirm before save (no auto-save on audio)
- Performance: 30s audio memo → transcribed and shown in preview within 8s on M-series Mac
- Edit distance test: 30 voice memos against ground-truth transcripts; median edit distance ≤15%
- services/v4_transcription.py handles Whisper errors gracefully (timeout, missing model, low audio quality) and returns a user-readable error
- tests/integration/test_v4_capture_multimodal.py with test_audio_capture_transcribes_and_extracts, test_audio_capture_preview_editable, test_audio_capture_whisper_error_returned_to_user
- cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_capture_multimodal.py tests/integration/test_v4_capture_extraction.py passes
- Manual smoke: record a 30s voice memo, verify transcription appears in preview, correct if needed, save, verify entity creation works as expected

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram && test -f services/v4_transcription.py
  cd /Volumes/lex1t/dev/shared/repos/engram && which whisper && whisper --help 2>&1 | head -5
  cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_capture_multimodal.py
```

## Files affected

api/v4_entities.py (capture route accepts content_type: text|audio|image, content_base64), services/v4_transcription.py (new — Whisper integration for audio), services/v4_vision.py (new — vision model integration for images), ui/src/views/V5CaptureSheet.jsx (audio + image input controls, preview/edit before save), ui/src/components/VoiceFAB.jsx (new — long-press FAB for voice input), ui/src/hooks/useSwipeGesture.ts (new — swipe left/right on Now rows), ui/src/views/V5Settings.jsx (new — overflow menu, profile, theme), ui/src/components/LandmarkNav.jsx (new — accessibility landmarks for screen readers), tests/integration/test_v4_capture_multimodal.py (new), tests/fixtures/multimodal_corpus/ (new — 30 voice memos + 30 whiteboard photos with ground-truth text)

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_4_1_audio-capture.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd-phase4.json` → `tasks[0]`

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
