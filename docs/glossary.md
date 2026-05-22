# Glossary

Status: Canonical
Date: 2026-05-22

Canonical definitions for terms used across the Orthodox-AI-Assistant contract pack. The list is alphabetical within each section. Each entry cross-references the contract or ADR where the term is normatively defined.

## Pipeline stages (A1–A6)

| Term | Definition |
|---|---|
| **A1 (Classifier)** | Query classifier. Resolves `sensitivityPrimary`, `riskFlags`, the reframed query when safety reframing applies, and the `answerMode` hint. See `docs/schemas/classified-query.schema.json`, AGENTS.md L78–88. |
| **A2 (Planner)** | Retrieval planner. Produces `RetrievalPlan` with `semanticQuery`, `answerMode`, `k`, filters, and (Phase 3+) optional `conceptExpansion`. See ADR-0007, `docs/schemas/retrieval-plan.schema.json`. |
| **A3 (Retrieval)** | Dense + sparse hybrid retrieval over Qdrant with server-side RRF (`k=60`); optional ColBERT 3rd signal gated by `RetrievalPlan.useLateInteraction`. Output: `list[ScoredChunk]`. See ADR-0011. |
| **A4 (Admission)** | Deterministic evidence admission. Filters `ScoredChunk`s by tenant, approval, visibility, and confidence thresholds; emits the `EvidencePacket`. See `docs/schemas/evidence-packet.schema.json`. |
| **A5 (Composer)** | Answer composition. Reads only from `EvidencePacket`; never sees the open web; never trains on user text. Uses `anthropic:claude-opus-4-7` for Phase-1 production. See AGENTS.md L60–64. |
| **A6 (Verifier)** | Citation verifier. Deterministic shingle-based quote-overlap check (≥70% by default); optional low-cost LLM consistency judge after the deterministic check passes. See `docs/contracts/quote-overlap-algorithm.md`. |

## Data structures

| Term | Definition |
|---|---|
| **BoundedFallbackResponse** | The shape returned when A6 fails or the safety path triggers (cases 6, 10, 12, 17, 20 of the 20-query suite). Platform-fixed text for self-harm and medical-emergency; tenant-tunable disclaimer for others. See `docs/contracts/phase1-implementation-contract.md` Appendix A. |
| **calendarProfile** | Inline object on `tenants.config` carrying fixed-feast and Paschalion settings; `version` field is part of the cache key (`cache-key.md`). See `docs/schemas/calendar-profile.schema.json`. |
| **Chunk** | Indexed retrievable unit; the smallest piece of evidence A5 can quote and A6 can verify. Has `sectionPath`, `pageStart`/`pageEnd`, `parentChunkId`, `embeddingModel`, optional `contextPrefix` (REC-005). See `docs/schemas/chunk.schema.json`, ADR-0009. |
| **ChunkPayload** | The Qdrant-payload projection of a `Chunk` — fields that travel with the vector for filtering and hydration. See `docs/contracts/vector-store-interface.md`. |
| **ClassifiedQuery** | Output of A1: the canonical typed record of how the user's question was classified. See `docs/schemas/classified-query.schema.json`. |
| **contextPrefix** | Optional 50–100-token per-chunk document-context summary (≤200 chars), generated at ingestion by a `ModelRoute` with `purpose='context_prefix'`. Concatenated to `text` for embedding and BM25 but not used for A6 quote-overlap. See ADR-0009 §Step 4. |
| **corpusVersion** | Tenant-scoped string that bumps when approved-set, embedding model, chunking parameters, or Contextual Retrieval toggle changes. Part of the cache key. See `docs/contracts/cache-key.md`. |
| **EvidencePacket** | The bounded, tenant-scoped, approved-only set of chunks A5 may compose from. Produced by A4; consumed by A5 and A6. See `docs/schemas/evidence-packet.schema.json`. |
| **graph_candidates** | Phase-1 candidate-edge table populated by ingestion-time regex + LLM hybrid extraction. Candidate edges never reach A4/A5; promotion to `lineage_edges` requires Phase-2 admin approval. See REC-013, `docs/contracts/db-schema.md`. |
| **lineage_edges** | Approved relations between graph entities (`quotes`, `references`, `builds_on`, etc.). The only edges A6 considers for lineage verification. See ADR-0006. |
| **ModelRoute** | Certified `(provider, model, prompt_version, schema_version, purpose)` tuple. The row in `model_routes`; the runtime selector for every LLM call. Routes are seeded as `experiment` and promoted by `role='owner'` per ADR-0004. |
| **Principal** | Authenticated request actor. Carries `tenant_id`, `role`, `user_id`, `clerk_user_id`, and (Phase 2, ADR-0015) `region`/`cross_region`. See `docs/schemas/principal.schema.json`, `docs/contracts/auth-context.md`. |
| **RetrievalPlan** | Output of A2. Carries `semanticQuery`, `answerMode`, `k`, filters, optional `useLateInteraction` and `lateChunking` flags. See `docs/schemas/retrieval-plan.schema.json`. |
| **RunTrace** | Per-request persistent trace. Records every stage (A1–A6) with input/output shapes, latency, `prompt_version`, `model_route_id`, redacted log lines, and `quoteOverlapRatio` per citation. Unconditionally persisted on every served request including hard-safety bypass. See `docs/schemas/run-trace.schema.json`. |
| **ScoredChunk** | Retrieval hit. A `Chunk` plus a cosine `score`, a `rank`, and an optional `rerankScore`. The contract is shared by `VectorStore.search` and `Reranker.rerank`. See `docs/schemas/scored-chunk.schema.json`. |
| **VerifiedResponse** | The final API payload after A6 passes. Carries `runId`, the composed answer, citations with per-citation `quoteOverlapRatio`, `confidenceTier`, and `handling`. See `docs/schemas/verified-response.schema.json`. |

