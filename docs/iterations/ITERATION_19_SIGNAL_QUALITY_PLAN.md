# Iteration 19 — Signal Quality & Capture Intelligence — Implementation Plan

Date: 2026-07-02
Status: **complete** (2026-07-03)
Owner: Engram
Predecessor: Iteration 18 (V5 Productivity & Trust Loop, complete)

## Why this iteration

Iteration 18 fixed the *visibility* of the loop (outcomes, review sheet, honest labels).
Production data shows the *intelligence* of the loop is where trust breaks:

| Evidence (live DB, 2026-07-02) | Number |
|---|---|
| Agent-created tasks later deleted by user | 69 of 111 (~65%) |
| Suggestion acceptance rate (all time) | 20 accepted / 62 dismissed (~24%) |
| `create_project` suggestions accepted | 0 of 10 |
| Avg confidence of deleted vs surviving auto-created tasks | 0.94 vs 0.95 (not predictive) |
| Entities created per capture note | avg 5.1, max 22 |
| Duplicate person entities (Priya ×3, Akash/Lexi ×2) | all hand-deleted |
| User-initiated merges / relationship removals | 33 / 50 |

Trace-level failures (real captures, 2026-07-02):

- *"…We can close this task now."* → suggested **create_task "Close this task"** (dismissed),
  recorded a spurious decision, closed nothing. Intent was classified `update` and then ignored.
- *"Pending until next week… no decision on the policies yet."* → suggested
  create_task "Decide on policies" (dismissed) instead of follow_up_at + waiting.

Root causes, in order of leverage:

1. **Intent-blind routing** — intent classification works, then every note runs the same
   exhaustive entity-extraction machinery regardless.
2. **Model misallocation** — reconciliation (the highest-judgment step: new/update/link/skip/
   progress_update) and decision extraction default to `gpt-5.4-nano`; extraction gets `-mini`.
   Nano demonstrably ignores its own conservative prompt rules (decision misfire above).
3. **Recall-over-precision prompts** — "prefer over-extraction", "when in doubt split",
   reconciler forbidden from demoting task candidates; no "is this MY action?" test.
