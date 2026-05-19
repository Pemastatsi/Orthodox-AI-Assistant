# Documentation Index

Status: Canonical
Date: 2026-05-02

## Normal Read Order

For coding sessions, read only:

1. `AGENTS.md`
2. `docs/contracts/code-gen-guide.md`
3. the relevant `docs/task_cards/phase1/*.md` (Phase 1) or `docs/task_cards/phase2/*.md` (Phase 2)
4. directly affected source files
5. failing tests

Read `docs/contracts/`, `docs/adr/`, `docs/api/`, and `docs/schemas/` when the task card points to them. Read `docs/reference/` or `docs/archive/` only to resolve a contradiction or revisit strategy.

For Phase 2 work, also read `docs/phase2-roadmap.md` for wave ordering and `docs/contracts/artifact-spec-contract.md` for the artifact lifecycle.

## Canonical Files (Repo Root)

| Path | Status | Purpose |
|---|---|---|
| `CLAUDE.md` | canonical | Auto-loaded universal operating standard (safety, privacy, execution policy). |
| `AGENTS.md` | canonical | Always-read coding brief and product semantics. |
| `README.md` | canonical | Short repo map. |
| `CONTRIBUTING.md` | canonical | Working brief for internal contributors and Claude sessions. |
| `SECURITY.md` | canonical | Vulnerability reporting and scope. |
| `LICENSE` | canonical | Placeholder copyright notice. |
| `.gitignore` | canonical | Ignore rules including secrets. |
| `.github/workflows/ci-safety-gate.yml` | canonical | CI safety gate. |
| `docs/DOCS_INDEX.md` | canonical | This file: documentation status and traceability. |

## Contracts (Code-Gen and Implementation)

### Phase 1 Contracts

| Path | Status | Purpose |
|---|---|---|
| `docs/contracts/code-gen-guide.md` | canonical | FastAPI/Next.js architecture and code-gen rules. |
| `docs/contracts/scaffold-contract.md` | canonical | Concrete repository tree, deps, env, Docker, Makefile for T-001. |
| `docs/contracts/phase1-implementation-contract.md` | canonical | Phase 1 implementation behavior + Phase 1→2 exit criteria. |
| `docs/contracts/approved-decisions-register.md` | canonical | Approved decisions extracted from archived drafts. |
| `docs/contracts/auth-context.md` | canonical | Clerk JWT resolution, Principal, multi-org users, webhook auth. |
| `docs/contracts/provider-interface.md` | canonical | LLMProvider Protocol, error taxonomy, streaming, refusals. |
| `docs/contracts/cache-key.md` | canonical | Canonical cache-key recipe with reference test vectors + artifact cache key (Phase 2). |
| `docs/contracts/error-taxonomy.md` | canonical | API error codes, HTTP mapping, retryability, user visibility. |
| `docs/contracts/observability.md` | canonical | Structured-log shape, trace propagation, redaction, metrics. |
| `docs/contracts/db-schema.md` | canonical | Postgres DDL + RLS decision; first Alembic migration source. |
| `docs/contracts/api-versioning.md` | canonical | Version formats and deprecation policy. |
| `docs/contracts/quote-overlap-algorithm.md` | canonical | A6 70% rule, normalization, shingles, test vectors. |
| `docs/contracts/safety-config-format.md` | canonical | YAML format for sensitivity keywords and pastoral filters. |
| `docs/contracts/frontend-components.md` | canonical | React component prop/state contracts and routing (Phase 1 + Phase 2 summary). |

### Phase 2 Contracts

| Path | Status | Purpose |
|---|---|---|
| `docs/contracts/artifact-spec-contract.md` | canonical | Artifact type taxonomy, envelope, lifecycle, caching rules. |
| `docs/contracts/artifact-provider-interface.md` | canonical | ArtifactProvider protocol hierarchy (GraphRenderer, ExportProvider, TTSProvider, etc.). |
| `docs/contracts/rich-output-rendering.md` | canonical | Frontend component contracts for all Phase 2 views. |
| `docs/contracts/export-format-contract.md` | canonical | PDF/DOCX/PPTX format specs, citation footnoting, tenant branding. |
| `docs/contracts/audio-overview-contract.md` | canonical | Two-voice TTS spec, SSML rules, pronunciation coverage gate. |
| `docs/contracts/workflow-orchestration-contract.md` | canonical | Pipeline stages, approval gates, evidence coverage checks, retry, audit. |
| `docs/contracts/multimedia-integration-contract.md` | canonical | Iconography, chant, liturgical calendar, monastery map — sourcing and rules. |
| `docs/contracts/bilingual-rendering-contract.md` | canonical | Greek+English side-by-side with token morphology; MorphologyProvider. |

