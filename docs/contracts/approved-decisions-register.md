# Approved Decisions Register

Status: Canonical
Date: 2026-05-11

This register preserves approved decisions extracted from archived planning drafts. Use it when a task needs a specific decision not covered in `AGENTS.md`, ADRs, schemas, or task cards.

## Founder Decisions

| Area | Decision |
|---|---|
| Phase 1 tenancy | Tenant-aware admin UX and tenant-isolated data paths from day 1. |
| Theological review | Founder reviews internal beta; external Orthodox reviewer required before public or paid launch. |
| Beta scope | Phase 1 is internal/private beta. |
| Sensitive logs | Redacted by default; raw text encrypted, admin-only, audited, 30-day private-beta retention. |
| Model strategy | Provider abstraction from day 1; only certified routes serve users. |
| EU data region | Keep `data_region`; EU-only hosting is not a Phase 1 blocker. |
| Cached billing | Cached answers count as served answers; fresh model runs tracked separately. |
| Citation detail | Target exact quote span plus page/timestamp, source/work, father, hashes, approval, and origin. |
| Study packets | Not in MVP; schemas/hooks only until Q&A is stable. |
| Tenant prompts | Safe config fields only in MVP; no free-form base prompt editing. |

## Clarification Decisions

| Item | Decision |
|---|---|
| A. Sensitivity taxonomy | Use `sensitivityPrimary` plus `riskFlags`; hard triggers bypass two-stage gate. |
| B. Sensitivity keywords | Keep tunable keyword YAML with hard safety triggers separated from medical terms. |
| C. Answer mode selection | `scholarly_dispute` is available to all users for explicit dispute/comparison queries. |
| D. Tier thresholds | Confidence thresholds are tenant-tunable safe config, not hardcoded forever. |
| E. Phase 1 A2/A4 | Use stable interfaces; Phase 1 QueryAnalyzer and deterministic A4 enforce tenant and visibility gates. |
| F. Reframing UX | Sensitive reframing is transparent; no "view as originally asked" pseudo-control. |
| G. A6 verification | Deterministic checks first; 70% quote-overlap default; optional low-cost consistency judge only. |
| H. Clerk mapping | Clerk org maps to internal tenant; tenant is resolved from auth context, not request body trust. |
| I. Calendar style | Use `calendar_profile` with independent fixed-feast and Paschalion settings. |
| J. Call 5 schema | Source hash is SHA-256 of raw bytes before processing; extraction method includes version string. |
| K. Permissions | Content managers see sensitive/flagged content redacted; audit raw sensitive views. |
| L. Safety queries | Queries 11-20 are canonical fixtures; changes require founder sign-off and safety-suite run. |
| M. Streaming | Draft-answer streaming rejected for MVP; stream progress only, final answer after A6. |
| N. Session cache | Full cache key includes prompt, corpus, role, config, calendar, model route, schema, and session where applicable. |
| O. Make.com HMAC | Webhooks require timestamp window, nonce/replay protection, idempotency key, and secret rotation. |
| P. PAG-RAG | Phase 2+ lineage graph; only approved edges enter evidence and answer claims. |

## Optimization Decisions

| Item | Decision |
|---|---|
| 1. Multi-tenant day 1 | Accepted; every tenant surface and data path is tenant-aware. |
| 2. Confidence/handling split | Accepted; confidence, sensitivity, risk flags, and handling are separate. |
| 3. Attestation day 1 | Store attestation/source integrity fields early to avoid re-ingestion. |
| 4. Flagged embeddings | Store flagged query embeddings; model upgrades require dimension-aware backfill. |
| 5. Father/work grouping | Cross-reference panels group by father and work. |
| 6. Prompt versioning | Admin-only, post-MVP free-form versions require preview, rollback, and safety gate. |
| 7. Starter corpus | Treat starter corpus as virtual tenant; enforce uniqueness at DB layer. **Phase 1 status: dormant** — `tenant.config.starterCorpusEnabled` is accepted by config validation but Phase 1 retrieval ignores it (the Qdrant filter is always `tenant_id == Principal.tenantId`). Activation requires a follow-up ADR that defines the virtual-tenant retrieval path, the citation `corpusOrigin` disclosure, and an isolation test demonstrating that enabling starter corpus does not expose other tenants' approved chunks. |
| 8. Regex post-filter | Pastoral forbidden phrases live in safety config; changes require safety-suite run. |
| 9. Retrieval explainability | Evidence packets include retrieval explanation metadata. |
| 10. Rate limiting | Per-tenant rate limiting is accepted. |
| 11. Cost telemetry | Per-tenant cost dashboard is accepted. |
| 12. Batch progress | Batch ingestion tracks progress and failures. |
| 13. Citation format | Use canonical citation formatter shared by answer modes and exports. |
| 14. API versioning | Version public response schemas. |
| 15. Query clustering | Auto-cluster flagged queries after core query path is stable. |
| 16. Answer schemas | Answer mode outputs use typed schemas. |
| 17. Embedding upgrades | Document and test embedding model upgrade procedure. |
| 18. CI safety gate | Theological safety regression runs in CI. |
| 19. Shadow A/B | Rejected until post-production traffic and evaluation infrastructure exist. |
| 20. Scoped approvals | Phase 3+ downward-only delegation; admins cannot grant beyond their scope. |

## Architecture Decisions (Phase 1)

These rows resolve the engineering decisions previously flagged as open in `AGENTS.md` §Known Architecture Gaps. They are referenced by ADRs 0008–0010 and by `parser-interface.md`, `chunking-contract.md`, and `vector-store-interface.md`.

