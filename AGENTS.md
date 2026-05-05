# Orthodox AI Assistant Coding Brief

Read this file first in every implementation session. Do not read archived PDFs or long planning documents during normal coding.

## Source Hierarchy

1. `AGENTS.md` is the always-read implementation brief.
2. `docs/task_cards/phase1/*.md` defines the current coding task.
3. `docs/contracts/phase1-implementation-contract.md` defines Phase 1 behavior.
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

## Known Architecture Gaps (address before Phase 2 begins)

The following gaps were identified during Phase 1 architecture review. They do not block Phase 1 implementation but must be resolved before Phase 2 work begins:

1. **Layout-aware PDF parsing** — `chunking_service.py` must use a layout-aware parser (not plain page-order extraction) to correctly link footnotes and scriptural citations to their body paragraphs. The library choice and chunk metadata requirements are specified in T-002. This must be decided before T-002 implementation begins.

2. **Chunking strategy** — Fixed-size chunking is insufficient for Patristic texts. Semantic or hierarchical chunking by natural section boundaries is required to preserve argument integrity and pass A6 citation overlap thresholds. Specified in T-002; must be decided before implementation begins.

3. **Multilingual embedding upgrade** — `text-embedding-3-small` is the Phase 1 certified baseline. Phase 2 must benchmark multilingual embedding models on Polytonic Greek ↔ English retrieval pairs before committing to a replacement. Candidate models and evaluation criteria are documented in ADR 0006. The existing upgrade SOP (dual-index → backfill → certify → cutover) applies.

4. **Reranking step between A3 and A4** — A cross-encoder reranker is deferred to Phase 2. `a3_retrieval.py` must return `ScoredChunk` objects (not raw Qdrant hits) in Phase 1 so the reranker can be inserted without breaking A4's input contract. See `code-gen-guide.md` section 12.

5. **Do not adopt pre-compilation or external Knowledge Artifact approaches** — Pre-compiling corpus summaries as persistent "Knowledge Artifacts" conflicts with ADR 0001 (every claim must trace to an approved chunk with a verifiable quote span) and the dynamic approval workflow (corpus changes continuously). Any future proposal to introduce a compilation stage must first produce an ADR update resolving the citation traceability conflict.