## Configuration

| Path | Status | Purpose |
|---|---|---|
| `config/sensitivity_keywords.yaml` | contract | A1 keyword detection. Stub format-only rules. |
| `config/pastoral_filters.yaml` | contract | A6 forbidden-phrase regex. Stub format-only rules. |

## API and Schemas

| Path | Status | Purpose |
|---|---|---|
| `docs/api/openapi.yaml` | contract | HTTP API shape with components, errors, runs, admin, webhooks, pagination. |

### Phase 1 Schemas

| Path | Status | Purpose |
|---|---|---|
| `docs/schemas/answer-mode.schema.json` | contract | Answer mode enum. |
| `docs/schemas/classified-query.schema.json` | contract | A1 classification output. |
| `docs/schemas/retrieval-plan.schema.json` | contract | A2 retrieval plan output. |
| `docs/schemas/evidence-packet.schema.json` | contract | A4 evidence admission output. |
| `docs/schemas/verified-response.schema.json` | contract | Final verified response. |
| `docs/schemas/principal.schema.json` | contract | Authenticated request principal. |
| `docs/schemas/api-error.schema.json` | contract | Canonical error envelope. |
| `docs/schemas/tenant.schema.json` | contract | Internal tenant record. |
| `docs/schemas/user.schema.json` | contract | Internal user record. |
| `docs/schemas/source.schema.json` | contract | Tenant corpus source document. |
| `docs/schemas/chunk.schema.json` | contract | Indexed retrievable chunk. |
| `docs/schemas/session.schema.json` | contract | Conversation session for follow-up queries. |
| `docs/schemas/ingest-job.schema.json` | contract | Async ingestion job. |
| `docs/schemas/billing-usage.schema.json` | contract | Per-tenant rolling usage row (extended in Phase 2 with artifact + audio meters). |
| `docs/schemas/audit-entry.schema.json` | contract | Immutable audit row. Includes `founder_phase2_signoff` and artifact lifecycle actions. |
| `docs/schemas/flagged-query.schema.json` | contract | Flagged queries for review and clustering. |
| `docs/schemas/model-route.schema.json` | contract | Certified provider/model/prompt/schema combination (extended for artifact-namespace purposes). |
| `docs/schemas/run-trace.schema.json` | contract | Full pipeline run trace. |
| `docs/schemas/calendar-profile.schema.json` | contract | Inline calendar profile stored at `tenants.config.calendarProfile`. |

### Phase 2 Schemas

| Path | Status | Purpose |
|---|---|---|
| `docs/schemas/artifact.schema.json` | contract | Base artifact envelope (all Phase 2 artifact types extend this). |
| `docs/schemas/artifact-request.schema.json` | contract | Artifact generation request. |
| `docs/schemas/lineage-graph.schema.json` | contract | Patristic Lineage Graph data structure. |
| `docs/schemas/council-timeline.schema.json` | contract | Council Decision Timeline. |
| `docs/schemas/citation-network.schema.json` | contract | Father-cites-father citation network. |
| `docs/schemas/dispute-map.schema.json` | contract | Theological position comparison with evidence anchors. |
| `docs/schemas/manuscript-witness-tree.schema.json` | contract | Textual transmission lineage tree. |
| `docs/schemas/mind-map.schema.json` | contract | Hierarchical outline derived from verified response. |
| `docs/schemas/study-packet.schema.json` | contract | Evidence-grounded study bundle. |
| `docs/schemas/audio-overview.schema.json` | contract | Two-voice TTS audio overview. |
| `docs/schemas/slide-deck.schema.json` | contract | Presentation slide deck. |
| `docs/schemas/sermon-outline.schema.json` | contract | Sermon/homily outline with patristic commentary. |
| `docs/schemas/bilingual-passage.schema.json` | contract | Greek+English passage with token morphology. |
| `docs/schemas/iconographic-card.schema.json` | contract | Icon reference card from curated licensed set. |
| `docs/schemas/liturgical-context.schema.json` | contract | Liturgical calendar context for a given date. |
| `docs/schemas/geographic-overlay.schema.json` | contract | Map artifact with ecclesiastical site overlays. |

