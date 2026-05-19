# Tech Stack Comparison + Phase 1 Go/No-Go Analysis

> **Status:** Analysis deliverable. Not a canonical contract. Lives in `docs/reference/`
> per `CLAUDE.md` Source Hierarchy (reference docs are not active sources). The
> recommendations in §3 require founder approval before any ADR/contract/schema edits.

## Context

A "recommended tech stack" was proposed (LlamaIndex/LangChain, Pinecone/Weaviate/Chroma,
text-embedding-3-large, Unstructured.io, generic multi-agent/eval/fine-tuning/graph-RAG).
The question: is the **current** Orthodox AI Assistant stack — as locked in `AGENTS.md`,
18 contracts in `docs/contracts/`, 12 ADRs in `docs/adr/`, `docs/api/openapi.yaml`, 21
schemas in `docs/schemas/`, and 7 task cards in `docs/task_cards/phase1/` — superior, and
can the project truly beat **VulgateAI (Longbeard)** and **Logos Bible Software** so Phase 1
(T-001 → T-007) can begin?

This file contains:

1. A category-by-category verdict comparing the current stack to the recommended one.
2. A competitive verdict vs. VulgateAI and Logos.
3. Pre-Phase-1 quick-win optimizations (incorporate before T-001 kickoff).
4. Phase 2 optimization charter (defer, but charter now).
5. A go/no-go recommendation for Phase 1.
6. Critical files for the executor.
7. How to verify the verdict.

No backend or frontend code is implemented yet — Phase 1 is the implementation of the
contract layer that already exists.

---

## 1. Verdict: Current Stack vs. Recommended Stack

**Bottom line:** Current stack is **superior in 8/12 categories**, **equal in 3/12**, and
**recommended suggests a future upgrade in 1/12** (already on the Phase 2 charter). The
recommended stack is a generic "best-of-RAG-2025" loadout; the current stack is
**purpose-built for closed-corpus, multi-tenant, citation-verified theological QA** — a
problem the recommended stack does not address.