| Item | Decision |
|---|---|
| D-PDF-001. PDF parser library | Two-path hybrid behind a `Parser` Protocol: `pdfplumber` for born-digital PDFs (text layer present), `pytesseract` with the `grc` (Polytonic Greek) and `ell` (modern Greek) language packs for scanned PDFs. Dispatch heuristic lives in the chunking service: after `pdfplumber` extraction, if average extracted text is below 50 characters per page, the file is re-routed to the Tesseract path. MIT-licensed dependencies only (no AGPL exposure from `pymupdf`); no per-page OCR cost; corpus bytes never leave the server boundary. Phase 2 hook: `VisionParser` (LLM-with-vision) added as a third `Parser` implementation without touching the dispatch heuristic. See ADR-0008 and `parser-interface.md`. |
| D-CHK-001. Chunking strategy | Hierarchical (heading-boundary) chunking with a sentence-boundary fallback for unheaded sections. Soft token cap 800–1200 (cl100k_base via `tiktoken`); hard cap 1500 tokens triggers a sentence-boundary split. Every chunk carries `sectionPath` (ordered enclosing heading strings), `pageStart`, `pageEnd`, and `parentChunkId` (NULL for top-level chunks, populated when a parent chunk is split by the sentence-boundary fallback). The `parentChunkId` field is the join key for the Phase 2 graph traversal layer described in ADR-0006 — preserving the hierarchy now is what unlocks that future architecture without re-ingestion. See ADR-0009 and `chunking-contract.md`. |
| D-VS-001. VectorStore seam | Qdrant remains the Phase 1 vector store per ADR-0006. All agent and service code accesses the vector store only through a `VectorStore` Protocol modeled on the existing `LLMProvider` Protocol (`provider-interface.md`). The concrete `QdrantStore` implements the Protocol; a `PgvectorStore` can be added in Phase 2 as a drop-in replacement without touching agent or service code. The Protocol enforces the tenant-isolation invariant: every `search` and `delete_by_filter` call MUST include `tenantId` in the filter, mirroring the DB-level invariant from ADR-0003. See ADR-0010 and `vector-store-interface.md`. |
| D-MDL-001. Active Phase 1 model routes | Three certified-track routes seed the `model_routes` table at Phase 1 cutover (all with `certification_status='experiment'` per ADR-0004; promotion to `certified` runs through the safety-suite gate in T-005): A1/A2 query analysis uses `anthropic:claude-sonnet-4-6` (low latency, reliable structured output); A5 composition uses `anthropic:claude-opus-4-7` (lowest hallucination risk for evidence-grounded composition); embeddings use `openai:text-embedding-3-small` (Phase 1 baseline per ADR-0006). An A6 verifier-judge route is intentionally absent; per decision register row G, the optional consistency judge is disabled when no certified `verifier_judge` route exists. See `db-schema.md` §First Migration Seed Data. |
| D-RET-001. Hybrid retrieval (dense + sparse) | Phase 1 A3 retrieval issues a hybrid query combining dense (`text-embedding-3-small`) and sparse (BM25 via Qdrant FastEmbed server-side inference) signals through Qdrant's native sparse-vector support, fused server-side with Reciprocal Rank Fusion (RRF, `k=60` default). Pure-dense retrieval remains the fallback when no sparse model is configured for a tenant. The fusion `k` parameter is tenant-tunable through safe config (same pattern as the 70% quote-overlap threshold). BM42 and SPLADE are deferred; promotion requires empirical comparison on the certified retrieval gold set (`retrieval-eval-suite.md`). Re-ingestion of existing chunks is required to populate `ChunkPayload.sparse_embedding`. See ADR-0011 and `vector-store-interface.md`. |
| D-RNK-001. Reranker selection | A `Reranker` Protocol is added behind a Phase 1 adapter pattern mirroring `LLMProvider` and `VectorStore`. The Phase 1 concrete implementation is `BgeRerankerLocal` (wrapping `BAAI/bge-reranker-v2-m3` via `sentence-transformers`, Apache-2.0). `CohereRerankerAdapter` is a certified-track managed-API alternative requiring closed-corpus-egress review. LLM-pointwise reranking (per Sialtsis 2026) is forbidden: it would add 20× generative-LLM calls per query (~90% of per-query token cost in the referenced empirical study), violate the answer-path-LLM-count principle from ADR-0006, and produce a brittle integer-parsing scoring path. The reranker is a `ModelRoute` with `purpose='rerank'`; activation requires both the safety-suite gate (ADR-0004) and the retrieval-eval gate (`retrieval-eval-suite.md`). A4 sorts by `ScoredChunk.rerankScore` when present, falling back to `score`. See ADR-0012. |
| D-EVAL-001. Retrieval evaluation suite | A per-tenant, version-pinned retrieval evaluation suite at `tests/retrieval_eval/` gates `model_routes` certification for `purpose IN ('embedding', 'rerank')` alongside the existing safety-suite gate. Gold sets anchor on stable `chunk_id` values (not URLs); cases include `language`, `expectedChunkIds`, `minimallySufficientChunkIds`, `answerMode`, and `sensitivityPrimary`. Deterministic metrics (Recall@K, Precision@K, MRR, nDCG@K) at K∈{6,12,20} require no LLM judge; answer-quality metrics (faithfulness, answer_relevancy, context_precision, context_recall) use a Ragas-style LLM judge route (`purpose='retrieval_eval_judge'`, certified separately from any production route). Pass gate: new score ≥ baseline − 0.02 on every metric for the active gold-set version. Hard-trigger queries live in the safety suite only. See `retrieval-eval-suite.md`. |
