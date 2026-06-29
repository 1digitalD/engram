# SLICE_4_2 — Image capture via vision model (with preview/edit before save)

> **Phase 4 / v5-redesign-phase4-multimodal-polish**
> **Task id:** `prd-image-capture`
> **Risk:** medium
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

POST /api/v4/capture accepts content_type='image' + content_base64. The server sends the image to a vision model (gpt-4o-mini default; configurable) with a prompt 'Extract any visible text, notes, or diagram labels from this image as a single text block.' The extracted text becomes the note content; the rest of the capture pipeline runs as if the user had typed it. The capture sheet (V5CaptureSheet) gains an image input control (camera/gallery icon); on selection, the image is sent to the server. The extracted text is shown in a preview/edit area BEFORE the user confirms save. Same as audio: uncorrected errors propagate, so preview/edit is required.

## Acceptance criteria

- services/v4_vision.py exists with extract_text_from_image(image_bytes: bytes) -> str that calls a vision model and returns extracted text
- POST /api/v4/capture accepts content_type='image' + content_base64
- V5CaptureSheet image flow: tap camera → file input or camera capture → server extracts text → preview shown → user edits if needed → user taps Save → extraction runs
- Vision model is configurable via OPENAI_VISION_MODEL env var; default is gpt-4o-mini
- Performance: 1MB whiteboard photo → extracted and shown in preview within 10s
- Edit distance test: 30 whiteboard photos against ground-truth text; median edit distance ≤20% (vision is harder than audio)
- services/v4_vision.py handles vision model errors (timeout, image too large, low resolution) and returns a user-readable error
- tests/integration/test_v4_capture_multimodal.py with test_image_capture_extracts_text, test_image_capture_preview_editable, test_image_capture_vision_error_returned_to_user
- cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_capture_multimodal.py tests/integration/test_v4_capture_extraction.py passes
- Manual smoke: take a photo of a whiteboard, verify text extraction appears in preview, correct if needed, save, verify entity creation

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram && test -f services/v4_vision.py
  cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_capture_multimodal.py
```

## Files affected

api/v4_entities.py (capture route accepts content_type: text|audio|image, content_base64), services/v4_transcription.py (new — Whisper integration for audio), services/v4_vision.py (new — vision model integration for images), ui/src/views/V5CaptureSheet.jsx (audio + image input controls, preview/edit before save), ui/src/components/VoiceFAB.jsx (new — long-press FAB for voice input), ui/src/hooks/useSwipeGesture.ts (new — swipe left/right on Now rows), ui/src/views/V5Settings.jsx (new — overflow menu, profile, theme), ui/src/components/LandmarkNav.jsx (new — accessibility landmarks for screen readers), tests/integration/test_v4_capture_multimodal.py (new), tests/fixtures/multimodal_corpus/ (new — 30 voice memos + 30 whiteboard photos with ground-truth text)

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_4_2_image-capture.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd-phase4.json` → `tasks[1]`

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