| # | Category | Recommended | Current (this repo) | Verdict | Why |
|---|----------|-------------|---------------------|---------|-----|
| 1 | **Frontend** | Next.js / React | Next.js 14 + React 18 + TS + Tailwind + Clerk + zod | **TIE** | Same framework; current adds typed API client generated from `openapi.yaml`, schema-driven validators, SSE streaming for A1–A6 progress. |
| 2 | **Backend** | FastAPI **or** Node.js | FastAPI (Python 3.12, async-first, `uv`, SQLAlchemy 2, Alembic, structlog, Clerk JWT) | **CURRENT WINS** | Single, opinionated, contract-driven choice. Async Python is correct for RAG (Pydantic schema-first composition, tool ecosystem for OCR/embeddings). Node-or-FastAPI is a non-decision. |
| 3 | **RAG framework** | LlamaIndex **or** LangChain | Custom A1–A6 pipeline (`QueryAnalyzer → RetrievalPlanner → Retrieval → EvidencePackager → Composer → Verifier`) | **CURRENT WINS — DECISIVELY** | LlamaIndex/LangChain provide convenience at the cost of (a) opaque prompt chains, (b) weak tenant isolation, (c) no deterministic citation verification, (d) provider-coupling, (e) cost-amplifying retries you cannot audit. The closed-corpus + 70%-quote-overlap (`docs/contracts/quote-overlap-algorithm.md`) discipline **requires** a deterministic A6 step those frameworks cannot enforce. Multi-tenant + jurisdictional configs + dual-gate certification (safety + retrieval eval) would have to be re-implemented on top of either framework, fighting the framework the whole way. ADR-0001, ADR-0004, ADR-0006, ADR-0007 already justify this. |
| 4 | **Vector DB** | Pinecone / Weaviate / Chroma | Qdrant via `VectorStore` Protocol (ADR-0010), pgvector swap-in | **CURRENT WINS** | Qdrant has best-in-class **native hybrid** (dense + BM25 sparse via FastEmbed, server-side RRF). Pinecone is closed-source SaaS-only (vendor lock). Chroma is single-user dev-grade. Weaviate is fine but heavier ops. The Protocol abstraction means you can swap to pgvector if Railway-managed Qdrant becomes a cost issue. |
| 5 | **Embeddings** | text-embedding-3-large | text-embedding-3-small (Phase 1 baseline) → multilingual upgrade benchmarked Phase 2 (ADR-0006) | **EQUAL (current strategy correct)** | 3-small is the right Phase-1 baseline: ~6× cheaper, faster, and the bottleneck for Phase 1 is **retrieval quality on English + modern Greek**, not multilingual reach. The Phase 2 charter explicitly benchmarks 3-large vs `multilingual-e5-large-instruct` vs custom Polytonic-Greek fine-tune via dual-index + backfill + certify SOP. This is more disciplined than the recommendation. **Optimization opportunity below.** |
| 6 | **Ingestion** | Unstructured.io | `pdfplumber` (born-digital) + `pytesseract` with Polytonic Greek `grc` + modern Greek `ell` packs; `VisionParser` stub for Phase 2 (ADR-0008) | **CURRENT WINS** | Unstructured.io is general-purpose and **does not have polytonic Greek OCR**. Polytonic diacritics are non-negotiable for patristic sources. Hierarchical heading-boundary chunking (ADR-0009, `docs/contracts/chunking-contract.md`) preserves patristic argument structure — Unstructured uses fixed/semantic windowing that breaks it. |
| 7 | **LLMs** | Opus / Sonnet | Anthropic Claude Opus 4.7 (A5 composition) + Sonnet 4.6 (A1/A2 structured output), via `LLMProvider` Protocol with OpenAI adapter (ADR-0004) | **TIE** (current adds provider abstraction) | Same model choice; current adds certification-gated `model_routes` table (draft → experiment → certified → deprecated) so no model serves traffic until it passes the 20-case safety suite + retrieval eval. Neither competitor does this. |
| 8 | **Reranking** | (implied "advanced search") | `BAAI/bge-reranker-v2-m3` via `sentence-transformers` Apache-2.0, local inference (ADR-0012); LLM-pointwise reranking **explicitly forbidden** | **CURRENT WINS** | Local cross-encoder = ~100ms per query, no marginal API cost. The explicit ban on LLM-pointwise reranking (would 20×-amplify generative calls per query) reflects a discipline the recommended stack never mentions. |
| 9 | **Multi-agent** | "Multi-agent systems" (vague) | A1–A6 explicit pipeline with versioned JSON schemas per stage, deterministic A4 + A6, RED-tier early exit | **CURRENT WINS** | A defined, schema-driven, contract-versioned pipeline beats an undefined "multi-agent" abstraction. Each stage is testable in isolation; the `runTrace` schema records every stage so failures are debuggable. |
| 10 | **Evaluation / Monitoring** | "evaluation/monitoring (e.g., for hallucination reduction)" | **Dual-gate certification**: 20-case theological safety suite (`tests/safety/test_20_queries.py`) + per-tenant retrieval-eval gold sets with Recall@K / Precision@K / MRR / nDCG@K + Ragas-style LLM judge (`docs/contracts/retrieval-eval-suite.md`); `structlog` with ULID `runId` in `X-Run-Id`; redaction filter; 30-day sensitive-log retention | **CURRENT WINS — DECISIVELY** | The recommendation is a vibe. The current spec is a **CI-blocking certification gate** for every model route, with explicit pass thresholds (`new ≥ baseline − 0.02`) and tenant-confidential gold sets. This is enterprise/clergy-grade governance neither competitor has. |
| 11 | **Fine-tuning** | "Fine-tuning on domain data" | Charter only (Phase 2+: Polytonic-Greek embedding fine-tune benchmarked vs general multilingual baselines) | **EQUAL — current is correctly deferred** | Fine-tuning before you have (a) a stable retrieval baseline, (b) tenant gold sets, and (c) a certify-and-rollback SOP is malpractice. Phase 2 charter is the right sequence. |
| 12 | **Knowledge Graph / Graph RAG** | "Graph RAG or knowledge graphs" | **PAG-RAG (Private Agentic Graph-RAG)** — vector-first Phase 1, graph-augmented Phase 2 (ADR-0006); `graph_entities`, `chunk_entity_mentions`, `lineage_edges` (quotes / references / builds_on / contrasts_with / translation_of / paraphrases / supports / contested_by); approval-gated edges only enter evidence | **CURRENT WINS** | The current plan is **strictly more sophisticated** than generic graph-RAG: edges are typed for patristic discourse (lineage, dispute, translation), approval-gated (no candidate edges in user-facing evidence), and join via `parentChunkId` already populated in Phase 1 chunks. No competitor has this. |

