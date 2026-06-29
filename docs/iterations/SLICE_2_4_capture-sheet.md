# SLICE_2_4 — Capture sheet with streaming response and contextual thread attachment

> **Phase 2 / v5-redesign-phase2-composition**
> **Task id:** `prd-capture-sheet`
> **Risk:** low
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

Build V5CaptureSheet.jsx as a modal sheet (web) or bottom sheet (mobile) that opens from the FAB. The sheet has a single multi-line input. When the user types in a thread context, the sheet auto-attaches to that thread (the attachment is shown at the top, can be changed via a dropdown). On save, the sheet uses POST /api/v4/capture?stream=true and renders live progress events from the SSE stream. After the 'done' event, the sheet closes with a 1.5-second toast 'Saved · AI processing (N applied, M suggested). [View]'. Errors render inline; user can retry. The sheet replaces the old capture form in V4Inbox. The copy in the placeholder text is honest: 'Type anything. I'll suggest what I think it means; you can revert any of it after saving.' NOT 'AI will figure out what you mean' (that was the magical-thinking copy in Pass 2.0, replaced in Pass 2.5).

## Acceptance criteria

- ui/src/views/V5CaptureSheet.jsx opens from the FAB on any screen; context-aware: tap from inside a thread → attached by default; tap from Now or Threads → generic
- Save uses POST /api/v4/capture?stream=true; live events render as they arrive (e.g. 'extracting…', 'linking Mary to HITL…', 'done')
- Final 'done' event payload closes the sheet and shows a 1.5s toast with applied count + suggested count + [View] link
- Errors render inline with retry button; sheet stays open on error
- Mobile: slide-up bottom sheet, takes full width, drag-down to dismiss, FAB replaced by a header bar (input only)
- Placeholder text is honest about AI behavior; copy matches the v5 spec (not the Pass 2.0 magical-thinking version)
- Storybook: capture sheet in 3 states (empty, typing, streaming), 3 attachment states (none, thread, project)
- cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test && npm run build
- Manual smoke: capture from Now, capture from inside a thread (verify auto-attach), verify streaming events render in real time

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && test -f src/views/V5CaptureSheet.jsx
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run build
```

## Files affected

ui/src/App.jsx, ui/src/views/V5Now.jsx (new), ui/src/views/V5Threads.jsx (new), ui/src/views/V5ThreadDetail.jsx (new), ui/src/views/V5EntityRow.jsx (new), ui/src/views/V5Recall.jsx (new), ui/src/views/V5CaptureSheet.jsx (new), ui/src/components/XGlyph.jsx (new), ui/src/components/AIInspector.jsx (new), ui/src/components/Sheet.jsx (new), ui/src/components/TopBar.jsx (new), ui/src/api/v5Client.js (new), ui/src/styles/v5.module.css (new), ui/src/views/V4*.jsx (delete after V5 verified), api/v4_entities.py (new /api/v4/threads endpoint)

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_2_4_capture-sheet.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd-phase2.json` → `tasks[3]`

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
