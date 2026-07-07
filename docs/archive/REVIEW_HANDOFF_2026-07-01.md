# Engram Review Handoff - 2026-07-01

This document is a fresh-session handoff for continued review and optimization of Engram v4.

It captures:
- verified fixes already made
- remaining confirmed bugs
- likely workflow and product risks
- cleanup and maintenance gaps
- production data insights
- validation already performed
- a ready-to-paste prompt for a new Codex session

## Ground Rules

- Repo root: `/Volumes/lex1t/dev/shared/repos/engram`
- Read first:
  - `AGENTS.md`
  - `docs/V4_PRINCIPLES.md`
  - `docs/V4_WORLD_MODEL_PLAN.md`
  - `EXECUTION-TRACKER.md`
  - `mcp_server/README_V4.md`
- Production DB is real: `postgresql://engram:engram@localhost:5432/engram`
- Never run destructive commands against prod
- Tests must use:
  - `TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test`
- Backend pytest must run serially, not in parallel
- `psql` is not on `PATH`; use:
  - `/opt/homebrew/opt/libpq/bin/psql`

## Verified Fixes Already Landed

These were implemented, tested, deployed, and live-verified earlier in the session:

1. `Now` navigation split fixed
- Item cards now distinguish between opening the item itself vs opening its thread context.

2. Direct editing restored on thread detail
- Attributes can again be edited directly from detail views.

3. Truthful thread totals restored in backend
- Thread counts were corrected so UI totals align with backend reality.

4. Memory `actor=agent:` filter fixed
- Timeline filtering for agent actors now behaves correctly.

5. `Open thread` fallback fixed on task detail
- When a task lacks a dedicated thread target, the button now falls back to a related thread instead of linking to itself or doing nothing.
- Live verification target:
  - task: `68b0a6a8-a135-4431-ba03-dfe851cdd099`
  - expected thread destination after reload: `/projects/657be076-3ae2-4753-9141-9594bfb8acf6`

Frontend validation was green after these fixes:
- `cd ui && npm test`
- `cd ui && npm run build`

## Confirmed Bugs / Product Gaps

Ordered roughly by severity and user impact.

### 1. Meeting/session prep exists in backend but is invisible in the UI

Why it matters:
- This blocks one of the highest-value workflows: preparing for a 1:1, project review, or stakeholder sync from the person/project thread itself.

Evidence:
- Backend detail payload includes:
  - `current_load`
  - `pulse`
  - `dependency_watch`
  - `meeting_prep`
- Main reference:
  - `api/v4_entities.py`
- Live verified on person:
  - `5f1e93c3-050a-4e0b-93fa-fae9a0abd8f8` (`Gonick Nalwa`)
- The response included:
  - `meeting_prep.headline`
  - `agenda_items`
  - `recent_notes`
- Current detail UI does not render these structures:
  - `ui/src/views/V5ThreadDetail.jsx`

### 2. `Now` is underusing `/api/v4/today`

Why it matters:
- `Now` should be the main operating surface, but it omits several backend-computed attention buckets that would make it genuinely useful day to day.

Evidence:
- `/api/v4/today` already returns:
  - `recent_notes`
  - `blocked_tasks`
  - `waiting_tasks`
  - `follow_ups`
  - `overdue_follow_ups`
  - `unscheduled_attention_tasks`
  - `new_since_yesterday_count`
  - and other useful buckets
- Current `V5Now` uses only a subset:
  - `overdue`
  - `due_today`
  - `delegations_quiet`
  - `dependency_interventions`
  - `stale_projects`
  - `suggested_archival`
- Main reference:
  - `ui/src/views/V5Now.jsx`

### 3. `Ask Engram` fails obvious daily-review questions

Why it matters:
- A user should be able to ask operational questions like "What changed today?" and get a grounded answer.
- Failure here makes the product feel unreliable even when the data exists.

Evidence:
- Live tested question:
  - `What changed today?`
- Result:
  - `I don't have anything in the workspace that answers this.`
- Meanwhile `/api/v4/timeline?limit=5` clearly returned today’s events.
- Main UI reference:
  - `ui/src/views/V5AskSheet.jsx`

### 4. `Recall` copy and behavior drift

