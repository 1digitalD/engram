# SLICE_2_2 — /api/v4/threads endpoint + Threads lens view

> **Phase 2 / v5-redesign-phase2-composition**
> **Task id:** `prd-threads`
> **Risk:** medium
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

Add a new backend route GET /api/v4/threads?rank=attention&limit=20 that returns ranked threads (people + projects + topics). Each thread: id, type, name, attention_score, attention_reasons, last_activity_at, last_context, key_items. Implementation: extend _coordination_radar_people and _coordination_radar_projects to return all threads (not just the radar-culled top 3); add a topic-clustering pass over notes with cosine similarity ≥0.7 to surface topic threads that don't have a parent entity. Add /api/v4/threads route handler. Frontend V5Threads.jsx consumes the endpoint and renders the ranked list (matches v5 mockup m-threads). Topics are a soft pass for this slice — can return [] if clustering is too expensive; ranked people + projects alone is enough to validate the IA.

## Acceptance criteria

- GET /api/v4/threads?rank=attention&limit=20 returns JSON with shape {threads: [{id, type, name, attention_score, attention_reasons, last_activity_at, last_context, key_items}]}
- Topic clustering is best-effort; if embedding similarity pass is too slow (>500ms), return [] for topics and log a warning; do not fail the request
- Attention reasons are the same reasons v4_attention.py computes per-entity, summed/aggregated for thread members
- last_context is a 1-sentence summary of the most recent activity (use the most recent note's content or 'last activity on <date>')
- Tests: tests/integration/test_v4_threads.py with test_threads_returns_active_people_and_projects, test_threads_ranked_by_attention, test_threads_includes_last_context, test_threads_topic_clustering_optional
- Frontend V5Threads.jsx renders the list with hot/warm/ambient bands (matches mockup m-threads)
- Mobile: single column, full-width thread cards (reuses V5EntityRow component from Slice 2.1)
- cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_threads.py tests/integration/test_v4_today.py passes
- cd /Volumes/lex1t/dev/shared/repos/engram/ui && npm test && npm run build
- Manual smoke: open /threads, verify ranked list of people + projects with attention_score visible, verify tap-through to thread detail (uses V4EntityDetail for this slice)

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram && grep -nE '/threads|@api_v4_bp\.route' api/v4_entities.py | grep -i thread
  cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_threads.py
  cd /Volumes/lex1t/dev/shared/repos/engram && curl -fsS 'http://localhost:5001/api/v4/threads?limit=5' | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "threads" in d; print(f"{len(d[\"threads\"])} threads returned")'
```

## Files affected

ui/src/App.jsx, ui/src/views/V5Now.jsx (new), ui/src/views/V5Threads.jsx (new), ui/src/views/V5ThreadDetail.jsx (new), ui/src/views/V5EntityRow.jsx (new), ui/src/views/V5Recall.jsx (new), ui/src/views/V5CaptureSheet.jsx (new), ui/src/components/XGlyph.jsx (new), ui/src/components/AIInspector.jsx (new), ui/src/components/Sheet.jsx (new), ui/src/components/TopBar.jsx (new), ui/src/api/v5Client.js (new), ui/src/styles/v5.module.css (new), ui/src/views/V4*.jsx (delete after V5 verified), api/v4_entities.py (new /api/v4/threads endpoint)

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_2_2_threads.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd-phase2.json` → `tasks[1]`

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
