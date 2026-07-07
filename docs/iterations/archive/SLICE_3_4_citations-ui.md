# SLICE_3_4 — Cross-link Ask ✦ citations into thread detail + Memory view

> **Phase 3 / v5-redesign-phase3-intelligence**
> **Task id:** `prd-citations-ui`
> **Risk:** low
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

Citations from Ask ✦ answers are returned as objects with entity_id and snippet. Add a CitationsList component that renders them as inline cards (📝 glyph + snippet preview + date + link to entity). Wire CitationsList into V5AskSheet (inline below the answer), V5ThreadDetail (a 'references' section showing all entities that cite this thread), and V5Memory (event rows include clickable citation links). When a citation is clicked, open the cited entity in a sheet (not a navigation) so the user can read it and return. Frontend-only slice; no backend changes.

## Acceptance criteria

- ui/src/components/CitationsList.jsx renders citations as cards with 📝 glyph, snippet preview (truncated to 140 chars), date, and 'open' button
- V5AskSheet renders CitationsList inline below the answer; clicking a citation opens a side sheet with the full entity
- V5ThreadDetail has a 'references' section showing entities that cited this thread (from Ask ✦ answers where citation.entity_id is related to the current thread); cross-link via the entity's parent project or assigned person
- V5Memory event rows include clickable citation links when the event has a source_note_id; clicking opens a side sheet
- Citation side sheet: read-only view of the entity, with a 'back' button to return to the previous view; the previous view's state is preserved
- Storybook: CitationsList in 3 states (single citation, multiple citations, no citations)
- cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test && npm run build
- Manual smoke: open Ask ✦, ask a grounded question, tap a citation, verify the side sheet opens with the cited entity, tap 'back' to return

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && test -f src/components/CitationsList.jsx
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test
  cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm run build
```

## Files affected

api/v4_entities.py (new /api/v4/ask, /api/v4/timeline, decisions-related routes), services/v4_extraction.py (decision extraction prompt update), services/v4_decisions.py (new — decision extraction, validation, query), services/v4_ask.py (new — RAG question answering, citation rendering), services/v4_timeline.py (new — chronological event stream across all entities), ui/src/views/V5AskSheet.jsx (new), ui/src/views/V5Memory.jsx (new — Memory view, vertical timeline with date headers), ui/src/components/CitationsList.jsx (new — inline citation rendering for Ask ✦), tests/integration/test_v4_decisions.py (new), tests/integration/test_v4_ask.py (new), tests/integration/test_v4_timeline.py (new), tests/fixtures/decisions_corpus.json (new — labeled decision extraction corpus)

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_3_4_citations-ui.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd-phase3.json` → `tasks[3]`

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