### Where the recommended stack would actively hurt this project

- **LlamaIndex/LangChain** would obscure the very prompt/tool/retrieval boundaries that
  ADR-0004 and ADR-0007 require to be auditable. Closed-corpus discipline + citation
  verification cannot be guaranteed through a framework that controls the loop for you.
- **Pinecone** vendor-locks you against the Phase 4 offline/monastery deployment path
  (`docs/reference/patristic-build-plan.md`). Qdrant + pgvector both run offline.
- **Unstructured.io** drops Polytonic Greek diacritics on scan-quality PDFs. That is a
  product-killing failure mode for patristic sources.

---

## 2. Verdict: Project Potential vs. VulgateAI and Logos

The competitive feature matrix in `docs/reference/patristic-build-plan.md` enumerates the
moats. The decisive moat is **layered**, not single-axis:

### Layer 1 — Existential moat (zero-hallucination by construction)

- **Closed-corpus contract (ADR-0001)** — A5 composes **only** from admitted evidence; no
  training data, no open-web fallback. Material claims that cannot be cited fail closed.
- **Deterministic citation verification (A6)** — 70% quote-overlap rule with
  tenant-tunable threshold. Schema-checked. No-citation answers fail closed.
- **Sensitivity reframing + RED-tier early exit** — hard triggers (self-harm, medical
  emergency, minor protection) block-with-redirect and never reach the model.

**Neither VulgateAI nor Logos has any of this.** Both allow general-knowledge answer paths
and treat citations as a UX feature, not a verification gate. This is the existential moat.

### Layer 2 — Authenticity moat (Orthodox-specific by construction)

- **Polytonic Greek OCR** (Tesseract `grc` + `ell` packs, ADR-0008).
- **Hierarchical heading-boundary chunking** preserves patristic argument structure
  (`docs/contracts/chunking-contract.md`).
- **`father` + `work` + `language` + `sectionPath` metadata** on every chunk
  (`docs/schemas/chunk.schema.json`) → exact-citation UX neither competitor matches.
- **Calendar profile per tenant** (`docs/schemas/calendar-profile.schema.json`):
  independent `fixedFeastCalendar` (julian/revised_julian/gregorian) +
  `paschalion` (julian/gregorian) → real ecclesiastical jurisdiction (OCA / ROCOR /
  GOARCH / Antiochian / Coptic / Romanian / etc.).
- **Answer modes** (`consensus / historical_development / scholarly_dispute /
  institutional_policy / unresolved`) and **`canonical_dispute` sensitivity class** are
  patristic-discourse-native primitives. Logos has none of this; VulgateAI is
  Catholic-aligned.

### Layer 3 — Institutional moat (clergy governance by construction)

- **Approval queues + visibility tiers** (`member / scholar / admin_only / suppressed`)
  built into the chunk schema, not bolted on.
- **Multi-tenant from day one** (ADR-0003): every read/write filters `tenant_id`, every
  cache key includes it, every retrieval enforces `approved=true`.
- **Safe config gating** (T-007): no production launch until founder + Greek reviewer
  sign off `sensitivity_keywords.yaml` + `pastoral_filters.yaml`.
- **No free-form tenant prompt editing** — platform-controlled, founder-locked.

Logos sells to individual users; VulgateAI sells to a single Catholic institution. **Only
this platform is architected for the Orthodox jurisdictional reality** (autocephalous
churches, monastic communities, seminaries, diaspora parishes — each needing isolated,
clergy-governed corpora).

### Layer 4 — Long-term defensibility (network + offline)

- **Phase 3 institutional network**: cross-diocese / cross-monastery corpus sharing under
  policy-hierarchy scoped visibility. First-mover wins permanently in the Orthodox market.
- **Phase 4 offline / monastery deployment**: Athonite manuscript archive partnerships,
  SQLite + embedded Qdrant on-monastery. Neither competitor targets this segment.

