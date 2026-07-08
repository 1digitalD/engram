## Review: v6-21-workboard-surface

**Verdict:** APPROVE

**Pass 1 — Spec conformance:** PASS
- Notes: The slice adds the `/next/workboard` surface, wires the route and nav entry, calls the v4 `/workboard` client method, renders state-chip counts, and supports space/person regrouping in [WorkboardSurface.jsx](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-21-code-review-codex-a070-codex/ui/src/next/WorkboardSurface.jsx:6), [NextApp.jsx](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-21-code-review-codex-a070-codex/ui/src/next/NextApp.jsx:1), [NextShell.jsx](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-21-code-review-codex-a070-codex/ui/src/next/NextShell.jsx:7), and [v4Client.js](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-21-code-review-codex-a070-codex/ui/src/api/v4Client.js:150). Component coverage exercises initial load, chip counts, and group/filter refetch behavior in [WorkboardSurface.test.jsx](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-21-code-review-codex-a070-codex/ui/src/next/WorkboardSurface.test.jsx:167). The inline actions and themes rail remain explicit placeholders, matching the task scope instead of silently implementing later-phase behavior.

**Pass 2 — PREAMBLE conformance:** PASS
- Notes: The change is surgical: one new surface, one stylesheet, one test file, minimal route/client wiring, and a narrow review-test stabilization. No compatibility adapters, speculative abstractions, or unrelated cleanup were introduced. The placeholder actions stay presentational and do not overreach into mutation flows that belong to later slices.

**Pass 3 — Skill conformance (tdd, incremental-implementation, git-workflow):** PASS
- Notes: The diff includes focused component tests for the requested behaviors in [WorkboardSurface.test.jsx](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-21-code-review-codex-a070-codex/ui/src/next/WorkboardSurface.test.jsx:167). The supporting fix in [ReviewSurface.test.jsx](/Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-21-code-review-codex-a070-codex/ui/src/next/ReviewSurface.test.jsx:244) stabilizes an existing timing-sensitive test without weakening assertions. Commit history stays slice-shaped: one implementation commit plus one PRD bookkeeping commit, both tagged to `v6-21-workboard-surface`.

**Pass 4 — Adversarial read:** PASS
- Findings: No blocking issues found. The component resets error/loading state before each fetch, preserves filter selections across regrouping intentionally, tolerates missing due dates and empty groups, and keeps risky actions as non-mutating announcements instead of fake writes. The review-test change waits for the second report detail fetch before advancing the mocked clock, which addresses the race directly rather than papering over it.

**Pass 5 — Verification reproduction:** PASS
- Commands run: `cd /Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-21-code-review-codex-a070-codex/ui && npm test -- next`; `cd /Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-21-code-review-codex-a070-codex/ui && npm run build`; `cd /Volumes/lex1t/dev/shared/repos/.engram-codloop-worktrees/v6-21-code-review-codex-a070-codex && bash scripts/v6_check_review_verdict.sh v6-21-workboard-surface`
- Result: `npm test -- next` passed with 20/20 tests, including `WorkboardSurface.test.jsx` and the stabilized `ReviewSurface.test.jsx`. `npm run build` passed. The repo-requested main-repo UI commands could not run in this sandbox because Vite writes temp config files under the read-only main-repo `ui/node_modules`; the worktree-local runs exercised the same code with a writable symlinked dependency tree, per repo worktree guidance.

**Fixes applied in review:** none

**Required changes before merge:** none

**Optional suggestions (non-blocking):** none
