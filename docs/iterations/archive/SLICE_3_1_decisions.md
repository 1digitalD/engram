# SLICE_3_1 — Decisions as first-class records (extraction + schema + sheet)

> **Phase 3 / v5-redesign-phase3-intelligence**
> **Task id:** `prd-decisions`
> **Risk:** medium
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

Add a new entity type 'decision' that tracks explicit commitments. Schema: id, thread_id (FK entities.id), statement, context, decided_at, decided_by ('user' or 'agent:<name>'), source_note_id (FK entities.id), superseded_by (FK decisions.id, nullable). Extract from notes/tasks via prompt: 'only extract EXPLICIT commitments with named person and specific date or deliverable. Reject tentative language (maybe, we could, I think).' Decisions ALWAYS go to suggestions queue, never auto-apply (per §11.6 of 02-fresh-pass.md). UI: thread detail timeline shows ⚖ decision entries; thread header shows a 'decisions' count chip; new POST /api/v4/decisions creates manually. False positives are worse than false negatives — a wrongly-recorded decision implies a commitment. Conservative prompt + always-to-suggestions is the guardrail.

## Acceptance criteria

- scripts/migrations/004_decisions.sql creates the decisions table (idempotent); runs cleanly against the live DB
- services/v4_decisions.py extracts decisions from notes via conservative prompt; only emits suggestions, never auto-creates
- POST /api/v4/capture pipeline includes decision extraction; decisions appear as suggestions with reason='Explicit commitment detected: <statement>'
- GET /api/v4/decisions?thread_id=<id> returns the thread's decisions ordered by decided_at desc; supports limit and superseded filtering
- POST /api/v4/decisions creates a decision manually (user can record a decision without a source note)
- Thread detail timeline (V5ThreadDetail) shows ⚖ decision entries; thread header chip shows the count
- tests/integration/test_v4_decisions.py with test_decision_extracted_from_explicit_commitment, test_decision_rejected_for_tentative_language, test_decision_always_suggestion_not_auto, test_decision_manual_create, test_decision_superseded_chain
- Decision extraction precision ≥85% on labeled corpus (tests/fixtures/decisions_corpus.json); precision = true_positives / (true_positives + false_positives)
- cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_decisions.py tests/integration/test_v4_capture_extraction.py tests/integration/test_v4_suggestions.py passes

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram && test -f scripts/migrations/004_decisions.sql && grep -c 'CREATE TABLE' scripts/migrations/004_decisions.sql
  cd /Volumes/lex1t/dev/shared/repos/engram && test -f services/v4_decisions.py
  cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_decisions.py
  cd /Volumes/lex1t/dev/shared/repos/engram && curl -fsS http://localhost:5001/api/v4/health
```

## Files affected

api/v4_entities.py (new /api/v4/ask, /api/v4/timeline, decisions-related routes), services/v4_extraction.py (decision extraction prompt update), services/v4_decisions.py (new — decision extraction, validation, query), services/v4_ask.py (new — RAG question answering, citation rendering), services/v4_timeline.py (new — chronological event stream across all entities), ui/src/views/V5AskSheet.jsx (new), ui/src/views/V5Memory.jsx (new — Memory view, vertical timeline with date headers), ui/src/components/CitationsList.jsx (new — inline citation rendering for Ask ✦), tests/integration/test_v4_decisions.py (new), tests/integration/test_v4_ask.py (new), tests/integration/test_v4_timeline.py (new), tests/fixtures/decisions_corpus.json (new — labeled decision extraction corpus)

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_3_1_decisions.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd-phase3.json` → `tasks[0]`

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