## Architecture Decision Records

### Phase 1 ADRs (locked)

| Path | Status | Purpose |
|---|---|---|
| `docs/adr/0001-closed-corpus-contract.md` | canonical | Closed-corpus evidence boundary. |
| `docs/adr/0002-confidence-sensitivity-handling.md` | canonical | Confidence, sensitivity, risk flags, and handling split. |
| `docs/adr/0003-multi-tenant-day-one.md` | canonical | Tenant-aware MVP architecture. |
| `docs/adr/0004-model-provider-routing.md` | canonical | Provider/model route certification. |
| `docs/adr/0005-cache-billing-privacy.md` | canonical | Cache, usage metering, and sensitive logs. |
| `docs/adr/0006-pag-rag-lineage-architecture.md` | canonical | Phased PAG-RAG lineage architecture. |
| `docs/adr/0007-query-transformation-boundaries.md` | canonical | No generic query rewriting in Phase 1. |
| `docs/adr/0008-pdf-parser-strategy.md` | canonical | Hybrid PDF parsing (born-digital + scanned). |
| `docs/adr/0009-chunking-strategy.md` | canonical | Hierarchical heading-boundary chunking strategy. |
| `docs/adr/0010-vector-store-interface.md` | canonical | VectorStore interface pattern. |
| `docs/adr/0011-hybrid-retrieval.md` | canonical | Hybrid dense + sparse (BM25) retrieval. |
| `docs/adr/0012-reranker-selection.md` | canonical | Cross-encoder reranking (BGE local, no LLM-pointwise). |

### Phase 2 ADRs

| Path | Status | Purpose |
|---|---|---|
| `docs/adr/0013-rich-output-format-strategy.md` | canonical | Five-tier rich-output model; closed-corpus provenance extends to all artifacts. |
| `docs/adr/0014-artifact-provider-abstraction.md` | canonical | ArtifactProvider protocol hierarchy; certified routes per artifact category. |
| `docs/adr/0015-multi-meter-billing.md` | canonical | Three Stripe meters; feature parity across tiers; EUR pricing. |
| `docs/adr/0016-workflow-approval-gates.md` | canonical | Approval lifecycle for high-stakes generated documents. |

## Task Cards

### Phase 1

| Path | Status | Purpose |
|---|---|---|
| `docs/task_cards/phase1/T-001-scaffold-contracts.md` | contract | Scaffold repo and validate contracts (cites scaffold-contract.md). |
| `docs/task_cards/phase1/T-002-tenant-data-ingestion.md` | contract | Tenant data model and ingestion. |
| `docs/task_cards/phase1/T-003-query-analyzer-retrieval.md` | contract | A1/A2 QueryAnalyzer and A3 retrieval. |
| `docs/task_cards/phase1/T-004-evidence-composer-verifier.md` | contract | A4, A5, and A6. |
| `docs/task_cards/phase1/T-005-cache-logs-billing.md` | contract | Cache, logs, billing counters, privacy. |
| `docs/task_cards/phase1/T-006-admin-chat-safety-gate.md` | contract | Chat UI, admin UI, safety gate. |
| `docs/task_cards/phase1/T-007-real-safety-configs.md` | contract | Real (non-stub) safety config delivery; founder + Greek-language reviewer ownership. Required by exit criterion #9. |

### Phase 2 — Wave 2.0 (Foundation)

| Path | Status | Purpose |
|---|---|---|
| `docs/task_cards/phase2/T-101-rich-text-rendering.md` | contract | Markdown + Mermaid + rich text in AnswerPanel. |
| `docs/task_cards/phase2/T-102-export-foundation.md` | contract | PDF/DOCX export and ExportProvider infrastructure. |
| `docs/task_cards/phase2/T-103-artifact-provider-abstraction.md` | contract | ArtifactProvider protocol registry and certification. |
| `docs/task_cards/phase2/T-104-study-packet-workflow.md` | contract | Study Packet (first LLM-composed document). |
| `docs/task_cards/phase2/T-105-patristic-lineage-graph.md` | contract | Patristic Lineage Graph (platform unique differentiator). |
| `docs/task_cards/phase2/T-106-audio-overview.md` | contract | Two-voice TTS audio overview with citation timestamps. |
| `docs/task_cards/phase2/T-107-multi-meter-billing.md` | contract | Multi-meter billing (artifact + audio meters). |

