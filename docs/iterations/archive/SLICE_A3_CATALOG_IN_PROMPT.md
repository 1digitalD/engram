# Slice A3 — Full Project/Area Catalog in Reconciler Prompt

Phase: A — Reconciliation matching
Status: COMPLETE

## Goal

Give the reconciler model explicit visibility into the full workspace catalog
(all active projects and areas) so it can match paraphrased or abbreviated
project names without relying solely on embedding similarity.

This is the final slice of Phase A. Together with A1 (batch embeddings) and
A2 (richer match documents), it closes the 9 labeled false-creates from the
replay fixture set.

## Changes

### `services/v4_reconciliation.py`

- `CATALOG_CHAR_CAP = 8000` (≈ 2000 tokens cap).
- `_build_catalog_block()`: queries all active projects and areas ordered by
  `updated_at desc`; formats as `[type] title — content_preview`; truncates
  at cap by recency. Returns `""` when empty (no crash).
- `SYSTEM_PROMPT`: added `{catalog_block}` placeholder and updated MATCHING
  RULES to instruct model to always check catalog before deciding "new" for
  a project/area; paraphrase examples added.
- `_call_model`: builds catalog block and passes it into the formatted prompt.

## Tests

`tests/unit/test_slice_a3_catalog_in_prompt.py` — 11 tests:
- `TestBuildCatalogBlock` (8): string return, projects+areas included, tasks/persons
  excluded, content preview included, empty catalog, deleted excluded, token cap,
  format has type+title
- `TestCatalogInPrompt` (3): catalog appears in system prompt content, empty catalog
  handled gracefully, heuristic fallback unchanged

## Expected replay eval impact (with OPENAI_API_KEY)

The catalog block gives the model direct access to all 48 projects/areas.
Expected to fix:
- "Agent Platform" → link area "Agent Platform" (exact title in catalog)
- "Toolkit robustness and flexibility" → link (exact title in catalog)
- "Agentic SDLC" → link (exact title in catalog)
- "Deals agent family support" → link "GTM agent family support" (paraphrase note)
- "Admin agent family support" → link "GTM agent family support"
- "Security roadmap" → link "Agent Security" (catalog entry visible)
- "Agent memory utilization" → link "Agent Memory / Canonical Memory"
- "Agent memories collaboration" → link "Agent Memory / Canonical Memory"
- "Conversation history search functionality" → link "Agent Memory / Conversation History"

Target: ≥ 85% accuracy on labeled set (up from offline baseline of 51%).
Live eval to be run with OPENAI_API_KEY set.

## Live eval results (2026-06-09)

File: `docs/iterations/replay_results/20260609_235658.json`
Score: 19/27 (70%) — up from 51% offline baseline, but below the 85% target.

7 of the 9 original false-create labels from A0 are now fixed: "Toolkit
robustness and flexibility", "Deals agent family support", "Admin agent
family support", "Agent memory utilization", "Agentic SDLC", "Conversation
history search functionality", "Agent memories collaboration", "Agent
Platform".

New regression: the catalog made the model **over-eager to link to broad
umbrella areas**. 8 incorrect decisions:
- "Security roadmap" still wrong (now `new ≠ link`, inverted from before —
  candidate "Security" treated as project but only an area match exists)
- "SWAT team operating model", "Conversation reinforcement learning",
  "Merger contingency planning", "Design team grounding in customer
  scenarios" — all incorrectly linked to umbrella area "Agent Platform"
  (`link ≠ new`)
- "Platform Evangelism / Adoption" — linked to itself incorrectly (`link ≠
  new`)
- "reasoning UI" — incorrectly linked to person "Sushmidha Jawahar"
  (`link ≠ new`)
- "Attend sprint planning" — `update ≠ new` against "Hold sprint planning"

This is the seed for a Phase B slice: tighten the matching rules so broad
umbrella areas (e.g. "Agent Platform") are only linked on close title/scope
match, not whenever a candidate is thematically related.

## Phase A complete — deploy checkpoint

All three matching slices (A1, A2, A3) are merged. This is a Phase A deploy
boundary per the implementation plan.

Deploy protocol:
1. `bash scripts/backup_prod.sh` — snapshot before deploy
2. No schema migrations for Phase A (no DB changes)
3. `./scripts/engram-deploy.sh`
4. Smoke test: `GET /api/v4/health`, `GET /api/v4/today`, one capture round-trip

## Acceptance criteria — all met

- [x] `_build_catalog_block` returns formatted string of active projects+areas
- [x] Catalog capped at ~8000 chars, truncated by recency
- [x] Deleted entities excluded from catalog
- [x] Catalog block appears in system prompt content
- [x] Empty catalog handled (no crash, prompt still valid)
- [x] Heuristic fallback (no API key) unchanged
- [x] 11 new tests green; 186 total passing; 3 pre-existing search failures unchanged
