# v6 Quality Control Loop

Every v6 Loopsmith slice follows **implement → review → green** before the next
task dispatches. This document is the contract for executors and overseers.

## Per-slice loop

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────┐
│  Implement  │ ──► │  Code review │ ──► │  Validation (green) │
│  (TDD slice)│     │  (5 passes)  │     │  → next task        │
└─────────────┘     └──────────────┘     └─────────────────────┘
```

### 1. Implement task (`kind: code`)

Skills: `tdd`, `incremental-implementation`, `git-workflow`

- One logical change per commit; build stays green after each commit.
- Tests first for new behavior; do not modify existing tests to make them pass
  unless the spec explicitly requires a contract change (Phase 0: zero contract
  changes).
- Run focused `validationCommands` before marking the task complete.

### 2. Review task (`kind: review`)

Skills: `code-review`, `debugging`

Runs immediately after its paired implement task. The reviewer:

1. Inspects `git log -p` for the implement task's commits.
2. Runs all five passes from LCS `code-review/SKILL.md`:
   - **Pass 1** — Spec conformance (every acceptance criterion met)
   - **Pass 2** — PREAMBLE conformance (surgical diff, no drive-by edits)
   - **Pass 3** — Skill conformance (TDD / incremental / git-workflow rules)
   - **Pass 4** — Adversarial read (null handling, error swallowing, naming)
   - **Pass 5** — Verification reproduction (re-run every validation command
     in a clean worktree; do not trust prior executor claims)
3. Fixes **BLOCK** and **REQUEST CHANGES** findings in the same worktree.
4. Records a short review verdict in `validationEvidence` (verdict + any
   fixes applied).
5. Never approves `no_changes` without inspecting worktree commits.

Review tasks do **not** add features. Scope is fix-only for findings from the
paired implement task.

### 3. Validation harness (must be green)

| Command | When |
|---|---|
| `bash scripts/v6_validate_slice.sh` | Every implement + review task |
| `bash scripts/v6_route_table_diff.sh` | V6-01 and any task touching routes |
| Focused pytest from task `validationCommands` | Implement task, before review |
| Full backend suite (serial, port 5433) | Review task + phase gate |
| `cd ui && npm test && npm run build` | Phase gate; any UI-touching slice |

### 4. Phase gate task (`kind: gate`)

Runs after all slice review tasks in a phase pass. Confirms:

- Full backend suite green (serial, `:5433`)
- UI test + build green
- Phase-specific checks (route table, replay eval, etc.)
- `EXECUTION-TRACKER.md` slice log updated

Deploy (backup + `scripts/engram-deploy.sh` + smoke) is overseer-run at phase
boundaries, not inside Loopsmith tasks.

## Overseer responsibilities

- **Policy A:** never edit product code on `main` while a drain attempt is live
  on the same `task-id`.
- Poll: `bash scripts/loopsmith_poll_status.sh`
- Recovery: `bash scripts/loopsmith_recover.sh <repo> inspect`
- On review task failure: pause drain, inspect worktree, cherry-pick or
  reset-state per `loopsmith_recover.sh`.
- After phase gate: deploy + smoke, then stand up the next phase `prd.json`.

## Phase 1 note (continuous build)

Deploy gate 1 metrics (review time, acceptance rate) are **tracked in parallel**,
not calendar-blocking. V6-14 ships instrumentation early; phases 2+ proceed
without a 2-week pause. UC-1 manual pass still required before leaving Phase 1.

## Loopsmith improvements backlog

Track harness friction here; fix between phases:

- [ ] `loopsmith_poll_status.sh` — dynamic iteration name (done Phase 0 kickoff)
- [ ] Route-table baseline fixture + diff script (done Phase 0 kickoff)
- [ ] Review task `kind: review` — confirm Loopsmith dispatches with
      `code-review` skill only (no feature prompts)
- [ ] Post-Phase 0 retro: V6-01 monolith split attempt count, executor used