## Tenant and corpus concepts

| Term | Definition |
|---|---|
| **approved** | A `Chunk` (and its parent `Source`) flagged `approved=true` in Postgres and the Qdrant payload. The closed-corpus invariant requires `approved=true` AND `tenant_id=Principal.tenantId` on every retrieved chunk. See ADR-0001. |
| **closed corpus** | The Phase-1 invariant that A5 may compose only from `EvidencePacket`. No web search, no training-data recall, no unapproved evidence. See ADR-0001. |
| **ecclesiasticalJurisdiction** | Tenant-config field naming the ecclesiastical body (e.g., Greek Orthodox Archdiocese of America, Russian Orthodox Church Outside Russia). Drives default `calendarProfile`, certain pastoral filters, and some content-license disclosures. See `docs/schemas/tenant.schema.json`. |
| **starter corpus** | Phase-1 dormant feature: a virtual "starter" tenant whose chunks could be surfaced to other tenants via `tenant.config.starterCorpusEnabled`. Phase 1 retrieval ignores the flag; activation requires a follow-up ADR. See decision register row 7. |
| **tenant_id** | The canonical isolation key. Carried on every multi-tenant row; required on every `VectorFilter`; enforced by Postgres RLS (ADR-0016) and by the `VectorStore` Protocol invariant (ADR-0010). |

## Operational concepts

| Term | Definition |
|---|---|
| **certified_route** | A `model_routes` row with `certification_status='certified'`. Only certified routes serve user traffic. Promotion requires safety-suite + retrieval-eval pass + `role='owner'` PATCH. See ADR-0004. |
| **cross-provider failover** | Phase-2 mechanism (ADR-0014) that routes a stage to a certified peer when the primary returns 5xx, times out, exceeds rate-limit threshold, or breaches the latency circuit-breaker. Refusals never trigger failover. |
| **failover_peer_route_id** | Reference on a `ModelRoute` to a certified peer of the same `purpose`. At most one peer per route; no cycles. See ADR-0014. |
| **hard safety** | The category of queries where the response is platform-fixed (self-harm → 988; medical emergency → local emergency redirect). Hard-safety queries bypass the rest of the pipeline but still mint a `runId` and persist a minimal `run_traces` row. See AGENTS.md, `phase1-implementation-contract.md`. |
| **prompt_version** | Path-identifier of the form `{stage}/{language}/{date}.{counter}` mapping to a file under `/prompts/`. Stamped on every `ModelRoute` invocation and `RunTrace` entry. See `docs/contracts/prompt-management.md`. |
| **RED rate** | Rolling-7-day fraction of served answers whose `confidenceTier` is RED (hard-safety excluded). Phase-1→2 exit criterion #3 requires ≤30%. See `phase1-implementation-contract.md` L116–124. |
| **safety_suite_run** | An aggregate row in `safety_suite_runs` recording the outcome of a full 20-query suite execution against a candidate route. The route's certification PATCH references this row. See ADR-0004 §Route Certification Protocol. |

## Vocabulary used by the report (REC / GS prefixes)

| Term | Definition |
|---|---|
| **REC-NNN** | Recommendation NNN from the 2026-05-22 frontier meta-evaluation report. P0 blocks Phase-1 ship; P1 blocks Phase-2 launch; P2 is Phase-2+ planning. |
| **GS-N** | Gold-Standard upgrade N (1–4) supplied by the founder on 2026-05-22 after the report review. GS-1 = Postgres RLS pulled forward (ADR-0016). GS-2 = Unicode normalization cross-link (no-op; quote-overlap-algorithm.md already mandates it). GS-3 = Prompts-as-code (`/prompts/` + CI gate). GS-4 = Latency-threshold circuit breaker (folded into ADR-0014). |
