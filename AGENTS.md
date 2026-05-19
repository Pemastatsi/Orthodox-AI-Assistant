# Orthodox AI Assistant Coding Brief

Read this file first in every implementation session. Do not read archived PDFs or long planning documents during normal coding.

## Source Hierarchy

1. `AGENTS.md` is the always-read implementation brief.
2. `docs/task_cards/phase1/*.md` defines Phase 1 coding tasks. `docs/task_cards/phase2/*.md` defines Phase 2 coding tasks.
3. `docs/contracts/phase1-implementation-contract.md` defines Phase 1 behavior. Phase 2 behavior is governed by ADRs 0013–0016 and the Phase 2 contracts.
4. `docs/adr/*.md` defines locked architectural decisions.
5. `docs/api/openapi.yaml` and `docs/schemas/*.json` define public contracts.
6. `tests/fixtures/` and `tests/safety/` define executable expectations.
7. `docs/reference/` and `docs/archive/` are not active sources unless resolving a contradiction or revisiting strategy.

If sources conflict, use this priority: newer canonical docs over old reference docs; ADRs over prose; schemas/tests over prose for exact behavior.

## Product Goal

Build a closed-corpus Orthodox theological assistant for tenant-approved libraries. The assistant answers only from approved tenant-visible evidence and fails closed when evidence is insufficient.

## Locked Stack

- Backend: FastAPI, Python, PostgreSQL, Alembic.
- Vector search: Qdrant with tenant payload filters.
- Cache/session: Redis.
- Frontend: Next.js, React.
- Auth: Clerk organizations mapped to internal tenants.
- Billing: Stripe metered billing.
- LLM providers: provider interface from day 1; Anthropic certified first.
- Embeddings: OpenAI `text-embedding-3-small` unless a later certified route replaces it.
- Hosting target: Railway for early deployment.

## Phase 1 Scope

Phase 1 is an internal/private beta. Orthodox Ethos is the first tenant, but the app is tenant-aware from day 1.

Build:
- tenant-scoped data model, admin UX, logs, cache keys, and Qdrant filters
- manual corpus upload and approval
- closed-corpus Q&A
- deterministic evidence packaging
- citation verification
- query logging and flagged query capture
- provider/model abstraction
- standalone chat page and tenant-aware admin screens
- schemas/hooks for later workflows where explicitly called out

Do not build in Phase 1:
- public launch assumptions
- generated study packets
- generic LLM query rewriting
- graph-driven answering
- free-form tenant prompt editing
- draft answer text streaming before verification
- unbounded agent collaboration
- open-web answer-time browsing

## Closed-Corpus Rules

- A5 composition may use only evidence admitted into the `EvidencePacket`.
- No answer may rely on model training data, outside knowledge, or open web content.
- Every material claim needs citation support.
- If approved evidence is missing or insufficient, return the appropriate bounded fallback.
- Candidate graph edges, unapproved chunks, suppressed chunks, and admin-only content are never user-facing evidence.
- The system may explain uncertainty, but may not invent consensus, quotes, lineage, or source relationships.

## Tenant And Role Rules

- Every persisted domain row that can contain tenant data includes `tenant_id`.
- Qdrant queries always filter by `tenant_id` and `approved = true`.
- Clerk is the identity source of truth; Stripe is the billing source of truth; the internal `tenants` table joins them.
- Cache keys include tenant, normalized query, role, session hash when applicable, corpus version, prompt version, model routes, schema version, and relevant tenant config/calendar version.
- Content managers see redacted sensitive/flagged content unless explicitly authorized.
- Admin views of raw sensitive text are audited.

## Query Pipeline

- QueryAnalyzer may combine A1 and A2 into one physical low-cost structured call.
- Logs still store A1 `ClassifiedQuery` and A2 `RetrievalPlan` outputs separately.
- A1 owns query classification, sensitivity detection, and transparent safety reframing.
- A2 owns retrieval planning: filters, boosts, answer mode, and `k`.
- A2 does not rewrite user intent.
- A3 executes retrieval and returns scored candidate chunks.
- A4 is deterministic in MVP: tenant isolation, approval gates, role visibility, thresholds, policy checks, citation health, and `EvidencePacket` construction.
- A5 composes from admitted evidence only.
- A6 verifies citations, schema completeness, safety handling, and claim-source consistency.
- RED-tier early exit skips A5/A6 when no answer should be generated.

## Query Transformation Boundary

Phase 1 does not use generic LLM rewriting, synonym expansion, or intent reinterpretation.

`RetrievalPlan.semanticQuery` is:

```text
classifiedQuery.reframedQuery ?? classifiedQuery.rawQuery
```

Future concept expansion must be graph-grounded, tenant-scoped, auditable, and based only on approved graph metadata.

## Sensitivity And Handling

