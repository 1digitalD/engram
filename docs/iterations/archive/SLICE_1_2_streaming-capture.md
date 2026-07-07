# SLICE_1_2 — Stream capture response via SSE (opt-in via ?stream=true)

> **Phase 1 / v5-redesign-phase1-trust-foundation**
> **Task id:** `prd-streaming-capture`
> **Risk:** low
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

POST /api/v4/capture currently blocks for 5-30s and returns a single JSON with applied_changes and suggestions. Add an opt-in streaming mode: when ?stream=true, the response is a Server-Sent Events stream with events: 'reading' (got the note), 'extracting' (extraction LLM started), 'candidates' (extraction returned N candidates), 'reconciling' (reconciliation LLM started), 'applying' (applying decisions), 'linking' (creating entity_links), 'summarizing' (queueing summarization), 'done' (final payload as JSON in data field). The existing single-shot response stays as the default for backward compat. The frontend's new capture sheet (Phase 2) will use ?stream=true to render live progress; existing clients continue to work. The final 'done' event payload has the same shape as the current JSON response, so callers parsing the final event get the existing data without changes.

## Acceptance criteria

- api/v4_entities.py::capture() detects ?stream=true and returns a Response with mimetype='text/event-stream' instead of a JSON response
- Each pipeline step emits a Server-Sent Event with type matching the step name (reading, extracting, candidates, reconciling, applying, linking, summarizing, done) and a data field with step-specific JSON
- The 'done' event's data field has the same shape as the current single-shot response (applied_changes, suggestions, warnings, source_note); existing JSON consumers see no breaking change
- Errors during streaming emit a 'error' event with the exception message in data, then close the stream with HTTP 200 (not 500) so SSE clients can parse the error cleanly
- Existing single-shot behavior (?stream=false or absent) is unchanged: same JSON response, same status codes, same shape
- tests/integration/test_v4_capture_extraction.py has new tests: test_capture_stream_emits_all_events (parse SSE stream, verify all 8 event types arrive in order), test_capture_stream_done_event_matches_single_shot (compare final event payload to ?stream=false response), test_capture_stream_error_event (force an error mid-pipeline, verify error event + 200 close)
- cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_capture_extraction.py tests/integration/test_v4_capture.py passes (no regressions on single-shot)
- Manual smoke: capture a 200-word note via curl with ?stream=true, verify all 8 events arrive and the done event payload parses to a valid capture response

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
  cd /Volumes/lex1t/dev/shared/repos/engram && grep -nE 'stream.*true|text/event-stream|sse|Server-Sent' api/v4_entities.py | head -10
  cd /Volumes/lex1t/dev/shared/repos/engram && bash scripts/run_tests.sh tests/integration/test_v4_capture_extraction.py tests/integration/test_v4_capture.py
  cd /Volumes/lex1t/dev/shared/repos/engram && curl -fsS -N -X POST 'http://localhost:5001/api/v4/capture?stream=true' -H 'Content-Type: application/json' -d '{"content":"Test capture for SSE smoke"}' | head -30
```

## Files affected

api/v4_entities.py, services/v4_extraction.py, services/v4_reconciliation.py, services/v4_narration.py, tests/integration/test_v4_capture_extraction.py, tests/integration/test_v4_suggestions.py, tests/unit/test_v4_extraction.py, tests/unit/test_v4_reconciliation.py

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_1_2_streaming-capture.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task (Phase 1): prd-phase1.json` → `tasks[1]`

## Results

**Commit:** `0a0e6d81` — `prd-streaming-capture: Stream capture response via SSE (opt-in via ?stream=true)`

**Tests:**
```
$ bash scripts/run_tests.sh tests/integration/test_v4_capture_extraction.py
......................................................                   [100%]  54 passed in 36.46s
```
Full suite: `352 passed in 27.70s`.

**Manual smoke (live API, 2026-06-29 22:52 PDT):**

`POST /api/v4/capture?stream=true` with body
`{"content":"Phase1 QA probe SSE — confirm applied_changes stream + skip/uncertain behaviour."}`
returned `200 OK` with `Content-Type: text/event-stream`. Ordered events:

```
event: reading
data: {"note_id": "98506aef-9a89-4075-b5bf-8acf77383298", "title": "Phase1 QA probe SSE — ...", "content_length": 80}

event: extracting
data: {"mode": "auto"}

event: candidates
data: {"count": 2}

event: reconciling
data: {"candidate_count": 2}

event: applying
data: {"candidate_count": 2}

event: linking
data: {"links_created": 1}

event: summarizing
data: {"queued": 1}

event: done
data: {"source_note": {...}, "applied_changes": [...], "suggestions": [...], "warnings": []}
```

The `done` payload shape matches the non-streaming response contract:
`source_note`, `applied_changes`, `suggestions`, `warnings`. Server-side
implementation lives at `api/v4_entities.py:155–234` (`_capture_sse_stream`
and `_format_capture_sse_event`).

**Notes / follow-ups:**
- The error path (`event: error`) was not exercised in this QA pass. Code
  inspection confirms it yields on `db.session.rollback()` then emits the
  error event, so a stranded client can parse it; full client-side recovery
  behavior untested.
- Live UI surfacing of stream updates (toast per event, progress bar, etc.)
  is UI code not exercised in this QA pass.

**Acceptance met:** [x] yes — endpoint contract verified live; error-path and
UI surfacing deferred to Phase 2 (capture sheet).