Why it matters:
- The input says `Search or ask…`, which sets an expectation the product does not fulfill.
- This increases confusion and makes the surface feel less trustworthy.

Evidence:
- `Recall` currently only calls `v4API.search(...)`
- It does not execute Ask behavior
- Fallback action is `Capture`
- Main reference:
  - `ui/src/views/V5Recall.jsx`

### 5. `Memory` is still too audit-log-like and low-signal

Why it matters:
- The memory/timeline surface should support recall and reflection, not force the user to parse raw event noise.
- Current behavior makes it hard to understand meaningful changes in the workspace.

Evidence:
- Live page dominated by repetitive events such as:
  - `Updated follow-up, updated at.`
- No compaction, grouping, or digest behavior
- Raw `Thread ID filter` still exposed in UI
- Main references:
  - `ui/src/views/V5Memory.jsx`

### 6. `Snooze` and `Send reminder` are opaque actions

Why it matters:
- The buttons look meaningful, but both currently mean roughly "set `follow_up_at` to now + 24h".
- This is surprising, weak for real follow-up workflows, and easy to misuse.

Evidence:
- `Snooze` behavior in `Now` and `Send reminder` in detail currently mutate follow-up time in a simplistic way
- Main references:
  - `ui/src/views/V5Now.jsx`
  - `ui/src/views/V5ThreadDetail.jsx`

## Likely Risks

These were not all fully reproduced as defects, but they are strong risks based on live behavior, code shape, or production data.

### 1. The app behaves more like a database browser than a daily operating system

Why it matters:
- The user wants this as the default productivity surface for notes, follow-ups, org tracking, and prep.
- Today the backend computes more value than the UI actually surfaces.

### 2. Capture-to-distillation is happening, but the payoff is hidden

Evidence:
- Production data shows many AI-added links, summaries, and extracted structure.
- The UI does not consistently turn that into strong next actions, summaries, or review loops.

### 3. Task anchoring quality may degrade follow-through

Evidence from production data:
- Open active tasks total: `37`
- Tasks without parent link: `7`
- Tasks without owner / `assigned_to`: `21`

Why it matters:
- Tasks without ownership or context are much easier to drop.

### 4. Follow-up burden is accumulating without enough triage help

Evidence from production data:
- Tasks/projects with due dates: `14`
- Tasks/projects with `follow_up_at`: `37`
- Overdue follow-ups: `17`
- By type:
  - project overdue follow-ups: `8`
  - task overdue follow-ups: `22`

Why it matters:
- The product should help shrink this queue, not just display it.

### 5. `Ask` likely lacks good fallback paths for temporal / operational questions

Why it matters:
- If the retrieval path is too narrow, users will stop trusting the assistant even when the data exists elsewhere in the system.

## Cleanup / Maintenance Gaps

### 1. Product copy is ahead of implementation in some places
- `Search or ask…` in Recall is the clearest example.

### 2. Raw/internal affordances are still leaking into the UI
- Example: `Thread ID filter` in Memory.

### 3. Action labels are more expressive than action semantics
- `Snooze`
- `Send reminder`
- potentially other workflow buttons should be audited for "looks smarter than it is"

### 4. Important backend-computed structures are not consistently reflected in the view layer
- This is both a UX gap and a contract-surfacing gap.

## Production Data Insights

Read-only inspection only.

### Active entity counts
- notes: `63`
- tasks: `54`
- resources: `36`
- people: `32`
- projects: `25`
- areas: `18`

### Active entity statuses
- tasks:
  - `open: 33`
  - `done: 15`
  - `in_progress: 4`
  - `cancelled: 2`
- projects:
  - `active: 23`
  - `completed: 2`
- notes:
  - `active: 60`
  - `processed: 3`

### Relationship density
- `parent`: `216`
- `assigned_to`: `157`
- `mentions`: `122`
- `derived_from`: `103`
- `related`: `92`
- `activity_update`: `33`
- `references`: `31`
- `blocks`: `5`

### Event patterns
Top event counts:
- `relationship_added | agent:v4-capture | 478`
- `relationship_added | user | 326`
- `ai_summarized | agent:v4-summarize | 296`
- `tag_added | agent:v4-capture | 264`
- `created | user | 256`
- `updated | user | 204`
- `created | agent:v4-capture | 176`