Use separate fields:
- `confidenceTier`: `GREEN | YELLOW | RED`
- `sensitivityPrimary`: `normal | pastoral_advice | political | medical | comparative_religion | canonical_dispute | other_sensitive`
- `riskFlags`: `self_harm | medical_emergency | canonical_dispute_active | minor_protection`
- `handling`: `answer | answer_with_disclaimer | reframe_to_teaching | block_with_redirect | insufficient_evidence`

Hard safety triggers such as self-harm or medical emergency immediately use `block_with_redirect`.

Pastoral, medical, political, comparative, and canonical-dispute queries must not become personal advice, diagnosis, electoral guidance, or unsupported doctrinal certainty.

Sensitive reframing is transparent in the UI. The user sees that the system answered a teaching-oriented version of the question.

## Prompt And Model Rules

- Base closed-corpus prompt is platform-controlled.
- Tenants do not edit free-form base prompts in MVP.
- Tenants may configure safe fields only: tone, answer length, citation style, calendar style, starter corpus toggle, sensitive strictness, and approved disclaimer template.
- Free-form prompt versions require preview tests, rollback, audit trail, and full safety-suite pass before activation.
- Production model routes must be certified by provider, model, prompt version, schema version, and safety-suite result.

## Citation Rules

- Target exact quote span where possible, plus page or timestamp, source title/work, father, chunk/source hashes, approval status, and corpus origin.
- A6 first checks deterministic citation ID existence and quote overlap.
- Quote overlap threshold defaults to 70% and is tenant-tunable only through safe config.
- A5 may not claim lineage such as "quotes", "builds on", "translation of", or "contrasts with" unless approved edge IDs appear in evidence and pass A6.

## Cache, Billing, Logs

- Stored answer cache TTL defaults to 1 hour.
- Standalone questions may be cached; follow-ups include session hash and should not share cache entries with standalone queries.
- Cached answers count as `served_answer_count`.
- Fresh model runs count separately as `fresh_model_run_count`.
- Stripe MVP meter is `served_answer_count`.
- Store sensitive logs redacted by default.
- During private beta, raw sensitive text may be encrypted, admin-only, audited, and retained for 30 days.
- Never send raw sensitive logs to analytics tools.

## Graph And PAG-RAG

- MVP retrieval is vector-first with Qdrant.
- PostgreSQL stores canonical graph metadata first.
- LLM-extracted graph data is candidate-only until reviewed.
- Only approved graph edges may affect retrieval expansion, answer wording, confidence, lineage explanations, or source priority.
- Neo4j or Apache AGE is optional later, not MVP infrastructure.

## Required Tests

- 20-query theological safety suite.
- Closed-corpus "no outside answer" tests.
- Tenant isolation tests for SQL, Qdrant filters, cache keys, and logs.
- Sensitivity classification and hard-trigger tests.
- No generic query rewriting tests.
- Evidence admission and unapproved-content suppression tests.
- Citation verification tests.
- Cache invalidation tests.
- Mode-specific response schema tests.

## Implementation Style

- Prefer schemas, tests, and deterministic services over long prompt prose.
- Keep each coding session scoped to the task card.
- Do not weaken safety, tenant isolation, or citation rules for convenience.
- Update ADRs when changing locked decisions.

## Phase 2 Direction

Phase 2 introduces a Rich Output layer on top of the Phase 1 Q&A foundation. All Phase 2 capabilities are governed by ADRs 0013–0016 and the Phase 2 contracts.

### Five Output Tiers (ADR 0013)
- **Tier 1:** Markdown + Mermaid + LaTeX rich-text answers.
- **Tier 2:** Interactive visual artifacts — Patristic Lineage Graph, Council Timeline, Citation Network, Dispute Map, Manuscript Witness Tree, Mind Map.
- **Tier 3:** Generated documents — Study Packet, Sermon Outline, Slide Deck, Catechism Lesson Plan, Parish Bulletin, Bishop Briefing, Syllabus Bundle, Feast-Day Bundle, Parish FAQ.
- **Tier 4:** Two-voice TTS audio overviews with citation timestamps.
- **Tier 5:** Orthodox-unique multimedia — Bilingual Greek+English with morphology, Liturgical Calendar Overlay, Iconographic Reference Cards, Byzantine Chant integration, Holy Land + Monastery Map, Disputation Simulator.

### Key Phase 2 Architectural Rules
- **Closed-corpus provenance (ADR 0013):** Every artifact carries `citationRefs` back to approved evidence chunks; no artifact can contain an unverified claim.
- **Artifact provider abstraction (ADR 0014):** All rendering goes through certified `ArtifactProvider` interfaces; no direct library calls in business logic. Same certification model as LLM routes (ADR 0004).
- **Multi-meter billing (ADR 0015):** Three Stripe meters — `served_answer_count` (Q&A), `generated_artifact_count` (documents + complex graphs), `audio_minutes_generated` (TTS). All features available on all paid tiers; only volume caps differ.
- **Workflow approval gates (ADR 0016):** High-stakes documents (Bishop Briefing, Syllabus Bundle, Catechism Lesson Plan, Parish FAQ, Parish Bulletin, Feast-Day Bundle) require admin/owner approval before export.

