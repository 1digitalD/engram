# Activity Update v2 — V5 Entity-Scoped Updates

Date: 2026-07-02 (revised 2026-07-02)
Status: **active**
Owner: Engram
Companion plan: `docs/iterations/ACTIVITY_UPDATE_V2_IMPLEMENTATION_PLAN.md`

## Summary

V5 has a global capture sheet that can attach to the current thread, but it does not restore entity-scoped **Add update**. The activity-update API is directionally correct yet not V5-ready without hardening around provenance, indexing, summarization, suggestions, and UI semantics.

**Target:** a V5-native **Add update** path on entity detail pages, backed by a consolidated activity-update service. Generic capture stays broad capture; entity updates are an explicit operation.

## Loopsmith delivery model

Work ships as thin, independently testable slices (`SLICE_AU0` … `SLICE_AU7`). Each slice doc follows the repo Loopsmith pattern:

- smallest coherent change that proves the behavior;
- inspect current code before editing;
- preserve contracts unless the slice explicitly changes them;
- tests in the same slice as behavior changes;
- narrow validator first, then broader suites;
- slice is not done until implementation, tests, and verification evidence agree.

Active slice docs live in `docs/iterations/SLICE_AU*.md`. Continuity updates go to `EXECUTION-TRACKER.md`.

## Implementation status (2026-07-02 review)

| Area | Status |
|---|---|
| Backend CRUD (note, link, event) | Done (pre-v2) |
| Entity detail `activity_updates` section payload | Done (API only) |
| Capture `progress_update` → activity update | Done (pre-v2) |
| MCP `append_activity_update` | Done (pre-v2) |
| Slice AU0 characterization tests | **Done** |
| Direct update embed + summary queue | **Done** |
| Provenance + timeline hygiene | **Done** |
| Trust policy (suggestions, follow-up) | **Done** |
| V5 AddUpdateComposer | **Done** |
| V5 Activity section | **Done** |
| Capture attachment cleanup | **Done** (AU6) |
| Pagination / near-duplicate | **Done** (AU7) |

## V5 goals this must preserve

- Thread detail is a focused narrative surface, not a legacy bucketed editor.
- Capture remains broad and honest; uncertain work stays reviewable.
- Timeline is episodic provenance, not raw bookkeeping.
- Entity pages should make current state, activity, next actions, and related context understandable at a glance.
- Noise reduction beats clever automation: no surprise tasks, hidden follow-ups, or unexplained mutations.
- Trust requires provenance: updates are searchable, citeable, and linked to what they updated.

## Verified current-state findings

### V5 UI

- `V5ThreadDetail.jsx` FAB calls `openCapture()` (`aria-label="Capture"`).
- `CaptureContext` derives default thread attachment from entity routes.
- `V5CaptureSheet` sends `thread_id` in the capture body and best-effort creates a `related` link post-capture.
- V5 does **not** call `v4API.activityUpdates.create` or render an Activity section.

### Backend capture

- `POST /api/v4/capture` passes `thread_id` into extraction and reconciliation as context bias; it still does not create activity updates.
- Attached generic capture ≠ entity update.

### Backend activity update (direct POST)

- `GET/POST /api/v4/entities/<id>/activity_updates` exist.
- `_create_activity_update_note` creates `source="activity_update"` note + `activity_update` link + `activity_update_added` event.
- Also writes a bookkeeping `updated` event when bumping `updated_at` (timeline noise).
- Direct POST runs lightweight extraction (follow-up dates, tasks, delegation cadence).
- High-confidence tasks (`>= 0.8`) still auto-create; tasks without explicit dates get a 2-business-day follow-up.
- Direct POST does **not** queue embed for the update note or summary refresh for the target.
- Direct POST does **not** set `source_note_id` on `activity_update_added` (capture path does).

### Entity detail API

- Project/task/area detail includes `activity_updates` section via `_fetch_activity_updates`.

## Problems to fix (ordered by trust impact)

1. **No V5 Add update path** — users must use misleading generic capture.
2. **Weak downstream processing** — direct updates may not embed or refresh summaries.
3. **Over-eager automation** — auto tasks and silent follow-up churn conflict with V5 noise reduction.
4. **Provenance gaps** — `source_note_id` missing on direct events; bookkeeping `updated` events narrate.
5. **Generic capture ambiguity** — attachment looks context-aware but is not an update.
6. **Long-term caps** — max-30 409 and exact-only dedup (deferred after core path works).

