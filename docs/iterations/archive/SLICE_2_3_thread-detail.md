# SLICE_2_3 — Thread detail view (continuous timeline + next actions + decisions + people + related threads)

> **Phase 2 / v5-redesign-phase2-composition**
> **Task id:** `prd-thread-detail`
> **Risk:** low
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

Build V5ThreadDetail.jsx as the new deep surface. Replaces V4EntityDetail. Same regions for every entity type (project, person, area, resource, task, note): header (type glyph + title + status), narrative summary (from existing summarization or 'I haven't summarized this yet'), next actions (extracted from child tasks + decisions + blocking entities), continuous timeline (entity_events with narration from Phase 1.3), people section (typed relationships), related threads (clusters that share members with this thread). Narrative summary uses the existing canonical_document.py or a short 'current state' summary if available. Type-specific workspace panels (project_pulse, person_pulse, dependency_watch) are folded into the 'next actions' section as inline cards; not boxed regions. Mobile: single column, full-width sections, long-press for actions.

## Acceptance criteria

- ui/src/views/V5ThreadDetail.jsx renders all 5 regions (header, narrative, next actions, timeline, people, related threads) for every entity type
- Timeline uses event.narration from Phase 1.3; no raw event_type strings visible to the user
- Next actions section surfaces top 3 things the user could do (open task, send reminder, decide, etc.); each action has an inline button
- Type-specific signals (project_pulse, person_pulse) appear as compact cards inside the 'next actions' section, not as separate boxed panels
- Storybook story: V5ThreadDetail for each entity type (project, person, area, resource, task, note) with sample data
- Mobile layout: single column, full-width sections, FAB still bottom-right (matches mockup m-thread-detail-mobile)
- Lighthouse a11y ≥95
- cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test && npm run build
- Manual smoke: tap into a project, a person, and a note thread; verify the layout is consistent across types and the timeline reads as a story not a log

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && test -f src/views/V5ThreadDetail.jsx
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run build
```

## Files affected

ui/src/App.jsx, ui/src/views/V5Now.jsx (new), ui/src/views/V5Threads.jsx (new), ui/src/views/V5ThreadDetail.jsx (new), ui/src/views/V5EntityRow.jsx (new), ui/src/views/V5Recall.jsx (new), ui/src/views/V5CaptureSheet.jsx (new), ui/src/components/XGlyph.jsx (new), ui/src/components/AIInspector.jsx (new), ui/src/components/Sheet.jsx (new), ui/src/components/TopBar.jsx (new), ui/src/api/v5Client.js (new), ui/src/styles/v5.module.css (new), ui/src/views/V4*.jsx (delete after V5 verified), api/v4_entities.py (new /api/v4/threads endpoint)

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_2_3_thread-detail.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd-phase2.json` → `tasks[2]`

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
