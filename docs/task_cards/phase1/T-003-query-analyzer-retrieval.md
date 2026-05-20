# T-003: QueryAnalyzer And Retrieval

## Goal

Implement combined A1/A2 structured analysis and A3 tenant-filtered retrieval.

## Required Reads

- [`AGENTS.md`](../../../AGENTS.md) — "Query Pipeline" + "Query Transformation Boundary" + "Sensitivity And Handling" sections.
- [`docs/adr/0002-confidence-sensitivity-handling.md`](../../adr/0002-confidence-sensitivity-handling.md) — confidence/sensitivity/risk-flags split.
- [`docs/adr/0007-query-transformation-boundaries.md`](../../adr/0007-query-transformation-boundaries.md) — `semanticQuery = reframedQuery ?? rawQuery`; no rewriting.
- [`docs/adr/0010-vector-store-interface.md`](../../adr/0010-vector-store-interface.md) — `VectorStore` Protocol; tenant-isolation invariant enforced at the adapter boundary.
- [`docs/adr/0011-hybrid-retrieval.md`](../../adr/0011-hybrid-retrieval.md) — dense + sparse via Qdrant native sparse vectors with server-side RRF fusion; the Phase 1 A3 default path.
- [`docs/adr/0012-reranker-selection.md`](../../adr/0012-reranker-selection.md) — cross-encoder `Reranker` Protocol; certification gate; A3's optional reranking step.
- [`docs/adr/0013-qdrant-collection-topology.md`](../../adr/0013-qdrant-collection-topology.md) — single shared `chunks` collection with `tenant_id` payload filter; required payload indexes.
- [`docs/contracts/vector-store-interface.md`](../../contracts/vector-store-interface.md) — full `VectorStore` Protocol spec including `SparseVector` and the `ChunkPayload`/`ScoredChunk` shapes.
- [`docs/contracts/retrieval-eval-suite.md`](../../contracts/retrieval-eval-suite.md) — gold-set shape and the retrieval-quality gate that binds reranker/embedding-route certification.
- [`docs/contracts/safety-config-format.md`](../../contracts/safety-config-format.md) — YAML format; hard-trigger semantics; A1 must check the regex BEFORE the LLM call.
- [`config/sensitivity_keywords.yaml`](../../../config/sensitivity_keywords.yaml) — current rules (stub today; real rules per Phase-2 launch gate).
- [`docs/contracts/provider-interface.md`](../../contracts/provider-interface.md) — `generate_structured` for the QueryAnalyzer call; refusal handling for A1.
- [`docs/schemas/classified-query.schema.json`](../../schemas/classified-query.schema.json), [`retrieval-plan.schema.json`](../../schemas/retrieval-plan.schema.json), [`evidence-packet.schema.json`](../../schemas/evidence-packet.schema.json) — typed boundaries.
- [`docs/contracts/observability.md`](../../contracts/observability.md) — `query.classified` and `query.retrieved` event payloads.
- Qdrant filter rule: `tenant_id` AND `approved=true` MUST always be present (enforced in `app/adapters/vector_store/qdrant_store.py` per ADR-0010, never in agents).

## Files In Scope

- QueryAnalyzer provider call
- `ClassifiedQuery` and `RetrievalPlan` models
- sensitivity keyword config
- Qdrant retrieval service
- retrieval tests

## Acceptance Tests

- QueryAnalyzer returns schema-valid `ClassifiedQuery` and `RetrievalPlan`.
- `semanticQuery` equals `reframedQuery ?? rawQuery`.
- No generic query rewriting occurs in Phase 1.
- Qdrant filters include tenant and `approved = true`.
- Hard safety triggers route to `block_with_redirect`.

## Forbidden Scope

- Do not compose final answers.
- Do not add synonym expansion.
- Do not use candidate graph data for retrieval.
- Do not allow unapproved chunk retrieval.

## Acceptance — Wave 4 Additions

- **F-23 E2E:** `tests/integration/test_t003_e2e.py::test_classify_then_retrieve_against_fixture` PASSES — runs A1+A2+A3 against `tiny_approved_corpus.json` and asserts tenant-filtered retrieval and recovery of expected chunkIds.