Interpretation:
- A lot of extraction and enrichment is happening.
- The UI is not yet turning that into clear digest, review, and follow-up value.

### Recent creation bursts
From the most recent roughly two-week window inspected:
- notes:
  - `2026-06-23`: `15`
  - `2026-06-30`: `14`
- tasks:
  - `2026-06-19`: `24`
  - `2026-06-22`: `15`

Interpretation:
- Capture and task creation appear bursty.
- This strengthens the need for good daily review, triage, and distillation surfaces.

## Typical Workflows This Product Should Excel At

These came from the docs, redesign material, live behavior review, and the user’s stated goals.

### 1. All-day capture loop
- Capture thoughts, meeting notes, decisions, follow-ups, blockers, and references quickly
- Let Engram extract entities and relationships automatically
- Make the extracted structure visible enough that the user trusts the system distilled something useful

### 2. Morning / midday `Now` review loop
- Show what is overdue, blocked, waiting, newly important, and likely to slip
- Surface the smallest set of high-value actions first

### 3. Org follow-up loop
- Track active people, projects, dependencies, and quiet delegations
- Make it easy to follow up without losing context

### 4. Thread-centric work loop
- Open a person/project/task thread
- See summary, status, recent changes, linked work, follow-ups, and editable attributes
- Take the next action directly

### 5. Meeting / session prep loop
- Open a person or project thread before a meeting
- See agenda suggestions, recent notes, open questions, risks, decisions, and follow-ups

### 6. Recall / ask-on-demand loop
- Search by keyword when the user knows what they want
- Ask broader questions when they do not
- Provide grounded answers with honest fallback when confidence is low

### 7. Memory / review loop
- Review meaningful changes over time
- Compress noise into digestible updates
- Support end-of-day, weekly, or pre-meeting recall

## Validation Already Performed

### Code and doc review
- Read:
  - `AGENTS.md`
  - `docs/V4_PRINCIPLES.md`
  - `docs/V4_WORLD_MODEL_PLAN.md`
  - `EXECUTION-TRACKER.md`
  - `mcp_server/README_V4.md`
- Also reviewed redesign material in:
  - `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/`
  - including `00-overview.md`, `02-fresh-pass.md`, `04-execution-tracker.md`, `README.md`
- Also reviewed:
  - `docs/V4_UI_UX_DESIGN_GUIDE.md`
  - `docs/iterations/SLICE_2_4_capture-sheet.md`
  - `docs/iterations/SLICE_3_2_ask-endpoint.md`

### Live app / API verification
- Browser-based functional checks on local app
- Verified `Open thread` fix live on task detail route
- Verified backend detail payload for person meeting-prep fields
- Verified `Ask Engram` failure on `What changed today?`
- Verified timeline had current-day events despite the Ask failure

### Data inspection
- Read-only SQL inspection on production DB
- No destructive operations performed

### Validation commands run earlier in session
- `cd ui && npm test`
- `cd ui && npm run build`

## Recommended Next Fixes In Priority Order

### P0
1. Surface meeting/session prep on person and project thread detail
- Render `meeting_prep`, `current_load`, `pulse`, and `dependency_watch`
- Turn backend intelligence into visible prep value

2. Expand `Now` to use the full `/today` contract
- Add blocked, waiting, recent-note, follow-up, and unscheduled-attention views
- Make `Now` the default operational cockpit

3. Fix `Ask Engram` for obvious operational questions
- Add fallback or dedicated handling for recency / timeline questions like:
  - `What changed today?`
  - `What did I miss?`
  - `What moved this week?`

### P1
4. Resolve Recall contract drift
- Either make Recall truly support Ask + Search
- Or rename/re-scope the UI so the behavior is honest

5. Redesign Memory into a digest surface
- Group low-signal events
- Highlight meaningful changes
- Remove raw/internal controls from the default UX

6. Replace opaque follow-up actions with explicit scheduling UX
- `Snooze` and `Send reminder` should expose intent and timing clearly

### P2
7. Improve task anchoring and triage
- Encourage or require clearer parent/owner assignment for open tasks
- Add UI cues for orphaned or unowned work

