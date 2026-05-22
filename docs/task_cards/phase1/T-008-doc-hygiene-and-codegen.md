# T-008: Documentation Hygiene + Codegen Bring-Forward (v1)

## Goal

Land every documentation-level change identified by the 2026-05-22 frontier
meta-evaluation report, plus four gold-standard upgrades (GS-1 Postgres RLS,
GS-2 normalization cross-link, GS-3 prompts-as-code, GS-4 latency-threshold
circuit breaker), so that the contract pack is internally consistent and the
eventual coding sessions for T-001–T-006 have unambiguous acceptance criteria
for every code-bearing recommendation.

T-008 is a **documentation-only** task card. No application code, scripts,
schemas-as-code, or CI workflow files are modified by this card. Code-bearing
items are captured here as **amendment blocks against existing task cards
T-001..T-006** so that future coding sessions can pick them up without
re-deriving design.

## Required Reads

- [`AGENTS.md`](../../../AGENTS.md) — invariants every amendment must preserve (closed-corpus, tenant isolation, citation verification, provider abstraction, safety-suite gating, no LLM rewriting, no token streaming before A6).
- [`CLAUDE.md`](../../../CLAUDE.md) — §6 (contracts and ADR amendments are approval-required).
- [`docs/DOCS_INDEX.md`](../../DOCS_INDEX.md) — the canonical index that T-008 brings back into sync with disk.
- [`docs/contracts/phase1-implementation-contract.md`](../../contracts/phase1-implementation-contract.md) — §Exit Criteria (none of T-008's amendments may weaken these).
- The 2026-05-22 evaluation report (received as uploaded HTML) — REC-001 through REC-025 and the four GS items.

## Owners

- **Maintainer:** Claude Code session on branch `claude/gallant-dirac-kKQfI`.
- **Founder (out-of-band):** T-007 ownership block (see §Open Blockers below).

## Files In Scope (this card only — documentation)

### Amended (existing docs)

| File | Change | Originating REC / GS |
|---|---|---|
| `docs/DOCS_INDEX.md` | Add ADRs 0008–0013; add 5 missing contracts; add 3 missing schemas; promote `approved-decisions-register.md` in Normal Read Order | REC-001 |
| `docs/contracts/code-gen-guide.md` §12 | Replace stale `ms-marco-MiniLM-L-6-v2`; reframe Phase-2 framing to Phase-1 reality per ADR-0011 / ADR-0012; cross-link `scored-chunk.schema.json` | REC-002 |
| `docs/contracts/vector-store-interface.md` §Concrete Implementations | Reserve TurbopufferStore (Phase 2 conditional) paragraph | REC-007 |
| `docs/adr/0007-query-transformation-boundaries.md` | One-line clarifying note distinguishing chunk-side ingestion from query-side rewriting | R-1 mitigation |
| `docs/adr/0009-chunking-strategy.md` | Add Step 4 "Contextual prefix" (ingestion-time, 50–100 tokens); add late-chunking section gated on REC-008 | REC-005, REC-014 |
| `docs/contracts/chunking-contract.md` | Add contextual prefix step to §Algorithm; storage option | REC-005 |
| `docs/contracts/embedding-upgrade-sop.md` | Note Contextual Retrieval prefix as embedding-input contract; add REC-008 timeline; add late-chunking gating | REC-005, REC-008, REC-014 |
| `docs/schemas/chunk.schema.json` | Add optional `contextPrefix: string` field (≤200 chars, nullable) | REC-005 |
| `docs/contracts/approved-decisions-register.md` | D-MDL-001: add Haiku 4.5 as proposed `query_analyzer` + `verifier_judge`; Sonnet 4.6 → experiment fallback. New D-MDL-002 `context_prefix` → Haiku 4.5. New D-MDL-003 `edge_extraction` → Haiku 4.5. Mark all three proposed pending T-006 + retrieval-eval. Decision 6 (prompt versioning) amended to note GS-3 structural piece is Phase 1 | REC-006, REC-013, GS-3 |
| `docs/adr/0008-pdf-parser-strategy.md` | Add `LogiosParser` as alternate route; vision-LLM Phase-2 fallback with per-tenant egress flag; one-line cross-link to `quote-overlap-algorithm.md` (GS-2) | REC-012, GS-2 |
| `docs/contracts/parser-interface.md` | Note Logios as additional Parser implementation; ParsedBlock translation | REC-012 |
| `docs/adr/0006-pag-rag-lineage-architecture.md` | Pull forward Phase-1 candidate-edge emission at ingestion; edges remain candidate-only | REC-013 |
| `docs/contracts/db-schema.md` | Add `graph_candidates` DDL spec (table shape only); amend L10–11 to point at new ADR-0016 (Postgres RLS) | REC-013, GS-1 |
| `docs/adr/0011-hybrid-retrieval.md` | Add optional 3rd signal (ColBERT) behind `RetrievalPlan.useLateInteraction` flag default false, gated on REC-008 | REC-015 |
| `docs/adr/0012-reranker-selection.md` | Note `CohereRerankerAdapter` as managed Greek-stress fallback; cert gated on retrieval-eval | REC-016 |
| `docs/contracts/provider-interface.md` | §JSON Mode: `cache_control` hook for A5; §Outage Handling: cross-reference ADR-0014; §Batch: gate by `purpose='retrieval_eval_judge'` | REC-011, REC-017, REC-020 |
| `docs/contracts/cache-key.md` | Extend recipe to include `model_id + system_hash + chunk_id_set + corpusVersion` | REC-011 |
| `docs/contracts/observability.md` | Add OpenTelemetry section — OTel SDK + GenAI semconv; `runId` → `trace_id`; redaction extends to OTel span processor | REC-010 |
| `docs/contracts/retrieval-eval-suite.md` | Note DeepEval as RAGAS-metric complement; judge stays internal `retrieval_eval_judge` route | REC-019 |
| `docs/adr/0005-cache-billing-privacy.md` | Egress amendment — Modal-hosted reranker receives chunk text; Cohere Rerank under same banner | REC-016, REC-018 |
| `docs/adr/0004-model-provider-routing.md` | Route certification protocol now covers prompt-template version changes under `/prompts/` | GS-3 |

### Newly created

| File | Purpose | Originating REC / GS |
|---|---|---|
| `docs/task_cards/phase1/T-008-doc-hygiene-and-codegen.md` | This card | meta |
| `docs/task_cards/phase1/T-009-embedding-upgrade.md` | Dual-index BGE-M3 + text-embedding-3-large benchmark; sequencing for REC-014 (late chunking) and REC-015 (ColBERT); Modal Llama-3-70B A5 peer certification block | REC-008, REC-014, REC-015, GS-4 |
| `docs/task_cards/phase2/T-2XX-vector-store-swap-evaluation.md` | Phase-2 evaluation of Turbopuffer / pgvector+ParadeDB at trigger conditions | REC-022 |
| `docs/task_cards/phase2/T-2XX-regional-tenancy.md` | Phase-2 regional pinning design, gated by first EU customer | REC-023 |
| `docs/task_cards/phase2/T-2XX-phase2-platform-bundle.md` | Phase-2 bundle: Valkey + WorkOS + Langfuse self-host + judge dogfooding | REC-025 |
| `docs/adr/0014-cross-provider-failover.md` | Cross-provider failover ADR (certified peer only; refusals never trigger; 5xx/network OR latency-threshold breach trigger; embeddings excluded). Latency thresholds tunable per `ModelRoute` | REC-017, GS-4 |
| `docs/adr/0015-regional-tenancy.md` | Regional pinning options (Railway region / Cloud Run multi-region / Fly); JWT region claim | REC-023 |
| `docs/adr/0016-postgres-rls.md` | Pull Postgres RLS forward to Phase 1; FastAPI `SET LOCAL app.current_tenant_id` dependency; `BYPASSRLS` roles for migrations, seeders, retention; mandatory cross-tenant integration test | GS-1 |
| `docs/contracts/prompt-management.md` | `/prompts/` directory layout; `prompt_id` + `prompt_version` on every `ModelRoute` invocation and `RunTrace` entry; CI gate runs safety-suite + retrieval-eval on any `/prompts/` change | GS-3 |
| `docs/glossary.md` | Canonical terms (A1–A6, EvidencePacket, RetrievalPlan, ScoredChunk, ChunkPayload, ModelRoute, RunTrace, BoundedFallbackResponse, ecclesiasticalJurisdiction, calendarProfile, corpusVersion, etc.) | REC-021 |
| `docs/architecture/pipeline.md` | A1–A6 pipeline as Mermaid diagram + inputs/outputs table (SVG export deferred to design phase) | REC-021 |
| `docs/architecture/schema-to-code-map.md` | Manual placeholder describing the eventual generated mapping; will be auto-generated once REC-009 codegen lands | REC-021 |
| `docs/runbooks/frontier-sync.md` | Quarterly process — re-run retrieval-eval against current routes; check 2026/2027 benchmarks; produce one-page diff + at most one ADR amendment | REC-024 |

## Code-Deferred Items (acceptance criteria for future T-001..T-006 sessions)

These items are NOT executed by T-008. T-008 ensures each item has an
unambiguous design in the documentation set above. The acceptance criteria
below are duplicated into the relevant existing task card's §Acceptance
Criteria block at the point the file is opened for code work.

### Amendments to T-001 (scaffold)

- **REC-003 doc-drift checker** — add `scripts/check_docs_index.py` that diffs `docs/adr/`, `docs/contracts/`, `docs/schemas/` filesystem against `docs/DOCS_INDEX.md` tables; wire into the `contracts` job in `.github/workflows/ci-safety-gate.yml`. CI fails when a file exists on disk without an index row OR an index row points at a missing file.
- **REC-009 schema-to-code automation** — add three generators behind a single `make codegen` target: `datamodel-code-generator` (Pydantic v2 → `backend/app/domain/models/_generated/`), `openapi-typescript` (`web/lib/api-client.generated.ts`), `json-schema-to-typescript` or `zod-from-json-schema` (`web/lib/schemas/_generated/`). Add `make codegen-check` that fails if generated artifacts drift from schemas; wire into `contracts` job. Generated dirs added to `.gitattributes` as `linguist-generated=true`.
- **GS-1 Postgres RLS** — Alembic migration enables `ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` on every multi-tenant table; creates `tenant_isolation_policy` keyed off `current_setting('app.current_tenant_id', true)`; reserves `BYPASSRLS` to a dedicated `app_admin` role used only by migrations, seeders, and the audited retention worker. FastAPI dependency `set_tenant_guc(principal)` sets `SET LOCAL app.current_tenant_id` at the start of every request transaction. Integration test: `tests/integration/test_rls_zero_results.py` — a `SELECT` from any multi-tenant table without the GUC set must return zero rows (not raise; RLS fails closed by design).
- **GS-3 prompts-as-code bootstrap** — create `/prompts/` directory layout per `docs/contracts/prompt-management.md`; reserve `{stage}/{language}/{version}.j2` (or `.yaml`) path scheme; integrate `prompt_id` + `prompt_version` fields into the `ModelRoute` Pydantic model and `RunTrace` payload schema (per the updated `docs/schemas/`); CI gate that runs safety-suite + retrieval-eval whenever any file under `/prompts/` changes (uses `git diff --name-only` against base).

### Amendments to T-002 (parser + ingestion)

- **REC-005 Contextual Retrieval at ingestion** — at ingestion, after chunking and before embedding, call a `ModelRoute` with `purpose='context_prefix'` (default Haiku 4.5, D-MDL-002) once per chunk to produce a 50–100 token prefix summarizing the chunk's place in the source document. Use Anthropic prompt caching to amortize the source-doc preamble across that source's chunks. Store the prefix in `chunk.contextPrefix` (new optional field on `chunk.schema.json`) and feed `contextPrefix + "\n\n" + text` to the embedding model and BM25 indexer at upsert time. Bump `corpusVersion` when context-prefix generation parameters or model route change. Ingestion-only LLM call — no answer-time rewriting (cross-reference ADR-0007 §Clarification).
- **REC-012 Logios scanned-OCR route** — add `LogiosParser` adapter under `app/adapters/parser/logios_parser.py`; selectable via a per-source manifest flag in the `sources` table (`parser_kind: 'pdfplumber' | 'tesseract' | 'logios'`); default off until benchmarked on Orthodox-Ethos sources. Add Logios-to-`ParsedBlock` translation. Local execution only (closed-corpus posture preserved).
- **REC-013 Phase-1 candidate-edge emission** — at ingestion, emit candidate edges (`X quotes Y`, `X cites Y`, `X translation of Y`) using a deterministic regex + LLM-extracted hybrid pipeline (LLM via `ModelRoute` `purpose='edge_extraction'`, default Haiku 4.5, D-MDL-003) to a `graph_candidates` table. Edges remain candidate-only (never surfaced to A4/A5) until approved through a Phase-2 admin UI.

### Amendments to T-003 (query analyzer + retrieval + reranker)

- **REC-016 CohereRerankerAdapter** — implement under `app/adapters/reranker/cohere_adapter.py` behind the existing `Reranker` Protocol; add a certified-track `ModelRoute` row for `purpose='rerank'`, vendor `cohere`; gate certification on retrieval-eval pass. ADR-0005 egress amendment in effect (Cohere receives chunk text).
- **REC-018 Modal GPU reranker** — implement `ModalBgeReranker` adapter that calls a Modal endpoint hosting `BAAI/bge-reranker-v2-m3` on T4 by default (`$0.59/hr`, per-second billing); auto-fallback to local CPU adapter on Modal error. Add a Modal deployment script under `infra/modal/reranker_app.py`. Cite ADR-0005 amendment for egress.

### Amendments to T-004 (evidence + verifier + retrieval eval)

- **REC-011 Anthropic prompt caching for A5** — structure A5 composition prompts as `[system + corpus_chunks_prefix | dynamic_query]`; set `cache_control` on the corpus prefix block in `anthropic_adapter.py`. Extend cache-key recipe per the updated `cache-key.md` to include `model_id + system_hash + chunk_id_set + corpusVersion` so a stale cache cannot poison follow-ups.
- **REC-019 DeepEval inside retrieval-eval** — pin `deepeval` in backend dev-deps; replace homegrown judge calls in `tests/retrieval_eval/judge.py` with DeepEval metric classes routed through the internal `purpose='retrieval_eval_judge'` `ModelRoute`. Disable DeepEval cloud telemetry (no login, no telemetry env vars set).
- **REC-020 Anthropic Batch API for judge** — extend `anthropic_adapter.py` with a batch-mode submission path; gate by `purpose='retrieval_eval_judge'` only. Never used on the user-facing answer path.

### Amendments to T-005 (cache + logs + billing + observability)

- **REC-010 OpenTelemetry SDK** — pin `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx` in backend deps. Configure exporter to console in Phase 1; add stub for Langfuse self-host (Phase 2, REC-025). Use `runId` as `trace_id`. Add GenAI semconv attributes (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`) on every provider call. Extend redaction filter to OTel span processor (same rule set as structlog: never log `query_text`/`chunk_text`/secrets). Benchmark p95 latency before merging to confirm OTel span overhead is bounded (R-7 mitigation).

### Amendments to T-006 (admin + chat UI + safety-suite-execution)

- **REC-006 Haiku 4.5 certification** — once T-006 ships `backend/tests/safety/test_20_queries_harness.py`, the certification PR for Haiku 4.5 routes runs both the safety-suite-execution job and the retrieval-eval suite as PR-blocking artifacts. Only `role='owner'` may PATCH the routes to `certified` (per ADR-0004). Sonnet 4.6 stays as `experiment` fallback for the same purposes.

## Acceptance Criteria

- All files listed under "Amended" and "Newly created" exist on disk with the documented changes.
- Every documentation amendment carries a cross-link to its originating ADR / REC ID where applicable.
- A mental run of the proposed `scripts/check_docs_index.py` check passes — every file in `docs/adr/`, `docs/contracts/`, `docs/schemas/` appears in `docs/DOCS_INDEX.md`; every index row maps to a present file.
- No application code, no scripts, no JSON-schema-as-code files outside `docs/schemas/`, no CI workflow files are modified by this task card.
- No file under `config/`, no file in `tests/`, no file under `scripts/` is touched by this card (those are reserved for code-phase task cards).
- T-007 placeholders (founder + Greek reviewer ownership + target merge date) remain UNCHANGED. T-008 does not unblock T-007.
- The `contracts` CI job in `.github/workflows/ci-safety-gate.yml` still passes (JSON schemas validate; OpenAPI lints).

## Open Blockers

- **T-007 (REC-004) — founder + Greek-language reviewer action.** Out-of-scope for this card. Founder (`peterstavrinides0@gmail.com`) must name two reviewers, set target merge date, produce real safety rules covering every `sensitivityPrimary` + `riskFlags` value in English and Greek, and populate the paraphrase test (3–5 entries per case). Exit criterion #9 cannot close until then. T-008 deliberately does not touch `config/sensitivity_keywords.yaml`, `config/pastoral_filters.yaml`, or `tests/safety/test_20_queries_paraphrases.py`.

## Forbidden Scope

- Modifying any file under `config/`, `tests/`, `scripts/`, `backend/`, `web/`, `app/`, or `.github/workflows/`.
- Pulling forward any item that requires a founder decision, vendor egress approval, or a paid API call.
- Opening a pull request without explicit user instruction (CLAUDE.md §6).
- Weakening any of the invariants listed in AGENTS.md §60–99 or §3.3 of the evaluation report.

## Notes for Future Sessions

- The Phase-2 task cards under `docs/task_cards/phase2/` are speculative — they exist so the eventual Phase-2 planning session does not start from zero. They do not commit the project to any specific Phase-2 sequencing.
- The four GS upgrades materially change two existing decisions: GS-1 reverses the Phase-2 deferral of Postgres RLS recorded at `db-schema.md` L10–11, and GS-3 pulls the structural piece of decision 6 (prompt versioning) forward from "post-MVP" to "Phase 1." Both reversals are documented in the relevant amendments; do not relitigate them without a follow-up ADR.
- The Contextual Retrieval (REC-005) amendment is the only change that has been flagged for a risk of being misread as a query-rewriting violation. The clarifying note on ADR-0007 and the ingestion-vs-retrieval framing in the amended ADR-0009 are the authoritative resolution. R-1 in the evaluation report's Risk Register is the cited mitigation.
- The Modal-hosted Llama-3-70B A5 peer (GS-4) is mentioned in ADR-0014 as a candidate certified peer only. Activation requires safety-suite + retrieval-eval certification per ADR-0004; the work is captured in T-009.
