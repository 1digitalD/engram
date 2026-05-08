# AGENTS.md - Engram

## Project purpose
Engram is Dan's Highspot/work-management and second-brain system for capture, search, project/task context, and durable work updates.

## Working rules
- Keep changes scoped to the active tracker task.
- Do not touch unrelated files or the dirty root worktree.
- Prefer this clean worktree for autonomous implementation: `/Volumes/lex1t/dev/shared/repos/engram/.claude/worktrees/reverent-knuth-45dc53`.
- A task is done only when the relevant validation passes.
- Update `EXECUTION-TRACKER.md` after each completed or blocked task.
- Commit logical, reviewable units.
- Preserve worktree state on failure; do not cleanup failed work without review.

## Validation
- Backend targeted: `source .venv/bin/activate && PYTHONPATH=. pytest -q tests/test_phase1_backend_foundation.py tests/test_models.py tests/test_api.py`
- Frontend: `cd ui && npm install && npm run build`
- For UI-only slices, frontend build is the primary gate; rerun backend targeted tests when API/model/store semantics are touched.

## Conventions
- Backend uses Flask/SQLAlchemy with repo-specific migration scripts, not Alembic.
- Frontend uses React/Vite and Zustand store under `ui/src/stores/useStore.js`.
- Existing Batch 1 and Batch 2 commits are the foundation for remaining Phase 1 work.

## Gotchas
- Root repo branch `ui-ux-parallel-implementation` is dirty and not a safe autonomous target unless explicitly reconciled.
- This worktree has an untracked `.venv/`; leave it alone and do not commit it.
- Full `requirements.txt` install previously failed on unavailable `fastmcp`; the local `.venv` contains the subset needed for targeted backend tests.
- `ui/node_modules` is not tracked, so frontend validation may require `npm install` before `npm run build`.

## Recent learnings
- Batch 1 validation command passed with 24 tests after adding schema/API coverage.
- Batch 2 frontend build was green after npm install.
