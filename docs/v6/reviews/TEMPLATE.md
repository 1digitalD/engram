# Code Review Verdict Template

Copy this file to `docs/v6/reviews/<implement-task-id>.md` and fill in every
section. A review task must **not** set `passes: true` until `Verdict: APPROVE`.

```markdown
## Review: <implement-task-id>

**Verdict:** APPROVE | REQUEST CHANGES | BLOCK

**Pass 1 — Spec conformance:** PASS | FAIL — Notes: ...

**Pass 2 — PREAMBLE conformance:** PASS | FAIL — Notes: ...

**Pass 3 — Skill conformance:** PASS | FAIL — Notes: ...

**Pass 4 — Adversarial read:** PASS | FAIL — Findings: ...

**Pass 5 — Verification reproduction:** PASS | FAIL — Commands run: ... Result: ...

**Fixes applied in this review:** (none | list commits/changes)

**Required changes before merge:** (none | numbered list)

**Optional suggestions (non-blocking):** ...
```

Validation: `bash scripts/v6_check_review_verdict.sh <implement-task-id>`