### Phase 2 — Wave 2.1 (Visual Depth)

| Path | Status | Purpose |
|---|---|---|
| `docs/task_cards/phase2/T-108-council-timeline.md` | contract | Council Decision Timeline (deterministic). |
| `docs/task_cards/phase2/T-109-dispute-map.md` | contract | Theological Dispute Map (LLM-assisted). |
| `docs/task_cards/phase2/T-110-citation-network-graph.md` | contract | Father-cites-father Citation Network (deterministic). |
| `docs/task_cards/phase2/T-111-manuscript-witness-tree.md` | contract | Manuscript Witness Tree (LLM-assisted). |
| `docs/task_cards/phase2/T-112-slide-deck-export.md` | contract | Slide Deck (PPTX + Marp). |
| `docs/task_cards/phase2/T-113-sermon-homily-builder.md` | contract | Sermon/Homily Outline Builder. |
| `docs/task_cards/phase2/T-114-mind-map-view.md` | contract | Mind Map / Outline View (deterministic). |

### Phase 2 — Wave 2.2 (Orthodox-Unique Multimedia)

| Path | Status | Purpose |
|---|---|---|
| `docs/task_cards/phase2/T-115-bilingual-side-by-side.md` | contract | Greek+English with token morphology. |
| `docs/task_cards/phase2/T-116-liturgical-calendar-overlay.md` | contract | Liturgical Calendar Overlay (deterministic algorithm). |
| `docs/task_cards/phase2/T-117-iconographic-reference-cards.md` | contract | Iconographic Reference Cards (curated licensed set). |
| `docs/task_cards/phase2/T-118-byzantine-chant-integration.md` | contract | Byzantine Chant integration (curated licensed audio). |
| `docs/task_cards/phase2/T-119-holy-land-monastery-map.md` | contract | Holy Land + Monastery Map (self-hosted tiles). |
| `docs/task_cards/phase2/T-120-disputation-simulator.md` | contract | Disputation Simulator (reuses Q&A pipeline). |

### Phase 2 — Wave 2.3 (Approval-Gated Workflow Library)

| Path | Status | Purpose |
|---|---|---|
| `docs/task_cards/phase2/T-121-bishop-briefing-workflow.md` | contract | Bishop Briefing (establishes approval UI). |
| `docs/task_cards/phase2/T-122-syllabus-bundle-workflow.md` | contract | Syllabus Bundle for seminary use. |
| `docs/task_cards/phase2/T-123-catechism-lesson-plan-workflow.md` | contract | Catechism Lesson Plan for adult inquirers. |
| `docs/task_cards/phase2/T-124-parish-bulletin-workflow.md` | contract | Parish Bulletin Insert (A5 PDF). |
| `docs/task_cards/phase2/T-125-feast-day-bundle-workflow.md` | contract | Feast-Day Bundle with multimedia cross-refs. |

## Tests and Fixtures

| Path | Status | Purpose |
|---|---|---|
| `tests/fixtures/corpus/tiny_approved_corpus.json` | contract | Corpus fixture with approved evidence for safety cases requiring it (Orthodox Ethos tenant). |
| `tests/fixtures/corpus/tiny_other_tenant_corpus.json` | contract | Second-tenant fixture for tenant-isolation integration tests; pairs with tiny_approved_corpus.json. |
| `tests/safety/test_20_queries.py` | contract | Canonical 20-query safety expectations (data + structural meta-tests + canonical-text substring inventory for cases 6/10/12/17/20). |
| `tests/safety/test_20_queries_paraphrases.py` | contract (skeleton, content delivered by T-007) | Paraphrase fuzz harness; gated on production + non-stub configs. |
| `tests/integration/test_corpus.py` | contract (skeleton, body delivered by T-002) | Encodes the chunks⇒sources approval invariant. |
| `tests/integration/test_tenant_isolation.py` | contract (skeleton, body delivered by T-005) | Owner of Phase 1 → 2 exit criterion #5 (tenant isolation invariant). |
| `tests/unit/test_quote_overlap.py` | contract (skeleton, body delivered by T-004) | Asserts quote-overlap V1–V6 vectors within ±0.01. |
| `tests/unit/test_cache_key.py` | contract (skeleton, body delivered by T-005) | Asserts cache-key V1–V4 vectors (literal sha256 + from-input-dict). |
| `scripts/exit_criteria_dashboard.py` | contract (skeleton, body delivered with Phase-2-exit dashboard work) | Phase 1 mechanism for tracking the 9 exit criteria; replaces the deferred Prometheus exporter. |
| `backend/tests/safety/test_20_queries_harness.py` | contract (delivered by T-006) | Executes the 20 cases through the live A1–A6 pipeline; required by CI `safety-suite-execution` job. |