### Verdict

**The project plan can beat VulgateAI and Logos on every axis that matters for the
Orthodox market** — provided Phase 1 ships on the contract as written. The contracts and
ADRs are already locked at a discipline level competitors do not approach. **What remains
is execution, not architecture.**

---

## 3. Pre-Phase-1 Optimizations (incorporate **before** T-001 kickoff)

These are low-cost changes to land in the contract layer before any backend/frontend code
is written, so Phase 1 ships them rather than retrofitting. Estimated total: **1–2 days**.

> Each of these touches a canonical contract, ADR, or schema. Per `CLAUDE.md` §6, those
> are High-risk actions requiring approval. **Do not execute O-1 through O-7 without
> founder sign-off.**

### O-1. Lock decision on Qdrant collection topology

**Status:** Open per `docs/contracts/db-schema.md` / approved-decisions-register
"implementer's choice".
**Action:** Pick `shared collection with tenant_id payload filter` (lower ops cost, easier
quotas) vs. `per-tenant collections` (stronger blast-radius isolation), record in
ADR-0013, and amend `vector-store-interface.md` accordingly. **Recommendation:** shared
collection + payload filter for Phase 1 (Railway cost), with a documented migration path
to per-tenant if a tenant requires data-residency isolation.
**Files:** new `docs/adr/0013-qdrant-collection-topology.md`,
amend `docs/contracts/vector-store-interface.md`.

### O-2. Pin OpenAI embedding model exact version + write a re-embed runbook now

**Status:** ADR-0011 says `text-embedding-3-small` but does not pin a snapshot.
**Action:** Add `embeddingModel` to every chunk row + every Qdrant payload, and document
the dual-index + backfill + certify SOP **now** so Phase 2 multilingual upgrade is a
runbook execution, not a design exercise.
**Files:** `docs/contracts/db-schema.md` (add `embedding_model TEXT NOT NULL` to chunks),
`docs/schemas/chunk.schema.json`, new `docs/contracts/embedding-upgrade-sop.md`.

### O-3. Add `jurisdiction` field to `tenants.config` + extend safety taxonomy

**Status:** Calendar profile is per-tenant, but jurisdiction (OCA / ROCOR / GOARCH /
Antiochian / Romanian / Bulgarian / Serbian / Coptic / etc.) is implicit.
**Action:** Add an `ecclesiasticalJurisdiction` enum + free-text override to
`tenant.config`. Extend `institutional_policy` answer mode to consume it. This unblocks
Phase 3 cross-institution network without schema migration later.
**Files:** `docs/schemas/tenant.schema.json`, `AGENTS.md` (Sensitivity And Handling
section).

### O-4. Specify the `scholarly_dispute` UI affordance now

**Status:** Answer mode exists in `answer-mode.schema.json`; UI not specified in T-006.
**Action:** Add to T-006 a wireframe note: when `answerMode === "scholarly_dispute"`,
render side-by-side patristic-source columns with explicit attribution. This is the
single most differentiating UX vs. Logos (which collapses all views into one).
**Files:** `docs/task_cards/phase1/T-006-chat-ui-admin-ui-safety-gate.md`.

### O-5. Promote paraphrase-fuzz harness to a Phase 1 CI gate

**Status:** `test_20_queries_paraphrases.py` is documented as a skeleton, gated on
production env + non-stub config.
**Action:** Promote it to a CI-blocking gate alongside the 20-case suite. Generates 3–5
paraphrases per canonical case via a fixed-seed paraphraser route. Catches the
most-likely real-world safety-bypass: rephrasing pastoral/medical/political queries to
slip past keyword detection.
**Files:** `docs/contracts/safety-config-format.md`,
`tests/safety/test_20_queries_paraphrases.py` (move from stub to required), CI workflow.

### O-6. Add `corpusOrigin` and `digitizationProvenance` to source schema

**Status:** Source schema has `extractionMethod` but no upstream provenance.
**Action:** Add `corpusOrigin` (e.g., `tlg`, `migne_pg`, `migne_pl`,
`goarch_publications`, `oca_publications`, `monastery_archive:<name>`, `tenant_upload`)
and `digitizationProvenance` (manuscript / critical-edition / paperback / web). This is
the foundation for Phase 4 Athonite manuscript partnerships and Phase 3 cross-institution
attribution — adding it now costs nothing; adding it later requires backfill of every chunk.
**Files:** `docs/schemas/source.schema.json`, `docs/contracts/db-schema.md`.

