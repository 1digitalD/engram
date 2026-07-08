# v6 Quality Control Loop

Every v6 Loopsmith slice follows **implement → review → fix → review → green**
before the next task dispatches. This document is the contract for executors
and overseers.

## Per-slice loop

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  Implement  │ ──► │  Code review │ ──► │ Fix (if any)│ ──► │ Re-review /  │
│  (TDD slice)│     │  (5 passes)  │     │ same task   │     │ APPROVE      │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
                           │                                         │
                           └──────── REQUEST CHANGES / BLOCK ─────────┘
```

A review task is **not complete** when validation passes once. It is complete
when a formal verdict file says `Verdict: APPROVE` after any required fixes
are applied.

### 1. Implement task (`kind: code`)

Skills: `tdd`, `incremental-implementation`, `git-workflow`

- One logical change per commit; build stays green after each commit.
- Tests first for new behavior.
- Run focused `validationCommands` before marking the task complete.

### 2. Review task (`kind: review`)

Skills: `code-review`, `debugging`

Runs immediately after its paired implement task.

1. Inspect `git log -p` for the implement task's commits.
2. Run all five passes from LCS `code-review/SKILL.md`.
3. Write **`docs/v6/reviews/<implement-task-id>.md`** using
   `docs/v6/reviews/TEMPLATE.md`.
4. **If any pass fails on product code:**
   - Fix the issue in the **same worktree** (review task scope: fix-only).
   - Re-run failed passes.
   - Update the verdict file with fixes applied.
   - Do **not** set `passes: true` until `Verdict: APPROVE`.
5. **If scope exceeds one fix slice:** set `blocked: true`, document in verdict,
   overseer splits a follow-up implement task — do not silently approve.
6. Run Pass 5 verification yourself (never trust prior executor claims).
7. Run `bash scripts/v6_check_review_verdict.sh <implement-task-id>` — must exit 0.

**Anti-patterns (Phase 0 retro learned):**
- Re-dispatching review until `validationEvidence` has pytest output but no verdict.
- Marking `passes: true` without `docs/v6/reviews/<id>.md`.
- Review commits that only touch `prd.json` / tracker with zero product review.

### 3. Validation harness (must be green)

| Command | When |
|---|---|
| `bash scripts/v6_validate_slice.sh` | Every implement + review task |
| `bash scripts/v6_check_review_verdict.sh <id>` | Every review task, before `passes: true` |
| `bash scripts/v6_route_table_diff.sh` | Route-touching slices |
| Full backend suite (serial, :5433) | Review task + phase gate |
| `cd ui && npm test && npm run build` | Phase gate; UI slices |

### 4. Phase gate task (`kind: gate`)

After all slice reviews APPROVE:

- Full backend + UI validation
- All `docs/v6/reviews/*.md` for the phase present with APPROVE
- `EXECUTION-TRACKER.md` updated
- Deploy (backup + smoke) is overseer-run, not a Loopsmith task

## Phase 0 retro review (2026-07-08)

Overseer re-ran 5-pass review on V6-01 and V6-02 after Phase 0 Loopsmith drain
marked review tasks `passes: true` without formal verdicts.

| Deliverable | Verdict file | Outcome |
|---|---|---|
| V6-01 API split | `docs/v6/reviews/v6-01-api-package-split.md` | APPROVE + dead import cleanup |
| V6-02 Operator setting | `docs/v6/reviews/v6-02-operator-identity.md` | APPROVE |

## Overseer responsibilities

- **Policy A:** never edit product code on `main` while a drain attempt is live on the same `task-id`.
- Poll: `bash scripts/loopsmith_poll_status.sh`
- Recovery: `bash scripts/loopsmith_recover.sh <repo> inspect`
- After phase gate: deploy + smoke, archive `prd.json`, stand up next phase `prd.json`.

## Phase 1 note (continuous build)

Quality metrics tracked in parallel via V6-14 — not calendar-blocking.

## Loopsmith harness backlog

- [x] Route-table baseline + diff script
- [x] Formal review verdict files + `v6_check_review_verdict.sh`
- [x] Phase 0 retro review completed
- [ ] Post-Phase 1 retro: did review tasks produce verdict files without re-dispatch churn?
