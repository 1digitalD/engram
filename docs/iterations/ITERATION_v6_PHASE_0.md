# Iteration v6 Phase 0 — Foundations

Date: 2026-07-07
Status: **active**
Owner: Engram
Design: `docs/v6/SOLUTION_DESIGN.md` §8.1, §4
Plan: `docs/v6/IMPLEMENTATION_PLAN.md` Phase 0
QC: `docs/v6/QC_LOOP.md`

## Objective

Mechanical foundations with **zero behavior change**: split the 7.6k-line
`api/v4_entities.py` monolith into the `api/v4/` package, and add the operator
identity setting. Every later v6 phase touches the API layer — this unblocks
them.

## Quality control

Each slice runs **implement → code review → green** (see `QC_LOOP.md`):

| Task | Type | Skills |
|---|---|---|
| v6-01-api-package-split | implement | tdd, incremental-implementation, git-workflow |
| v6-01-code-review | review | code-review, debugging |
| v6-02-operator-identity | implement | tdd, incremental-implementation, git-workflow |
| v6-02-code-review | review | code-review, debugging |
| v6-phase-0-gate | gate | git-workflow |

Review tasks fix blockers only — no new features.

## Milestones

| Milestone | Tasks | Ship criteria |
|---|---|---|
| **M1 — API package** | v6-01 + review | Route table identical to baseline; full suite green with zero test edits |
| **M2 — Operator setting** | v6-02 + review | GET/PUT `/settings/operator`; backfill from `owner_person_id` |
| **Gate** | v6-phase-0-gate | Full validation harness; tracker updated; ready for Phase 1 prd |

Deploy gate 0 (overseer): backup not required (no migrations), full suites
green, `npm run build`, deploy + smoke.

## Slice specifications

### V6-01 — API package split

Split `api/v4_entities.py` into `api/v4/` per SOLUTION_DESIGN §8.1:

```
api/v4/__init__.py        # blueprint assembly; url_prefix unchanged
api/v4/capture.py
api/v4/reports.py         # empty stub module (routes land in Phase 1)
api/v4/entities.py
api/v4/links.py
api/v4/workboard.py       # empty stub
api/v4/today.py
api/v4/markers.py         # empty stub
api/v4/recall.py
api/v4/insights.py
api/v4/system.py
```

**Rules:**
- Mechanical move only — no route, handler, or response shape changes.
- Shared helpers stay importable; prefer moving with their primary consumer.
- `api/__init__.py` imports from `api.v4` instead of `v4_entities`.
- Delete `api/v4_entities.py` only when empty.
- Incremental commits per module (capture, entities, today, …).
- Stub modules may export nothing until Phase 1 — they exist so new routes
  have a home.

**Verification:**
- `bash scripts/v6_route_table_diff.sh` — must match
  `docs/v6/fixtures/route_table_baseline.txt`
- Full pytest suite with **zero test file edits**

### V6-02 — Operator identity

Add `operator_person_id` to `AppSetting` with endpoints:

- `GET /api/v4/settings/operator` → `{operator_person_id, configured: bool}`
- `PUT /api/v4/settings/operator` → body `{operator_person_id}` (person entity id)

On first GET when `operator_person_id` is unset, backfill from existing
`owner_person_id` if present (do not delete `owner_person_id` — both may
coexist; v6 workboard uses `operator_person_id`).

Place routes in `api/v4/system.py`. Service helper in `services/` if needed.

### Phase 0 gate

- Run `bash scripts/v6_validate_slice.sh` + UI build
- Update `EXECUTION-TRACKER.md` Phase 0 → done
- Archive this iteration's `prd.json` when standing up Phase 1

## Non-goals

- No schema migrations
- No UI changes (`ui/src/next/` starts Phase 1)
- No distillation report work (Phase 1)
- No edits to `ui/src/lab/` or `ui/src/views/`

## Loopsmith commands

```bash
bash scripts/iteration_preflight.sh /Volumes/lex1t/dev/shared/repos/engram

bash /Volumes/lex1t/dev/shared/repos/loopsmith-coding-standards/scripts/loopsmithctl-lcs.sh \
  host-run --repo /Volumes/lex1t/dev/shared/repos/engram --drain

bash scripts/loopsmith_poll_status.sh
```
