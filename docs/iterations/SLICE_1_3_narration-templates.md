# SLICE_1_3 — Templated AI narration on entity_events (read-side, cached)

> **Phase 1 / v5-redesign-phase1-trust-foundation**
> **Task id:** `prd-narration-templates`
> **Risk:** low
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

entity_events rows have event_type and reason but no human-readable narration. The agent_activity page shows raw event types ('ai_updated at 14:32') instead of plain English. Add a services/v4_narration.py module that generates a 1-sentence narration for each event_type via a small set of templates. Templates are deterministic: 'ai_updated' + payload {task_created: X, from_note: Y} → 'I created task X from your note Y.' Templates cover the 80% case; the remaining 20% (complex multi-step events) fall back to a default 'I updated this entity.' Surface as event.narration on /api/v4/entities/<id>/events responses. Generated on read, cached per event_id in memory (LRU 10k entries); invalidated on entity revert. No LLM call in the read path — pure template substitution. This is the read-side companion to the existing entity_events writer; no writer changes.

## Acceptance criteria

- services/v4_narration.py exists with a function narrate_event(event: EntityEvent) -> str that returns a 1-sentence plain-English description of the event
- Templates cover these event_types: created, updated, status_changed, archived, deleted, relationship_added, relationship_updated, relationship_removed, tag_added, tag_removed, ai_processed, ai_updated, ai_summarized, suggestion_accepted, suggestion_dismissed, suggestion_expired, review_marked_resolved, activity_update_added, merged, merged_into, type_converted (read ENTITY_EVENT_TYPES from api/v4_entities.py to confirm the set)
- Each template uses payload fields when present: 'ai_updated' + {task_created: X, from_note: Y} → 'I created task X from your note Y'; 'suggestion_accepted' + {target_title: X} → 'You accepted the suggestion for X'
- An LRU cache (max 10k entries) keyed on event_id wraps the template function so repeated reads are O(1) after the first
- GET /api/v4/entities/<id>/events response includes a new 'narration' field on each event (string); existing fields are unchanged
- tests/unit/test_v4_narration.py has new tests: test_narration_ai_updated_with_task_created, test_narration_suggestion_accepted, test_narration_default_for_unknown_payload, test_narration_cache_hit (same event_id called twice → second call is cached)
- cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/unit/test_v4_narration.py tests/integration/test_v4_entity_detail.py tests/integration/test_v4_capture_extraction.py passes
- Manual smoke: GET /api/v4/entities/<id>/events for an entity with 5+ events, verify every event has a non-empty 'narration' field that reads as a sentence

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram && test -f services/v4_narration.py && grep -nE 'def narrate_event|ENTITY_EVENT_TYPES|templates' services/v4_narration.py | head -10
  cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/unit/test_v4_narration.py tests/integration/test_v4_entity_detail.py tests/integration/test_v4_capture_extraction.py
  cd /Volumes/lex1t/dev/shared/repos/engram && curl -fsS http://localhost:5001/api/v4/entities/<id>/events | python3 -c 'import json,sys; d=json.load(sys.stdin); assert all("narration" in e for e in d), "missing narration"; print("ok")'
```

## Files affected

api/v4_entities.py, services/v4_extraction.py, services/v4_reconciliation.py, services/v4_narration.py, tests/integration/test_v4_capture_extraction.py, tests/integration/test_v4_suggestions.py, tests/unit/test_v4_extraction.py, tests/unit/test_v4_reconciliation.py

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_1_3_narration-templates.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task (Phase 1): prd-phase1.json` → `tasks[2]`

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