## Target product behavior

On project/task/area detail:

1. Explicit **Add update** affordance (not generic capture).
2. Entity context visible and locked: `Updating: HITL Pilot`.
3. Save creates activity-update note linked to that entity.
4. Update appears in **Activity** section and timeline provenance.
5. Safe explicit changes may auto-apply; new/uncertain work becomes suggestions.
6. Update is indexed and citeable after background processing.
7. Entity summary/pulse eventually reflects the update.
8. Generic capture remains available elsewhere, not as the primary update path.

## Target backend behavior

One activity-update service path used by:

- V5 Add update UI;
- MCP `append_activity_update`;
- capture reconciliation `progress_update`.

Normalized result shape (introduced incrementally; POST stays backward compatible until clients adopt new fields):

```json
{
  "update_note": { "id": "...", "type": "note", "source": "activity_update" },
  "target": { "id": "...", "type": "project" },
  "applied_changes": [],
  "suggestions": [],
  "events": [],
  "warnings": [],
  "processing": {
    "embedding_queued": true,
    "summary_queued": true
  }
}
```

### Mutation policy

**Auto-apply when explicit and low-risk:**

- create update note and `activity_update` relationship;
- record timeline/provenance events;
- apply explicit follow-up dates;
- delegation cadence refresh (existing rules, tested);
- explicit status changes only when confidently parsed and allowed by entity type (later slice).

**Prefer suggestions for:**

- new tasks;
- inferred status/priority changes;
- inferred follow-up without explicit language;
- relationship creation beyond the update target.

### Follow-up policy

- Explicit follow-up dates: auto-apply.
- Delegated task cadence: preserve.
- Generic task progress note with no explicit date: do **not** silently set follow-up.

### Provenance policy

- Direct update note is `source_note_id` for its own `activity_update_added` event.
- Capture-derived updates preserve both source capture note and generated activity-update note.
- Bookkeeping `updated_at` events should not narrate in timeline.

## Target frontend behavior

### AddUpdateComposer

- Compact composer on `V5ThreadDetail` (after Summary or before Timeline).
- Entity context pill; type-tuned placeholder.
- Submit via `v4API.activityUpdates.create(entity.id, content)`.
- On success: clear draft, reload detail/events/canonical, refresh summary counts, show applied/suggested counts if returned.

### Activity section

- Render `detail.sections` where `key === "activity_updates"`.
- Latest first; content, timestamp, optional effect chips, link to source note.
- Timeline stays provenance; Activity is the human-readable progress log.

### Generic capture

- Attached capture = context/relationship, not update (cleanup slice after Add update ships).

## Scope for first milestone (Slices AU0–AU5)

1. AU0 — Characterization and policy lock (tests only).
2. AU1 — Embed + summary queue on direct POST.
3. AU2 — Provenance (`source_note_id`, suppress bookkeeping narration).
4. AU3 — Trust policy hardening (tasks → suggestions, no silent follow-up).
5. AU4 — V5 AddUpdateComposer.
6. AU5 — V5 Activity section.

**Deferred:** AU6 capture attachment cleanup, AU7 cap/pagination/near-duplicate.

## Open questions (defaults for v2)

| Question | Default |
|---|---|
| Entity types with Add update? | project, task, area only (matches API sections) |
| Explicit status parsing in v2? | No — save + provenance + indexing + suggestions first |
| Update #31 behavior? | Fix after core path; remove dead-end 409 before broad rollout |
| Capture `thread_id` as extraction bias? | **AU8** — bias extraction/reconciliation; no auto activity updates |

## Non-goals (first milestone)

- Full generic capture redesign.
- Multimodal updates, command bar, full historical rollup.
- Automatic status inference beyond explicit tested cases.

## Success criteria

- [x] Entity detail has Add update that does not use generic capture.
- [x] Save creates `activity_update` note and relationship.
- [x] Update appears in Activity and timeline.
- [x] Update is searchable/citeable after background processing (embed + summarize queued).
- [x] New tasks from updates go to review unless policy permits.
- [x] No silent follow-up churn from ordinary progress notes.
- [x] Existing capture and review tests still pass (spot-checked; run full suite before deploy).