### Phase 2 Billing Tiers (EUR)
Scholar €19/month · Parish €59/month · Seminary €179/month · Enterprise €600–1,500 custom.
All tiers: full feature access. Differentiator is volume cap per meter, not feature set.

### Phase 2 Task Cards
Organized in four implementation waves under `docs/task_cards/phase2/`:
- **Wave 2.0 (T-101–T-107):** Foundation — rich-text rendering, export foundation, artifact provider abstraction, study packet workflow, patristic lineage graph, audio overview, multi-meter billing.
- **Wave 2.1 (T-108–T-114):** Visual depth — council timeline, dispute map, citation network, manuscript witness tree, slide deck export, sermon builder, mind map.
- **Wave 2.2 (T-115–T-120):** Orthodox-unique multimedia — bilingual side-by-side, liturgical calendar overlay, iconographic reference cards, Byzantine chant, Holy Land map, disputation simulator.
- **Wave 2.3 (T-121–T-125):** Workflow library — bishop briefing, syllabus bundle, catechism lesson plan, parish bulletin, feast-day bundle.

## Known Architecture Gaps (address before Phase 2 begins)

The following gaps were identified during Phase 1 architecture review. They do not block Phase 1 implementation but must be resolved before Phase 2 work begins:

1. **Layout-aware PDF parsing — RESOLVED.** See ADR-0008 and `docs/contracts/parser-interface.md`. Two-path hybrid (`pdfplumber` for born-digital files, `pytesseract` with `grc`+`ell` language packs for scanned files) behind a `Parser` Protocol, dispatched by a `< 50 chars/page` heuristic owned by the chunking service. Decision row: `approved-decisions-register.md` D-PDF-001.

2. **Chunking strategy — RESOLVED.** See ADR-0009 and `docs/contracts/chunking-contract.md`. Hierarchical heading-boundary chunking with a sentence-boundary fallback; 800–1200 token soft cap, 1500 hard cap; every chunk carries `sectionPath`, `pageStart`, `pageEnd`, `parentChunkId`. The `parentChunkId` field is the join key for the ADR-0006 Phase 2 graph traversal layer. Decision row: `approved-decisions-register.md` D-CHK-001.

3. **Multilingual embedding upgrade** — `text-embedding-3-small` is the Phase 1 certified baseline. Phase 2 must benchmark multilingual embedding models on Polytonic Greek ↔ English retrieval pairs before committing to a replacement. Candidate models and evaluation criteria are documented in ADR 0006. The existing upgrade SOP (dual-index → backfill → certify → cutover) applies.

4. **Reranking step between A3 and A4 — RESOLVED.** See ADR-0012 and `docs/contracts/retrieval-eval-suite.md`. Phase 1 ships a `Reranker` Protocol mirroring `LLMProvider` and `VectorStore`, with `BgeRerankerLocal` (BAAI/bge-reranker-v2-m3) as the concrete implementation and `CohereRerankerAdapter` as the managed-API alternative. LLM-pointwise reranking is explicitly forbidden. Activation requires `purpose='rerank'` `ModelRoute` certification through both the safety-suite gate (ADR-0004) and the retrieval-eval gate (`retrieval-eval-suite.md`). A4 sorts by `ScoredChunk.rerankScore` when present, falling back to `score`. Decision row: `approved-decisions-register.md` D-RNK-001.

5. **Hybrid retrieval (dense + sparse) — RESOLVED.** See ADR-0011 and `docs/contracts/vector-store-interface.md`. Phase 1 A3 issues a hybrid query combining `text-embedding-3-small` dense vectors with BM25 sparse vectors via Qdrant's native sparse-vector support, server-side RRF fusion. The tenant filter applies to both signals identically; A3 issues a single Qdrant Query API call. Existing chunks require re-ingestion to populate `ChunkPayload.sparse_embedding`. Decision row: `approved-decisions-register.md` D-RET-001.

6. **Retrieval evaluation suite — RESOLVED.** See `docs/contracts/retrieval-eval-suite.md`. Per-tenant, version-pinned gold sets at `tests/retrieval_eval/gold_sets/<tenant_id>/<version>.json` anchored on stable `chunk_id` values, gating `purpose IN ('embedding', 'rerank', 'retrieval_eval_judge')` `model_routes` certification alongside the existing safety suite. Deterministic metrics (Recall@K, Precision@K, MRR, nDCG@K) plus Ragas-style LLM-judge metrics (faithfulness, context precision/recall, answer relevancy). Decision row: `approved-decisions-register.md` D-EVAL-001.

7. **Do not adopt pre-compilation or external Knowledge Artifact approaches** — Pre-compiling corpus summaries as persistent "Knowledge Artifacts" conflicts with ADR 0001 (every claim must trace to an approved chunk with a verifiable quote span) and the dynamic approval workflow (corpus changes continuously). Any future proposal to introduce a compilation stage must first produce an ADR update resolving the citation traceability conflict.
