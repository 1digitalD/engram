# SLICE_3_3 — /api/v4/timeline endpoint + V5Memory view (episodic chronology)

> **Phase 3 / v5-redesign-phase3-intelligence**
> **Task id:** `prd-timeline`
> **Risk:** medium
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

GET /api/v4/timeline?from=&to=&thread_id=&actor=&limit=&offset= returns a chronological event stream across all entities using the existing entity_events table. Each event: id, entity_id, entity_type, event_type, occurred_at, actor, narration (from Phase 1.3), thread_id (derived). Index: ensure entity_events has (occurred_at DESC) index or add via migration. UI: V5Memory view is a vertical timeline with date headers ('Today', 'Yesterday', 'Last week', 'May 2026', etc.), filter chips (entity_type, actor, thread), search box, and lazy loading. The view is the chronological complement to the Now surface; lets the user think in episodes not entities. Performance: paginate 50 events per page; 1000-event span should load in <500ms.

## Acceptance criteria

- GET /api/v4/timeline?from=&to=&thread_id=&actor= returns {events: [...], next_offset: ...} ordered by occurred_at DESC
- Migration scripts/migrations/005_timeline_index.sql adds (occurred_at DESC) index on entity_events if not present; runs idempotently
- Each event includes: id, entity_id, entity_type, event_type, occurred_at, actor, narration (from Phase 1.3), thread_id (derived via entity's parent project or assigned person)
- Pagination: limit (default 50, max 200), offset (cursor-style or numeric); query plan uses (occurred_at DESC) index
- Performance: query for 1000 events across all entities returns in <500ms; measured via tests/integration/test_v4_timeline.py::test_timeline_performance_1000_events
- V5Memory view: vertical timeline with date headers, filter chips, search box, lazy loading; matches mockup v5 mental model (date-grouped, not bucketed by entity type)
- Mobile: single column, full-width event cards, pull-to-refresh, infinite scroll
- tests/integration/test_v4_timeline.py with test_timeline_returns_events_desc, test_timeline_filtered_by_thread, test_timeline_filtered_by_actor, test_timeline_pagination, test_timeline_includes_narration, test_timeline_performance_1000_events
- cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_timeline.py tests/integration/test_v4_entity_detail.py passes

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram && test -f scripts/migrations/005_timeline_index.sql
  cd /Volumes/lex1t/dev/shared/repos/engram && grep -nE '/timeline|@api_v4_bp\.route' api/v4_entities.py | grep -i timeline
  cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_timeline.py
  cd /Volumes/lex1t/dev/shared/repos/engram && curl -fsS 'http://localhost:5001/api/v4/timeline?limit=10' | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "events" in d'
```

## Files affected

api/v4_entities.py (new /api/v4/ask, /api/v4/timeline, decisions-related routes), services/v4_extraction.py (decision extraction prompt update), services/v4_decisions.py (new — decision extraction, validation, query), services/v4_ask.py (new — RAG question answering, citation rendering), services/v4_timeline.py (new — chronological event stream across all entities), ui/src/views/V5AskSheet.jsx (new), ui/src/views/V5Memory.jsx (new — Memory view, vertical timeline with date headers), ui/src/components/CitationsList.jsx (new — inline citation rendering for Ask ✦), tests/integration/test_v4_decisions.py (new), tests/integration/test_v4_ask.py (new), tests/integration/test_v4_timeline.py (new), tests/fixtures/decisions_corpus.json (new — labeled decision extraction corpus)

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_3_3_timeline.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd-phase3.json` → `tasks[2]`

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
