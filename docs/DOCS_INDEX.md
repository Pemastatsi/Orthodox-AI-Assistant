# Documentation Index

Status: Canonical
Date: 2026-05-02

## Normal Read Order

For coding sessions, read only:

1. `AGENTS.md`
2. `docs/contracts/code-gen-guide.md`
3. the relevant `docs/task_cards/phase1/*.md`
4. directly affected source files
5. failing tests

Read `docs/contracts/`, `docs/adr/`, `docs/api/`, and `docs/schemas/` when the task card points to them. Read `docs/reference/` or `docs/archive/` only to resolve a contradiction or revisit strategy.

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

| Path | Status | Purpose |
|---|---|---|
| `docs/contracts/code-gen-guide.md` | canonical | FastAPI/Next.js architecture and code-gen rules. |
| `docs/contracts/scaffold-contract.md` | canonical | Concrete repository tree, deps, env, Docker, Makefile for T-001. |
| `docs/contracts/phase1-implementation-contract.md` | canonical | Phase 1 implementation behavior + Phase 1→2 exit criteria. |
| `docs/contracts/approved-decisions-register.md` | canonical | Approved decisions extracted from archived drafts. |
| `docs/contracts/auth-context.md` | canonical | Clerk JWT resolution, Principal, multi-org users, webhook auth. |
| `docs/contracts/provider-interface.md` | canonical | LLMProvider Protocol, error taxonomy, streaming, refusals. |
| `docs/contracts/cache-key.md` | canonical | Canonical cache-key recipe with reference test vectors. |
| `docs/contracts/error-taxonomy.md` | canonical | API error codes, HTTP mapping, retryability, user visibility. |
| `docs/contracts/observability.md` | canonical | Structured-log shape, trace propagation, redaction, metrics. |
| `docs/contracts/db-schema.md` | canonical | Postgres DDL + RLS decision; first Alembic migration source. |
| `docs/contracts/api-versioning.md` | canonical | Version formats and deprecation policy. |
| `docs/contracts/quote-overlap-algorithm.md` | canonical | A6 70% rule, normalization, shingles, test vectors. |
| `docs/contracts/safety-config-format.md` | canonical | YAML format for sensitivity keywords and pastoral filters. |
| `docs/contracts/frontend-components.md` | canonical | React component prop/state contracts and routing. |

## Configuration

| Path | Status | Purpose |
|---|---|---|
| `config/sensitivity_keywords.yaml` | contract | A1 keyword detection. Stub format-only rules. |
| `config/pastoral_filters.yaml` | contract | A6 forbidden-phrase regex. Stub format-only rules. |

## API and Schemas

| Path | Status | Purpose |
|---|---|---|
| `docs/api/openapi.yaml` | contract | HTTP API shape with components, errors, runs, admin, webhooks, pagination. |
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
| `docs/schemas/billing-usage.schema.json` | contract | Per-tenant rolling usage row. |
| `docs/schemas/audit-entry.schema.json` | contract | Immutable audit row. Includes `founder_phase2_signoff` action. |
| `docs/schemas/flagged-query.schema.json` | contract | Flagged queries for review and clustering. |
| `docs/schemas/model-route.schema.json` | contract | Certified provider/model/prompt/schema combination. |
| `docs/schemas/run-trace.schema.json` | contract | Full pipeline run trace. |
| `docs/schemas/calendar-profile.schema.json` | contract | Inline calendar profile stored at `tenants.config.calendarProfile`. Drives cache-key `calendarVersion` field. |

## Architecture Decision Records

| Path | Status | Purpose |
|---|---|---|
| `docs/adr/0001-closed-corpus-contract.md` | canonical | Closed-corpus evidence boundary. |
| `docs/adr/0002-confidence-sensitivity-handling.md` | canonical | Confidence, sensitivity, risk flags, and handling split. |
| `docs/adr/0003-multi-tenant-day-one.md` | canonical | Tenant-aware MVP architecture. |
| `docs/adr/0004-model-provider-routing.md` | canonical | Provider/model route certification. |
| `docs/adr/0005-cache-billing-privacy.md` | canonical | Cache, usage metering, and sensitive logs. |
| `docs/adr/0006-pag-rag-lineage-architecture.md` | canonical | Phased PAG-RAG lineage architecture. |
| `docs/adr/0007-query-transformation-boundaries.md` | canonical | No generic query rewriting in Phase 1. |

## Task Cards

| Path | Status | Purpose |
|---|---|---|
| `docs/task_cards/phase1/T-001-scaffold-contracts.md` | contract | Scaffold repo and validate contracts (cites scaffold-contract.md). |
| `docs/task_cards/phase1/T-002-tenant-data-ingestion.md` | contract | Tenant data model and ingestion. |
| `docs/task_cards/phase1/T-003-query-analyzer-retrieval.md` | contract | A1/A2 QueryAnalyzer and A3 retrieval. |
| `docs/task_cards/phase1/T-004-evidence-composer-verifier.md` | contract | A4, A5, and A6. |
| `docs/task_cards/phase1/T-005-cache-logs-billing.md` | contract | Cache, logs, billing counters, privacy. |
| `docs/task_cards/phase1/T-006-admin-chat-safety-gate.md` | contract | Chat UI, admin UI, safety gate. |

## Tests and Fixtures

| Path | Status | Purpose |
|---|---|---|
| `tests/fixtures/corpus/tiny_approved_corpus.json` | contract | Corpus fixture with approved evidence for safety cases requiring it (Orthodox Ethos tenant). |
| `tests/fixtures/corpus/tiny_other_tenant_corpus.json` | contract | Second-tenant fixture for tenant-isolation integration tests; pairs with tiny_approved_corpus.json. |
| `tests/safety/test_20_queries.py` | contract | Canonical 20-query safety expectations (data + structural meta-tests). |
| `backend/tests/safety/test_20_queries_harness.py` | contract (delivered by T-006) | Executes the 20 cases through the live A1–A6 pipeline; required by CI `safety-suite-execution` job. |

## Reference Material

These files are retained for context only. They are not normal coding inputs.

| Path | Status | Notes |
|---|---|---|
| `docs/reference/patristic-build-plan.md` | reference | Long build plan. Canonical contracts override it. |
| `docs/reference/pag_rag_design.html` | reference | Earlier PAG-RAG design exploration. ADR 0006 is the canonical PAG-RAG source. |
| `docs/claude-design-end-state-frontend-prompt.md` | reference | Designer-facing prompt for end-state UI exploration. `docs/contracts/frontend-components.md` is canonical for Phase 1 component contracts. |
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