4. **Broken explicit-linking affordance** — V5 capture sheet and Add update composer are plain
   `<textarea>`s; the @/[[ mention picker only exists on the entity content-body editor.
   Backend `_apply_explicit_mentions` still works — the UI lost the entry points.
5. **Dismissals don't teach** — suggestion dedup memory is exact-SHA1 fingerprint; any
   rewording re-proposes the same real-world item.
6. **Two capture paths with different intelligence** — thread-attached capture silently drops
   `progress_update` decisions (`api/v4_entities.py:3931`); only Add update changes state.

## Non-goals

- No new surfaces or features (no weekly review, no uploads, no next-best-action).
- No schema migrations (one additive column allowed for dismissal reasons if needed —
  prefer `payload`/`properties`).
- No re-ranking of Now/brief.

## Milestones

| Milestone | Slices | Ship criteria |
|-----------|--------|---------------|
| **M0 — Model reallocation** | SQ-00 | Reconciliation/decisions/AU-extraction on `-mini`-class; measured before/after on golden set |
| **M1 — Broken trust primitives** | SQ-01, SQ-02, SQ-03, SQ-04 | Mentions work in both composers; follow-up routing honest; no spurious decisions |
| **M2 — Route by intent** | SQ-05, SQ-06 | Update-intent captures act like activity updates; thread-attached capture applies progress |
| **M3 — Precision extraction** | SQ-07, SQ-08, SQ-09 | Meeting-note task noise cut; person dupes stop; confidence retired as sole gate |
| **M4 — Learning loop** | SQ-10, SQ-11 | Reworded duplicates suppressed; dismissal reasons captured |

Recommended order: M0 (minutes) → M1 → M2 → M3 → M4.
M2 is the behavior change that fixes the user's dominant daily pattern; M1 restores
already-promised behavior and should ship first.

---

## Slice specifications

### SQ-00 — Model reallocation (M0)

**Problem:** `resolve_chat_model` defaults everything to `gpt-5.4-nano`. Only extraction is
overridden to `-mini` in `.env`. Reconciliation — the step deciding new/update/link/skip/
progress_update with a ~2k-token rulebook — runs on nano, as do decision extraction, brief,
and activity-update extraction. Nano provably violates prompt rules (extracted "We can close
this task now" as a 0.90-confidence decision despite the prompt requiring named actor + date).

**Change:**
- `.env`: set `OPENAI_RECONCILIATION_MODEL=gpt-5.4-mini`, `OPENAI_DECISION_MODEL=gpt-5.4-mini`,
  `OPENAI_ACTIVITY_UPDATE_MODEL=gpt-5.4-mini`, `OPENAI_BRIEF_MODEL=gpt-5.4-mini`.
- Consider flipping the hardcoded default in `services/llm_models.py` to `-mini` and using
  nano only where explicitly configured (summarization, narration, title).
- Volume is ~5–10 captures/day; cost delta is negligible vs. trust cost of wrong decisions.

**Acceptance:**
- [ ] Golden-set eval (SQ-03 harness or a fixture set of ~15 real anonymized captures) shows
      reconciliation decisions unchanged-or-better; decision extraction no longer fires on
      closure language.

**Validation:** `TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/integration -q -k "reconcil or decision or activity"`

---

### SQ-01 — Restore @/[[ mentions in capture + Add update (M1)

**Problem:** `V5CaptureSheet.jsx:281` and `AddUpdateComposer` (`V5ThreadDetail.jsx:365`) are
plain textareas. `createMentionExtension` + `MentionList` + backend resolution
(`_apply_explicit_mentions`, confidence 1.0, no LLM) all still exist; only the content-body
editor uses them. Explicit linking — the single most reliable primitive — is unreachable
from the two inputs users actually type into.

**Change:** Swap both textareas for `MarkdownEditor` (or a slim mention-enabled variant if
the full toolbar is unwanted in a sheet). Preserve submit-on-Cmd/Ctrl-Enter, placeholder,
and draft state. Ensure output is markdown text (mention links `[Title](/tasks/<id>)`)
passed unchanged to `capture`/`activity_updates.create`.

**Acceptance:**
- [ ] Typing `@` in capture sheet opens person picker; `[[` opens entity picker
- [ ] Same in Add update composer
- [ ] Submitting content with a mention creates a `mentions` relationship with confidence 1.0
      (integration test exists — extend to activity-update path if missing)
- [ ] `cd ui && npm test -- V5CaptureSheet V5ThreadDetail` passes

**Validation:**
```bash
cd ui && npm test -- V5CaptureSheet V5ThreadDetail && npm run build
```

---

### SQ-02 — Fix follow-up routing override (M1)

**Problem:** `create_activity_update` re-routes a top-level `follow_up_at` onto task
suggestions whenever *any* task candidate exists (`route_follow_up_to_tasks`), overriding the
extractor's own routing decision. "Waiting on Priya's review — follow up Friday. Also need to
update docs." → Friday lands on the docs task; target gets nothing.

**Change:** Trust the extractor's placement. Only suppress target follow-up when extracted
status is `done`/`cancelled` (the closure case the prompt already handles). Remove the
"any task candidates exist" condition.

**Acceptance:**
- [ ] Open task + top-level follow-up + unrelated new task → follow-up applied to target
- [ ] Closure + spin-off scenario (AU11 test) still passes unchanged
- [ ] `follow_up_auto_set` in the response reflects what actually happened
      (currently hardcoded `False` — also fix here, it's the same response block)

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/integration/test_v4_activity_updates.py -q
```

---

### SQ-03 — Golden capture eval harness (M1, enables everything after)

**Problem:** Every prompt/model change so far has shipped without a fixed measure of
extraction quality; noise regressions were discovered by the user deleting entities.

**Change:** A pytest-marked (skipped-by-default, `ENGRAM_ALLOW_TEST_AI=1` to run) eval:
~15–20 fixture captures drawn from real usage (anonymized): meeting transcript, short status
update with deictic reference, delegation, junk, link-share, leader-direction blurb. Each has
expected outcomes (entities created/suggested, target statuses, follow-ups). Script prints
precision/recall per capture and a summary table. Not a CI gate — a decision tool.

**Acceptance:**
- [ ] `ENGRAM_ALLOW_TEST_AI=1 pytest tests/eval/test_capture_golden.py -q` runs against
      live OpenAI and reports per-fixture pass/fail
- [ ] Documented in the slice doc how to add fixtures

---

### SQ-04 — Decision extraction guardrail (M1)

**Problem:** Decisions fire on routine closure language. Prompt is correct; model isn't
(see SQ-00). Belt-and-braces regardless of model.

**Change:** Post-hoc structural validation in `_normalize_decisions` / suggestion creation:
reject statements that lack BOTH a named actor (capitalized name or "I/Dan") and a concrete
deliverable/date; reject statements matching closure patterns (`close|done|finished|wrap up`
against the update target). Keep decisions suggest-only (already true).

**Acceptance:**
- [ ] "We can close this task now." produces no decision suggestion
- [ ] "Dan will deliver the wireframes by 2026-07-15." still produces one

---

### SQ-05 — Intent-routed capture pipeline (M2) — **the core slice**

**Problem:** Intent (`update`/`follow_up`/`task_signal`/…) is classified and stored, then the
same exhaustive extraction runs for all intents. Status updates about existing work — the
user's dominant capture type (27 of 49 classified notes) — get treated as raw material for
new entities.

**Change:** In `_run_capture_extraction` (or immediately after basic extraction returns
intent), branch:

- **`update` / `follow_up` intent (high confidence):** run
  `extract_dates_and_tasks_from_update` against a *resolved target* instead of full
  reconciliation. Target resolution ladder:
  1. thread attachment (capture sheet attachment)
  2. explicit mention in content
  3. embedding search of content against recent active tasks/projects
     (reuse `_enrich_candidates` machinery); accept only above a high threshold
  4. unresolved → keep the note, emit ONE suggestion: "This looks like an update —
     which thread is it about?" (an `update_unresolved` suggestion type the review
     sheet renders with a thread picker)
  Then apply the existing AU10/AU11 policy (auto-apply status ≥ threshold, else suggestion).
- **`junk`:** stop after note creation (already effectively true — make it explicit, skip
  LLM reconciliation spend).
- **`task_signal` / `note` / `reference` / long content (> ~1200 chars):** current full
  extraction path.

**Acceptance:**
- [ ] Fixture: "Had 3 sessions… We can close this task now." attached to a task →
      task status `done` (or update_task suggestion), NO create_task suggestion
- [ ] Same text unattached, content names the task ("the coaching pilot") →
      resolved via embedding search, same outcome
- [ ] Same text unattached and unresolvable → single `update_unresolved` suggestion
- [ ] Meeting-transcript fixture still produces entity/link candidates (full path intact)
- [ ] Golden eval (SQ-03) shows no regression on non-update fixtures

**Validation:**
```bash
TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test ./venv/bin/pytest tests/integration/test_v4_capture.py tests/integration/test_v4_activity_updates.py -q
```

---

### SQ-06 — Unify thread-attached capture with Add update (M2)

**Problem:** `api/v4_entities.py:3931` silently drops `progress_update` decisions when
capture is thread-attached — not even a suggestion. Two text boxes on an entity page have
different intelligence; the capture sheet's hint text ("not an activity update") is a
band-aid.

**Change:** With SQ-05 in place, a thread-attached capture whose intent is `update`/
`follow_up` routes through the activity-update path with the attachment as target (delete
the early return). Non-update intents keep current behavior (note + links). Remove/soften
`CAPTURE_ATTACHMENT_HINT` copy accordingly.

**Acceptance:**
- [ ] Capture "shipped it, done" attached to a task → status applied or suggested,
      identical to Add update with the same text
- [ ] Attached capture of a reference/note intent → unchanged current behavior
- [ ] AU8 regression tests updated deliberately (this supersedes the AU8 non-goal)

---

### SQ-07 — Precision task extraction (M3)

**Problem:** Prompt optimizes recall ("be exhaustive", "when in doubt split"); reconciler
forbidden from demoting tasks; tentative filter is prefix-only. Result: discussion fragments
("Endorse L2 priority", "Name L3 defer on slide 5"), other people's calendar items, and
meeting logistics become task candidates. Confidence doesn't separate keepers from noise.

**Change (prompt + gate together):**
- Extraction prompt: replace "prefer over-extraction / when in doubt split" for TASKS with:
  a task candidate requires (a) a concrete deliverable or next action, AND (b) an owner that
  is the user or someone the user must chase. Explicitly exclude: meeting logistics
  (attend/schedule/hold), stance fragments (endorse/agree/defer/revisit), and restatements of
  discussion positions. Add negative examples from the real deleted set.
- Structural gate in `_apply_capture_decision`: replace confidence-only auto/suggest split
  for tasks with checklist scoring — has owner? has deliverable-shaped title (verb + object)?
  has date? target resolvable? Confidence becomes tiebreaker only.
- Meeting notes (long content): cap task suggestions per note (e.g. 8) and mark them as one
  group (`payload.group_id` = note id) so the review sheet can render "N action items from
  this note" with accept-all / per-row controls (UI part is small: group by `group_id` in
  `V5ReviewSheet`).

**Acceptance:**
- [ ] Golden meeting fixture: stance fragments and logistics no longer proposed;
      real action items still are (precision up, recall on true tasks held)
- [ ] Review sheet renders grouped meeting suggestions with accept-all
- [ ] Dismissal rate measurable via SQ-11 data going forward

---

### SQ-08 — Person hygiene (M3)

**Problem:** Person entities auto-create at ≥0.85 (`person` ∉ `SUGGEST_ONLY_CREATION_TYPES`);
exact-title dedup only → Priya ×3, Akash ×2, all hand-deleted. Every name in a transcript
becomes a person.

**Change:**
- Dedup: before creating a person, fuzzy/first-name match against existing active people
  ("Priya" ↔ "Priya <lastname>"); on match, link instead of create.
- Creation policy: only auto-create a person who carries work in the same note (assignee,
  delegation, follow-up owner); bare mentions become `link` if existing or are dropped.
  (Alternative if too aggressive: add `person` to `SUGGEST_ONLY_CREATION_TYPES`.)

**Acceptance:**
- [ ] Transcript fixture with 6 names, 2 assignees → ≤2 person creations, others linked/skipped
- [ ] "Priya" in a note with existing "Priya Dhandapani" links, doesn't create

---

### SQ-09 — Retire confidence as the primary gate (M3)

**Problem:** Deleted tasks avg confidence 0.94 vs 0.95 surviving — the 0.85 thresholds
(`AUTO_APPLY_CONFIDENCE`, `AUTO_CREATE_ENTITY_CONFIDENCE`) filter almost nothing because the
extractor is instructed to be exhaustive and rates its own output high.

**Change:** Mostly lands inside SQ-05/SQ-07; this slice is the audit + cleanup: every
`confidence >=` gate in `api/v4_entities.py` either (a) gains a structural precondition, or
(b) is documented as tiebreaker-only. Reconciliation prompt updated to stop asking for
self-graded confidence where it isn't used.

---

### SQ-10 — Semantic dismissal memory (M4)

**Problem:** `_suggestion_fingerprint` is exact SHA1; "Follow up with Henry" dismissed →
"Follow up with Henry on rollout status" re-proposed. Repeats observed 2–3× per item.

**Change:** In `_recently_resolved_duplicate`, add a semantic layer: embed the candidate
suggestion's normalized title (+ target id for updates); compare against embeddings of
suggestions dismissed in the last 30 days (store embedding on the suggestion row at
dismissal time, or compute lazily and cache in payload). Similarity ≥ ~0.85 with same
suggestion_type → suppress. Keep the exact-fingerprint fast path.

**Acceptance:**
- [ ] Reworded duplicate of a dismissed suggestion within 30 days is not re-created
- [ ] Genuinely different task about the same person still proposed

---

### SQ-11 — Dismissal reasons + honest suggestion copy (M4)

**Change:**
- Review sheet dismiss action offers optional one-tap reason: `not a task` / `not mine` /
  `duplicate` / `wrong target` / `other` → stored on suggestion `payload.dismiss_reason`.
- Replace `UNCERTAIN_SUGGESTION_REASON` ("AI was not sure about this") with the evidence
  quote from the candidate (`evidence` field) so rows are judgeable at a glance.

**Acceptance:**
- [ ] Dismiss with reason persists; GET /suggestions returns it
- [ ] Suggestion rows show evidence quotes when present

---

## Measurement (how we know it worked)

Run before M0 and after each milestone, from the live DB:

```sql
-- acceptance rate, last 14 days
SELECT status, count(*) FROM ai_suggestions
WHERE created_at > now() - interval '14 days' GROUP BY 1;
-- deletion rate of agent-created entities, last 14 days
SELECT e.lifecycle, count(*) FROM entities e
JOIN entity_events ev ON ev.entity_id=e.id AND ev.event_type='created'
 AND ev.actor LIKE 'agent%'
WHERE ev.created_at > now() - interval '14 days' GROUP BY 1;
```

Targets: suggestion acceptance ≥ 60% (from 24%); agent-created deletion rate ≤ 15%
(from 65%); zero unresolved "this task"-style updates silently doing nothing.

## Delivery

Same Loopsmith + LCS pattern as Iteration 18. SQ-05/SQ-06/SQ-07 are medium-risk backend
slices — run one at a time with the golden eval (SQ-03) before/after. M0 is a manual env
change + deploy, no loop needed. Do NOT overwrite `prd.json` until this plan is reviewed;
archive the Iteration 18 overlay first (`docs/iterations/archive/prd-v5-productivity.json`).