## Phase 2 Roadmap

| Path | Status | Purpose |
|---|---|---|
| `docs/phase2-roadmap.md` | canonical | Wave ordering, dependencies, pricing tier map, Phase 2→3 exit criteria. |

## Reference Material

These files are retained for context only. They are not normal coding inputs.

| Path | Status | Notes |
|---|---|---|
| `docs/reference/patristic-build-plan.md` | reference | Long build plan. Canonical contracts override it. |
| `docs/reference/pag_rag_design.html` | reference | Earlier PAG-RAG design exploration. ADR 0006 is the canonical PAG-RAG source. |
| `docs/claude-design-end-state-frontend-prompt.md` | superseded | Historical design exploration. Superseded 2026-05-19 by ADRs 0013–0016, Phase 2 contracts, and Phase 2 task cards. Deprecation header added to the file. |
| `docs/reference/prd-patristic-library-assistant-v1.1.pdf` | reference | Original PRD. Some MVP guidance is superseded. |
| `docs/reference/patristic_agent_architecture_spec_v3_build_ready.pdf` | reference | Earlier agent architecture draft. Phase order is superseded. |
| `docs/reference/patristic_engineering_spec.pdf` | reference | Future feature roadmap. |
| `docs/reference/patristic_strategic_features.pdf` | reference | Strategic feature context. |
| `docs/reference/UI_Build_Plan.pdf` | reference | UI ideas. MVP prompt editor/study packet guidance is superseded. |

## Archive

These files are superseded planning drafts. They have headers warning future agents not to use them as active instructions.

| Path | Status | Replaced By |
|---|---|---|
| `docs/archive/BLUEPRINT_CLARIFICATIONS.md` | superseded | `AGENTS.md`, ADRs, schemas, task cards, tests. |
| `docs/archive/BLUEPRINT_TO_CODE_NEXT_STEPS.md` | superseded | This contract pack. |
| `docs/archive/FEASIBILITY_AND_TOKEN_PLAN.md` | superseded | `AGENTS.md`, ADR 0004, ADR 0005, task cards. |
| `docs/archive/PROJECT_FEASIBILITY_REVIEW_2026-04-25.md` | superseded | `AGENTS.md`, ADRs, contracts, task cards. |

## Traceability

| Archived or Reference Source | Extracted Canonical Destinations |
|---|---|
| Blueprint clarifications | `AGENTS.md`, `docs/contracts/approved-decisions-register.md`, ADR 0002, ADR 0003, ADR 0005, ADR 0006, ADR 0007, schemas, safety tests. |
| Blueprint-to-code readiness plan | `AGENTS.md`, this index, contracts, ADR 0001-0007, OpenAPI, schemas, task cards. |
| Feasibility and token plan | `AGENTS.md`, ADR 0004, ADR 0005, task cards T-003 to T-005. |
| Project feasibility review | `AGENTS.md`, ADR 0001-0005, Phase 1 contract, safety tests. |
| Complete build plan | `AGENTS.md`, Phase 1 contract, OpenAPI, schemas, task cards. |
| Original PRD PDF | `AGENTS.md`, ADR 0001, ADR 0003, OpenAPI, schemas. |
| Agent architecture PDF | `AGENTS.md`, Phase 1 contract, ADR 0004, task cards T-003 and T-004. |
| UI build plan PDF | Task card T-006; superseded where it conflicts with no free-form prompt editing and no MVP study packets. |
| `pag_rag_design.html` | ADR 0006, code-gen-guide.md. |

## Resolved Contradictions

