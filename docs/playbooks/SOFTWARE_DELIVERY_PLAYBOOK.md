# Software Delivery Playbook

Purpose: ship high-quality software in small, reviewable increments without getting blocked, losing context, or drifting from the active product/runtime contract.

This playbook is intentionally small. It is a delivery aid, not a second product.

## When To Use This

Use this playbook for feature work, UX improvements, backend changes, refactors, and other iterative software delivery work where continuity and verification matter.

Do not force this playbook onto work that is purely exploratory. For research spikes or architectural probing, keep notes light and convert the result into a normal iteration contract only once the shape of the work becomes clearer.

## Core Rules

1. Follow the repo's governing artifacts first.
2. Work in small vertical slices whenever practical.
3. Keep the active context narrow and relevant to the current slice.
4. Prefer additive, explicit, testable changes.
5. Verify narrowly before broadening.
6. Keep risky writes, destructive actions, and data-shape changes explicit.
7. Preserve continuity in repo artifacts, not chat history.
8. If process overhead stops helping delivery, simplify it.

## Source-Of-Truth Order

Use this priority unless the repo defines a different order:

1. Repo working rules and active principles
2. Active implementation plan / contract docs
3. Current code and tests
4. Live execution tracker / active iteration notes
5. Archived plans or historical artifacts for archaeology only

If these conflict, resolve the conflict before implementing.

## Standard Iteration Loop

1. Lock the slice.
   Define the user problem, affected surfaces, dependencies, acceptance criteria, and non-goals.
2. Read the active code path.
   Trace the route, handler, service, data flow, and tests you are about to touch.
3. Implement the smallest complete change.
   Avoid speculative abstractions and unrelated cleanup.
4. Verify the core path.
   Run focused tests and a manual path through the main user flow.
5. Broaden validation as risk justifies.
   Build, run related suites, and check likely regressions.
6. Record continuity.
   Update the tracker with what changed, what was verified, risks, and the next step.

## Risk Levels

Use the lightest process that still protects quality.

- Low risk:
  Small UI tweaks, copy updates, isolated bug fixes, read-only improvements.
- Medium risk:
  Shared component changes, endpoint behavior changes, new route flows, non-destructive write-path updates.
- High risk:
  Schema changes, destructive commands, auth/permissions changes, data migrations, deployment-sensitive infra changes.

Higher risk means tighter acceptance criteria, stronger verification, and clearer continuity notes.

## Verification Expectations

Always verify the main user or system path you changed.

Prefer this order:

1. Focused tests for touched behavior
2. Manual QA for the critical path
3. Build / compile checks
4. Broader regression coverage when shared behavior changed

If you could not run an expected validation step, record that explicitly.

## Continuity Rules

Continuity should survive:

- rate limits
- session switches
- agent handoffs
- system restarts

To make that true:

- keep slices small
- leave the repo in a legible state
- record the active iteration and next step in the tracker
- prefer explicit acceptance boundaries over vague "in progress" memory

## Escape Hatch

You may deviate from this playbook when speed, ambiguity, or incident pressure requires it. If you do, record:

- what you skipped
- why
- what safeguard replaced the skipped step

## Minimal Artifact Set

This playbook assumes only:

- one general playbook
- one iteration contract template
- one live execution tracker per project

Add more artifacts only when the work proves they are needed.
