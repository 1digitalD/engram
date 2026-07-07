# Slice A1 — Batch Embeddings in Reconciliation

Phase: A — Reconciliation matching
Status: COMPLETE

## Goal

Behavior-preserving performance refactor: replace N `_embed_texts` calls (one per
candidate) with a single batched call for all candidates. Load each entity type's
chunk set once and reuse across candidates of the same type.

No change to match quality or decision output. Sets up the data structure
(`_load_chunks_for_type`) that Slice A2 will extend with richer match context.

## Changes

### `services/v4_reconciliation.py` (rewritten)

- `reconcile_candidates` now calls `_enrich_candidates` instead of a list
  comprehension over `_find_similar`.
- `_enrich_candidates`: single `_embed_texts(titles)` call for all N candidates;
  `_load_chunks_for_type(entity_type)` called once per unique type and cached
  in a dict for the duration of the call.
- `_embed_texts` extracted as a module-level function (thin wrapper over
  `services.embeddings._embed_texts`) so tests can patch it cleanly on the
  reconciliation module.
- `_load_chunks_for_type`: loads all chunks for active entities of a given type
  in one query; returns `(entity_id, chunk_text, embedding, entity_data)` tuples.
- `_find_similar` removed — replaced by `_enrich_candidates` + `_load_chunks_for_type`.
- All other behavior preserved: exact match, cosine scoring, threshold, TOP_K,
  heuristic fallback, `_call_model`.

## Tests

`tests/unit/test_slice_a1_batch_embeddings.py` — 12 tests:
- `TestBatchEmbeddingCallCount`: 8 candidates → 1 call; single, zero, mixed-type cases
- `TestChunkLoadedOncePerType`: same type → 1 load; two types → 2 loads
- `TestMatchOutputCorrectness`: exact match preserved; semantic match via batch;
  below-threshold entity excluded
- `TestFallbackBehavior`: exact-match heuristic, no-match heuristic, count invariant

## Acceptance criteria — all met

- [x] 8 candidates make 1 `_embed_texts` call with 8 titles
- [x] Chunk set per type loaded once not once-per-candidate
- [x] Exact match (score=1.0) still surfaces in enriched output
- [x] Semantic match found via batch embedding path
- [x] Below-threshold entities excluded
- [x] Heuristic fallback (no API key) unchanged
- [x] 12 new tests green; 161 total passing; 3 pre-existing search failures unchanged
- [x] Replay harness: offline baseline unchanged (no model calls in offline mode)
