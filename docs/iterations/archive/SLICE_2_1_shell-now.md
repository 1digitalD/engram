# SLICE_2_1 — Top bar (3 lenses + FAB + Ask + trust score) and Now view (sentence-shaped rows)

> **Phase 2 / v5-redesign-phase2-composition**
> **Task id:** `prd-shell-now`
> **Risk:** low
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

Build the new top bar component (TopBar.jsx) with: brand glyph, three lens toggles (Now / Threads / Recall), + Ask ✦ button, theme switcher, trust score chip. Build the new Now view (V5Now.jsx) that fetches /api/v4/today and renders ranked items as sentence-shaped rows. Each row: subject (one sentence), metadata (when + why-it-matters-now + thread context), 1-3 action buttons. Initial data: mocked JSON matching the v5 mockup-pass2.html screen; switch to live /api/v4/today once Slice 2.2 threads endpoint lands. Soft labels separate 'needs you now,' 'waiting on you,' 'ambient.' The capture sheet is not in this slice — that's Slice 2.4. Mobile responsive: same content, full-width cards, FAB prominent bottom-right.

## Acceptance criteria

- ui/src/components/TopBar.jsx renders brand + 3 lens toggles + Ask button + theme + trust score; matches v5 mockup (00-overview.md §'The new UI')
- ui/src/views/V5Now.jsx fetches /api/v4/today (or mocked data) and renders ranked items as sentence-shaped rows; matches v5 mockup (mockup-pass2.html screen m-now)
- Mobile: same content in single column, full-width cards, FAB bottom-right (mockup-pass2.html screen m-mobile)
- Storybook stories for TopBar (3 states: default, theme=dark, trust low) and Now (3 states: needs-you-now, waiting-on-you, ambient)
- Lighthouse a11y score ≥95 on both desktop and mobile renders
- Routes: /now, /threads, /recall (placeholder for now); feature flag in App.jsx toggles V4 vs V5
- cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test passes (frontend suite green)
- cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run build passes
- Manual smoke: open /now, verify three sections render with realistic data, verify tap-through to entity detail (existing V4EntityDetail still works for this slice)

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && test -f src/components/TopBar.jsx && test -f src/views/V5Now.jsx
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run build
```

## Files affected

ui/src/App.jsx, ui/src/views/V5Now.jsx (new), ui/src/views/V5Threads.jsx (new), ui/src/views/V5ThreadDetail.jsx (new), ui/src/views/V5EntityRow.jsx (new), ui/src/views/V5Recall.jsx (new), ui/src/views/V5CaptureSheet.jsx (new), ui/src/components/XGlyph.jsx (new), ui/src/components/AIInspector.jsx (new), ui/src/components/Sheet.jsx (new), ui/src/components/TopBar.jsx (new), ui/src/api/v5Client.js (new), ui/src/styles/v5.module.css (new), ui/src/views/V4*.jsx (delete after V5 verified), api/v4_entities.py (new /api/v4/threads endpoint)

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_2_1_shell-now.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd-phase2.json` → `tasks[0]`

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