### O-7. Decide answer-streaming UX once and lock the SSE event schema

**Status:** Approved-decisions-register confirms "draft-answer streaming rejected;
progress-only streaming accepted." Good — but the frontend SSE event schema is not yet
in `docs/schemas/`.
**Action:** Add `progress-event.schema.json` so the frontend SSE consumer and backend
emitter share a typed contract. Saves a real bug in T-006.
**Files:** new `docs/schemas/progress-event.schema.json`,
amend `docs/api/openapi.yaml`.

---

## 4. Phase 2 Optimization Charter (defer, but charter now)

These are deliberately NOT pre-Phase-1 work. They are sized here so the Phase 2 kickoff
has a clean charter and no surprises.

| ID | Optimization | Rationale |
|----|--------------|-----------|
| P2-1 | **Embedding bake-off**: `text-embedding-3-large` vs `multilingual-e5-large-instruct` vs custom polytonic-Greek fine-tune. Dual-index + backfill + certify SOP from O-2. | Better Greek + Slavonic + Arabic + Romanian recall. ADR-0006 already commits to this. |
| P2-2 | **Activate `VisionParser`** (LLM-with-vision) for badly degraded scans and manuscripts. | Required for Athonite manuscript partnerships (Phase 4 lead-in). ADR-0008 stub. |
| P2-3 | **Promote PAG-RAG lineage edges from candidate to retrieval-influential**. | ADR-0006 / ADR-0007 already define edge types; Phase 2 activates them in evidence packets. |
| P2-4 | **Real-time corpus ingest** (YouTube transcripts, RSS, webhooks) per `patristic-build-plan.md`. | Living-corpus differentiator vs. Logos / VulgateAI manual-only. |
| P2-5 | **Liturgical-calendar query boosting**: feast-aware retrieval (e.g., questions during Holy Week boost Holy Week sources). | Temporally-aware RAG — no competitor has this. |
| P2-6 | **Patristic Consensus Engine**: synthesize approved lineage chains into a "Fathers in agreement" view. | The marquee Phase 2 product feature; ADR-0006 graph foundation already laid. |
| P2-7 | **Add Church Slavonic, Romanian, Arabic, Russian OCR / embedding coverage** beyond current English + Greek. | Diaspora market expansion. |
| P2-8 | **LangSmith / Phoenix / Arize integration** behind the existing `structlog` + ULID `runId` adapter for distributed tracing once query volume justifies it. | Not needed Phase 1 (run trace + redacted logs are sufficient); becomes useful at multi-tenant scale. |
| P2-9 | **Cohere `rerank-multilingual-v3.0` as a second certified `Reranker`** alongside the local BGE, for tenants willing to pay for higher recall on long-tail polytonic Greek. | ADR-0012 Protocol already supports it. |
| P2-10 | **Bishop-briefing / study-packet export** (`institutional_policy` answer mode → PDF). | Institutional sales lever. |

---

## 5. Go / No-Go Recommendation

**GO on Phase 1, after O-1 through O-7 land in the contract layer (1–2 days).**

Reasoning:

- The current stack is **architecturally superior** to the recommended one for this
  specific problem, by every meaningful criterion. The recommendation is generic; the
  current spec is domain-correct.
- The current stack is **architecturally superior to VulgateAI and Logos** on the four
  decisive layers (zero-hallucination by construction, Orthodox-authenticity by
  construction, clergy-governance by construction, network + offline defensibility).
- The 7 pre-Phase-1 optimizations are all contract-layer changes (schemas, ADRs, task
  cards). None require code. None destabilize the T-001 → T-007 sequence. They prevent
  expensive backfills and retrofits later.
- **What remains is execution.** Phase 1 (T-001 → T-007) is correctly scoped, sequenced,
  and gated. T-007 is the explicit launch blocker (real safety configs from founder +
  Greek-language reviewer).

**Risks to monitor during Phase 1 (not blockers):**