- Phase 1 is tenant-aware from day 1, even with one initial tenant.
- Tenants do not edit free-form base prompts in MVP.
- Study packets are not shipped in MVP.
- A4 evidence packaging is deterministic in MVP.
- Phase 1 performs no generic LLM query rewriting or synonym expansion.
- Draft answer text is not streamed before A6 verification.
- PDFs are reference-only and never override canonical contracts.
- CLAUDE.md is the universal policy spine; FastAPI/Next.js code-gen rules live in `docs/contracts/code-gen-guide.md`.
- App-layer tenant scoping is the Phase 1 default; Postgres RLS is deferred to a Phase 2 ADR.
- `calendarProfile` is an inline object on `tenants.config`, not a referenced id; the cache-key path `tenants.config.calendarProfile.version` is satisfied without a join. Schema: `docs/schemas/calendar-profile.schema.json` (added 2026-05-02).
- Embeddings are obtained through the `LLMProvider.embed_texts` method; no direct provider SDK calls outside `app/adapters/providers/`.
- Phase 1 has no automatic cross-provider fallback on `provider_unavailable`. Codified in ADR 0004.
- Self-harm and medical-emergency bounded fallbacks are platform-fixed text (988 / local emergency redirect); never tenant-overridable. Other bounded fallbacks accept a tenant `disclaimerTemplateId` override.
- Only `role='owner'` may PATCH `model_routes.certification_status` to `certified`. Codified in ADR 0004.
- Founder Phase-2 sign-off is recorded as an `audit_entries` row with `action='founder_phase2_signoff'` and a JSON checklist in `details`.
- Phase-1→2 exit criterion #9 (added 2026-05-02): real safety-config rules approved by founder + Greek-language reviewer; CI startup test fails when stub baseline is still in place under `APP_ENV='production'`.
- Cache-key V3 SHA-256 corrected on 2026-05-02 to match the documented canonical JSON; V4 added for calendar-profile bumps.

### Audit Response — Phase 1 Pre-Implementation Audit (2026-05-04)

The 2026-05-04 pre-implementation audit identified 34 findings (F-01 through F-34). All resolutions land on branch `audit/phase1-pre-t001-fixes`. Status of each finding (✅ resolved · ➤ already in original commit · 📋 task-card workstream):

