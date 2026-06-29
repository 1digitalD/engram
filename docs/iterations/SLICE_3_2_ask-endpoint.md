# SLICE_3_2 — /api/v4/ask endpoint + V5AskSheet with honest 'I don't know' state

> **Phase 3 / v5-redesign-phase3-intelligence**
> **Task id:** `prd-ask-endpoint`
> **Risk:** medium
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

POST /api/v4/ask takes a question, runs hybrid search to retrieve top-k context, generates a grounded answer with citations. Response shape: {answer, citations: [{entity_id, snippet, relevance}], confidence: high|medium|low, caveats: [...], suggested_actions: [{type, label, payload}]}. When confidence is low or context is empty, return honest 'I don't have anything in the workspace that answers this' response with caveats explaining why. NEVER confabulate. Cache answers for 24h keyed on (question, top-k context hash). UI: V5AskSheet opens from the + Ask ✦ button in the top bar; shows the question, thinking state, then answer with citations. When confidence is low, the sheet shows the 'I don't know' state with a 'Capture starting point' action.

## Acceptance criteria

- POST /api/v4/ask with {question: 'What did Mary say about the PR review?'} returns {answer, citations, confidence, caveats, suggested_actions}
- When question has no in-workspace grounding: answer is 'I don't have anything in the workspace that answers this' with caveats explaining why; confidence is 'low'
- Citations always present when answer is grounded; inline format: 📝 'snippet' — entity_id
- Confidence high requires ≥2 citations with relevance ≥0.7; medium is 1 citation or 2+ with relevance <0.7; low is 0 citations
- Cache: 24h TTL keyed on sha256(question + top_k_context_hash); cache hit returns same response without re-running LLM
- services/v4_ask.py uses services.v4_search for hybrid retrieval; uses services.v4_brief.BRIEF_MODEL for answer generation (no new model needed)
- tests/integration/test_v4_ask.py with test_ask_returns_grounded_answer, test_ask_returns_low_confidence_when_no_context, test_ask_includes_citations, test_ask_low_confidence_state_does_not_confabulate, test_ask_cache_hit
- V5AskSheet opens from top bar; renders question, thinking state, answer with citations, suggested actions; 'I don't know' state with Capture starting point action
- cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_ask.py tests/integration/test_v4_search.py passes
- Manual smoke: ask 'What did Mary say about the PR review?' (grounded in note from Jun 22) and 'Did Mary say anything about Q3 budget in her last 1:1?' (no grounding) — verify the second returns the honest 'I don't know' state

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram && test -f services/v4_ask.py
  cd /Volumes/lex1t/dev/shared/repos/engram && grep -nE '/ask|@api_v4_bp\.route' api/v4_entities.py | grep -i ask
  cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_ask.py
  cd /Volumes/lex1t/dev/shared/repos/engram && curl -fsS -X POST http://localhost:5001/api/v4/ask -H 'Content-Type: application/json' -d '{"question":"test"}' | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "confidence" in d'
```

## Files affected

api/v4_entities.py (new /api/v4/ask, /api/v4/timeline, decisions-related routes), services/v4_extraction.py (decision extraction prompt update), services/v4_decisions.py (new — decision extraction, validation, query), services/v4_ask.py (new — RAG question answering, citation rendering), services/v4_timeline.py (new — chronological event stream across all entities), ui/src/views/V5AskSheet.jsx (new), ui/src/views/V5Memory.jsx (new — Memory view, vertical timeline with date headers), ui/src/components/CitationsList.jsx (new — inline citation rendering for Ask ✦), tests/integration/test_v4_decisions.py (new), tests/integration/test_v4_ask.py (new), tests/integration/test_v4_timeline.py (new), tests/fixtures/decisions_corpus.json (new — labeled decision extraction corpus)

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_3_2_ask-endpoint.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd-phase3.json` → `tasks[1]`

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