8. Audit all visible action buttons for truthfulness
- Especially detail and list views
- Confirm every button has a clear effect, reliable state refresh, and correct route target

9. Turn AI distillation into visible payoff
- Better summaries
- stronger "why this matters now"
- clearer relationship/context surfacing

## Suggested Fresh-Session Prompt

Use the prompt below in a new session:

```md
You are doing a fresh, skeptical review and optimization pass on Engram v4.

Repo: /Volumes/lex1t/dev/shared/repos/engram

Read first:
- /Volumes/lex1t/dev/shared/repos/engram/AGENTS.md
- /Volumes/lex1t/dev/shared/repos/engram/docs/V4_PRINCIPLES.md
- /Volumes/lex1t/dev/shared/repos/engram/docs/V4_WORLD_MODEL_PLAN.md
- /Volumes/lex1t/dev/shared/repos/engram/EXECUTION-TRACKER.md
- /Volumes/lex1t/dev/shared/repos/engram/mcp_server/README_V4.md
- /Volumes/lex1t/dev/shared/repos/engram/docs/REVIEW_HANDOFF_2026-07-01.md

Mission:
- Continue from the existing review handoff and do not assume prior passes were complete.
- Treat this as a combined code review, QA pass, workflow audit, and product-optimization review.
- Focus on making Engram a true daily productivity tool for capture, distillation, follow-up, org tracking, recall, and meeting/session prep.

What to do:
1. Re-validate the key findings in the handoff against the current code and live app.
2. Look for any additional real bugs, dead buttons, stale state, route mismatches, broken flows, contract drift, flaky tests, deploy blind spots, or backend/frontend mismatches.
3. Review whether the UI surfaces the most important information and actions for:
   - all-day capture
   - morning/midday review
   - follow-up tracking
   - project/person thread work
   - meeting/session prep
   - recall/ask
   - memory/review
4. Use read-only production-data inspection where helpful to identify real usage patterns, bottlenecks, or neglected entity states.
5. Prefer evidence over speculation. Reproduce issues carefully where possible.

Important safety rules:
- Production DB exists at localhost:5432/engram and contains real data
- Never run destructive commands against prod
- Tests must use TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test
- Run backend pytest commands serially, not in parallel
- `psql` is not on PATH; use `/opt/homebrew/opt/libpq/bin/psql`

Known context from prior work:
- Earlier fixes were already implemented, deployed, and live-verified for:
  - `Now` item-vs-thread navigation split
  - direct editing on thread detail
  - truthful thread totals in backend
  - Memory `actor=agent:` filter
  - `Open thread` fallback on task detail
- The biggest remaining gaps are workflow/value gaps, not just broken buttons.
- The backend already computes useful meeting-prep and daily-review structures that the UI under-surfaces.

Priority areas to inspect first:
1. Meeting/session prep surfacing on thread detail
2. `Now` coverage vs `/api/v4/today`
3. `Ask Engram` handling of operational/time-based questions
4. Recall search-vs-ask contract drift
5. Memory signal-to-noise and digest quality
6. Follow-up action semantics (`Snooze`, `Send reminder`, etc.)
7. Task anchoring quality and orphaned/unowned work
8. Any UI controls that look wired but are not truly functional

Please produce:
1. Findings first, ordered by severity
   - separate:
     - confirmed bugs
     - likely risks
     - cleanup / maintenance gaps
2. Open questions / assumptions
3. Validation performed
4. Recommended next fixes in priority order
5. If useful, propose specific workflow improvements tied to the actual code and data

Do not make code changes unless explicitly asked.
```

## Current Worktree Note

The repo currently has local modifications in these files, so a fresh session should inspect before editing:
- `api/v4_entities.py`
- `tests/integration/test_v4_threads.py`
- `tests/integration/test_v4_timeline.py`
- `ui/src/styles/v5.module.css`
- `ui/src/views/V5Memory.test.jsx`
- `ui/src/views/V5Now.jsx`
- `ui/src/views/V5Now.test.jsx`
- `ui/src/views/V5ThreadDetail.jsx`
- `ui/src/views/V5ThreadDetail.test.jsx`
- `ui/src/views/V5Threads.jsx`
- `ui/src/views/V5Threads.test.jsx`
- `ui/src/views/v5ThreadDetailUtils.js`