- ✅ **F-01 (P0):** `corpusVersion` declared as system-managed string at `tenant.schema.json#/properties/config/properties/corpusVersion`; `db-schema.md` documents the path and adds Cross-Table Invariant #6; `openapi.yaml GET /tenant/config` surfaces the field as read-only. Cache-key recipe references now resolve.
- ✅ **F-02 (P1):** `embeddingDimension` added to `chunk.schema.json#/required`.
- ✅ **F-03 (P1):** `actorRole` added to `audit-entry.schema.json#/required`.
- ✅ **F-04 (P1):** `/runs/{runId}` per-user filter rule documented in `auth-context.md`, `frontend-components.md`, and the OpenAPI description; cross-user fetch returns 404 not 403 to avoid runId existence disclosure.
- ✅ **F-05 (P1):** `phase1-implementation-contract.md` defines the 409 `corpus_empty` (setup error) vs 200 `insufficient_evidence` (query-time evidence gap) boundary.
- ✅ **F-06 (P1):** `text/event-stream` removed from `openapi.yaml /query`; SSE event grammar (`progress` / `done` / `error`) documented out-of-band in `code-gen-guide.md §Server-Sent Events (SSE) for /query progress`. Two pre-existing OpenAPI 3.1 `nullable: true` violations on `disclaimerTemplateId` fixed alongside; `redocly lint` exits 0.
- ➤ **F-07 (P2):** ADR 0004 Interface section now points to `provider-interface.md` as the authoritative source.
- ✅ **F-08 (P2):** `ACTIVE_MODEL_ROUTE_VERIFIER` added to `.env.example` (empty default; absence disables A6 judge cleanly).
- ✅ **F-09 (P2):** `QuotaExceeded` response component + 402 wiring on `/query` and `/ingest` in OpenAPI.
- ➤ **F-10 (P2):** Multi-org user model already documented in `auth-context.md`; no audit change needed.
- ✅ **F-11 (P2):** `clerkUserId` added to `principal.schema.json#/required`.
- 📋 **F-12 (P1):** `tests/integration/test_corpus.py` skeleton created with `test_chunk_approval_requires_source_approval` and `test_source_un_approval_cascades_or_rejects`; T-002 acceptance lists these tests.
- 📋 **F-13 (P1):** `tests/integration/test_tenant_isolation.py` skeleton created with 6 tests covering A3 retrieval, A4 admission, citations, cache keys, run-trace stages, and `/admin/queries`; T-005 acceptance lists this file.
- 📋 **F-14 (P2):** `tests/unit/test_quote_overlap.py` skeleton parametrized over V1–V6 vectors; T-004 acceptance lists ±0.01 tolerance.
- 📋 **F-15 (P3):** `tests/unit/test_cache_key.py` skeleton parametrized over V1–V4 vectors with literal SHA-256 + from-input-dict assertions; logs Python version on failure for V3 Greek casefold regression debugging.
- 📋 **F-16 (P1):** New task card `T-007-real-safety-configs.md` opens the non-coding workstream owned by the founder + a named Greek-language reviewer; placeholders in the card MUST be filled before work begins. Required by exit criterion #9.
- ✅ **F-17 (P1):** Appendix A of `phase1-implementation-contract.md` defines canonical bounded-fallback texts for cases 6, 10, 12, 17, 20 (each keyed by case class + schemaVersion); `tests/safety/test_20_queries.py` carries `CANONICAL_TEXT_SUBSTRINGS` matching the appendix.
- ✅ **F-18 (P2):** Run-trace persistence is unconditional (every served request, including hard-safety bypass, mints a runId and persists a minimal `run_traces` row); `BoundedFallbackResponse` now requires `runId`; `observability.md` documents the rule.
- 📋 **F-19 (P2):** `tests/safety/test_20_queries_paraphrases.py` skeleton; paraphrase content delivered by T-007. `safety-config-format.md §Paraphrase Coverage` documents the gating rule.
- ✅ **F-21 (P2):** `observability.md` redaction rules now explicitly cover `stages[].notes`; `run-trace.schema.json` constrains the field to `maxLength: 256` with a description prohibiting raw text.
- ✅ **F-22 (P3):** Prometheus exporter aspiration removed from `observability.md` and deferred to Phase 2; `scripts/exit_criteria_dashboard.py` skeleton is the Phase 1 mechanism for tracking the 9 exit criteria.
- 📋 **F-23 (P1):** Each Phase 1 task card (T-002 through T-005) now lists a focused E2E integration test in acceptance, so the pipeline gets exercised at every milestone instead of waiting for T-006.
- ✅ **F-24 (P2):** `web/lib/i18n/errors.en.json` added to `scaffold-contract.md` repo tree and T-001 acceptance criteria.
- ✅ **F-25 (P2):** `CHECK (~ '^sha256:[0-9a-f]{64}$')` constraints on `chunks.chunk_hash` and `sources.source_hash` in `db-schema.md`.
- ✅ **F-26 (P3):** Redocly CLI pinned to exact `@redocly/cli@1.34.3` in `ci-safety-gate.yml`; `redocly bundle` step added before `lint` so any broken relative `$ref` fails the step rather than silently passing.
- ✅ **F-27 (P2):** `scaffold-contract.md` clarifies Qdrant is a Railway custom-Docker service (not a managed plugin); `QDRANT_API_KEY` added to `.env.example`.
- ✅ **F-28 (P2):** ADR 0005 documents Phase 1 application-level envelope encryption (AES-256-GCM, key in `SENSITIVE_LOG_DATA_KEY_BASE64`, key_version-tagged ciphertext); env var renamed in `scaffold-contract.md`. Phase 2 KMS migration is a tracked ticket.
- ✅ **F-29 (P3):** `/webhooks/make` returns 501 with `x-phase: deferred-phase-2`; `MAKE_WEBHOOK_SECRET` comment updated to note the deferral.
- ✅ **F-30 (P2):** Backend always-redacts on `/admin/queries` and `/admin/flagged`; raw view requires a separate `GET /admin/queries/{runId}/raw` endpoint with the `admin:raw_sensitive:read` scope (admin role only); each call writes `audit_entries` with `action='raw_sensitive_view'`.
- ✅ **F-31 (P3):** `owner` role row in the auth-context table now grants `model_route:certify`; `PATCH /admin/model-routes/{routeId}/certify` endpoint added to OpenAPI requiring that scope.
- ✅ **F-32 (P3):** `db-schema.md` carries a rationale paragraph for the `flagged_queries` vs `raw_sensitive_logs` split.
- ✅ **F-33 (P3):** `code-gen-guide.md` notes that A1 and A2 are a single physical LLM call, with file-split rationale and an ADR gate on consolidation.
- ✅ **F-34 (P3):** `scaffold-contract.md` carries a "Phase 2 Deferrals" section noting the six `ACTIVE_MODEL_ROUTE_*` vars are individually pinned for Phase 1 simplicity and may consolidate into a `system_config` table in Phase 2.