1. **Polytonic Greek OCR quality on real Migne PG scans.** Validate on 10
   randomly-selected real pages during T-002 before approving the parser. If
   `pytesseract` quality is inadequate, activate `VisionParser` from P2-2 ahead of Phase 2.
2. **Retrieval recall on cross-lingual queries.** Phase 1 baseline (3-small) may fall
   below 0.70 Recall@10 on Greek ↔ English; if so, accelerate P2-1.
3. **Founder + Greek-reviewer bandwidth for T-007.** This is the critical-path human task.
   Calendar it before T-001 kickoff.

---

## 6. Critical Files (for the executor reading this analysis)

**Read these first:**

- `AGENTS.md` — always-read coding brief.
- `docs/contracts/code-gen-guide.md` — FastAPI/Next.js scaffold contract.
- `docs/contracts/phase1-implementation-contract.md` — 25-item Phase 1 exit criteria.
- `docs/contracts/scaffold-contract.md` — exact `pyproject.toml` / `package.json`.
- `docs/contracts/db-schema.md` — Postgres DDL.
- `docs/contracts/retrieval-eval-suite.md` — CI gate definition.
- `docs/contracts/quote-overlap-algorithm.md` — A6 verification math.
- All 12 ADRs in `docs/adr/`.
- All 21 schemas in `docs/schemas/`.
- All 7 task cards in `docs/task_cards/phase1/`.

**Files that would be edited during pre-Phase-1 (O-1 → O-7), pending approval:**

- `docs/adr/0013-qdrant-collection-topology.md` (new) — O-1.
- `docs/contracts/vector-store-interface.md` — O-1.
- `docs/contracts/db-schema.md` — O-2, O-6.
- `docs/schemas/chunk.schema.json` — O-2.
- `docs/contracts/embedding-upgrade-sop.md` (new) — O-2.
- `docs/schemas/tenant.schema.json` — O-3.
- `AGENTS.md` — O-3 (Sensitivity And Handling section).
- `docs/task_cards/phase1/T-006-chat-ui-admin-ui-safety-gate.md` — O-4.
- `docs/contracts/safety-config-format.md` — O-5.
- `tests/safety/test_20_queries_paraphrases.py` — O-5.
- `docs/schemas/source.schema.json` — O-6.
- `docs/schemas/progress-event.schema.json` (new) — O-7.
- `docs/api/openapi.yaml` — O-7.

**Reuse-don't-reinvent:**

- Cache-key construction → `docs/contracts/cache-key.md` (already canonical).
- Field naming → `docs/contracts/code-gen-guide.md` (camelCase in HTTP, snake_case in
  DB/Qdrant).
- API error envelope → `docs/schemas/api-error.schema.json` + `error-taxonomy.md`.
- Run trace shape → `docs/schemas/run-trace.schema.json`.

---

## 7. Verification

To verify this analysis end-to-end before kicking off Phase 1:

1. **Stack-comparison sanity check (10 min):** open `docs/contracts/code-gen-guide.md`
   and `docs/contracts/scaffold-contract.md`; confirm every cell in the comparison table
   in §1 matches the actual pinned dependency.
2. **Contract completeness check (20 min):** list `docs/contracts/`, `docs/adr/`,
   `docs/schemas/`, `docs/task_cards/phase1/` and confirm counts (18 / 12 / 21 / 7).
3. **Competitive-feature audit (15 min):** open `docs/reference/patristic-build-plan.md`
   feature comparison table; confirm every "✅ Core" row maps to a real ADR or contract
   in the repo (not just a planning doc).
4. **Pre-Phase-1 dry run (1–2 days, after approval):** execute O-1 through O-7. After
   each, run any existing JSON-schema validation locally (zod generation against
   `docs/schemas/`, `openapi.yaml` lint).
5. **Phase 1 kickoff readiness check:** confirm T-007 reviewer is calendared, founder
   sign-off process is defined, and the stub-baseline safety config startup self-test
   is wired to fail-closed in `APP_ENV='production'`.
6. **Phase 1 itself:** the dual-gate CI (20-case safety suite + retrieval-eval
   regression) is the running verification of every model route, prompt version, and
   retrieval change throughout Phase 1.

When O-1 through O-7 are merged and the T-007 reviewer is calendared, Phase 1 is cleared
for kickoff.
