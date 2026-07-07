# Slice A2 — Richer Matching Context

Phase: A — Reconciliation matching
Status: COMPLETE

## Goal

Improve reconciliation matching by embedding a composed document
(`entity_type + title + content + evidence`) instead of bare title.
Richer query vector = better paraphrase matching for the 9 labeled false-creates.

## Changes

### `services/v4_reconciliation.py`

- `_build_match_document(candidate)`: composes entity type + title + content + evidence
  into a single string; None/empty fields are skipped cleanly.
- `_enrich_candidates`: calls `_build_match_document` per candidate before passing
  to `_embed_texts`; one batch call still.
- A1 invariants preserved: 1 embed call, chunk-per-type loaded once.

### `tests/unit/test_slice_a1_batch_embeddings.py`

- Updated 2 assertions that checked `docs_sent == titles` (now docs contain title
  plus richer context); updated to `title in doc` contract.

## Tests

`tests/unit/test_slice_a2_richer_matching.py` — 14 tests:
- `TestBuildMatchDocument` (8): title-only, title+content, title+evidence, all three,
  None fields, empty strings, return type, type disambiguation
- `TestRicherEmbedInput` (4): evidence in embed input, content in embed input,
  title-only fallback, 8-candidates still 1-call
- `TestSemanticMatchViaComposedDoc` (2): paraphrase match found via composed doc;
  exact title match preserved

## Expected impact on replay eval

The richer composed doc will improve similarity scores for:
- "Security roadmap" → "Agent Security" (both contain "security" + context)
- "Agent memory utilization" → "Agent Memory / Canonical Memory"
- "Agent memories collaboration" → "Agent Memory / Canonical Memory"
- "Conversation history search functionality" → "Agent Memory / Conversation History"

Exact-title cases ("Agent Platform", "Agentic SDLC", "Toolkit robustness") are
handled by the exact-match path (no embedding needed) — A3 adds the full catalog
to the prompt for the reconciler model to make the final call.

Live replay eval to be re-run after A3 with OPENAI_API_KEY set.

## Acceptance criteria — all met

- [x] `_build_match_document` composes title + content + evidence correctly
- [x] Embed input includes evidence and content when present
- [x] Title-only candidates still work
- [x] 8-candidate 1-call invariant preserved
- [x] Paraphrase match found via composed doc
- [x] Exact match preserved with richer compose
- [x] 14 new tests green; 175 total passing; 3 pre-existing search failures unchanged
