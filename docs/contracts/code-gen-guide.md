# Code-Generation Guide

Status: Canonical
Date: 2026-05-01

This document is the architecture and code-generation contract for the Orthodox AI Assistant. Every coding session must read this after `AGENTS.md` and before opening a task card. Concrete scaffold steps (directory creation, dependency manifests, Dockerfile, CI) are in `docs/contracts/scaffold-contract.md`.

## 1. Architecture Overview

Two-process service:

- **`backend/`** — FastAPI (Python 3.12) service exposing `/api/v1/*`. Async-first. Owns the A1–A6 query pipeline, ingestion, admin, and webhooks.
- **`web/`** — Next.js 14 (TypeScript) app router. Owns the chat UI, citation panel, reframing disclosure, admin corpus/queries/flagged screens.

External services: Postgres (Railway managed), Qdrant (Docker), Redis (Railway managed), Clerk (auth), Stripe (billing), Anthropic + OpenAI (LLM/embedding providers).

## 2. Backend Layout

```
backend/
├── app/
│   ├── main.py                       # FastAPI app factory + middleware
│   ├── api/
│   │   └── v1/
│   │       ├── query.py              # POST /query
│   │       ├── ingest.py             # POST /ingest, GET /ingest/jobs/{id}
│   │       ├── corpus.py             # GET /corpus, PATCH /corpus/{chunkId}
│   │       ├── runs.py               # GET /runs/{id}
│   │       ├── admin.py              # GET /admin/queries|flagged|audit
│   │       ├── tenant_config.py      # GET/PATCH /tenant/config
│   │       └── webhooks.py           # POST /webhooks/{stripe,clerk,make}
│   ├── core/
│   │   ├── config.py                 # pydantic-settings; env-var inventory
│   │   ├── logging.py                # structlog setup; redaction filters
│   │   ├── auth.py                   # Clerk JWT → Principal
│   │   ├── errors.py                 # ApiError envelope, exception handlers
│   │   └── middleware.py             # tenant context, run-id, rate limit
│   ├── domain/
│   │   ├── agents/
│   │   │   ├── a1_classifier.py      # ClassifiedQuery
│   │   │   ├── a2_retrieval_planner.py # RetrievalPlan (paired with a1)
│   │   │   │                         # NOTE: A1 and A2 are a single physical LLM call (one structured-output
│   │   │   │                         # request returning both ClassifiedQuery and RetrievalPlan), but they
│   │   │   │                         # remain separate Python modules to keep the conceptual contract surface
│   │   │   │                         # clean and to allow future split if a different routing strategy emerges.
│   │   │   │                         # Do not consolidate into a single query_analyzer.py without an ADR.
│   │   │   │                         # Logs persist the two outputs separately per AGENTS.md §Query Pipeline.
│   │   │   ├── a3_retrieval.py       # Qdrant search → candidate chunks
│   │   │   ├── a4_evidence_packager.py # deterministic admission gates
│   │   │   ├── a5_composer.py        # evidence-only composition
│   │   │   └── a6_verifier.py        # citation + lineage verification
│   │   ├── services/
│   │   │   ├── query_orchestrator.py # A1→A6 pipeline driver
│   │   │   ├── ingest_service.py
│   │   │   ├── chunking_service.py
│   │   │   ├── citation_service.py
│   │   │   ├── cache_service.py      # response cache + key recipe
│   │   │   ├── usage_service.py      # served_answer_count / fresh_model_run_count
│   │   │   ├── audit_service.py
│   │   │   └── safety_config.py      # YAML loader for sensitivity/pastoral filters
│   │   └── models/                   # pydantic models = JSON Schema views
│   │       ├── classified_query.py
│   │       ├── retrieval_plan.py
│   │       ├── evidence_packet.py
│   │       ├── verified_response.py
│   │       ├── principal.py
│   │       ├── run_trace.py
│   │       └── ...                   # one file per docs/schemas/*.json
│   ├── repositories/
│   │   ├── tenant_repo.py
│   │   ├── source_repo.py
│   │   ├── chunk_repo.py
│   │   ├── session_repo.py
│   │   ├── run_repo.py
│   │   ├── audit_repo.py
│   │   ├── flagged_repo.py
│   │   └── billing_repo.py
│   ├── adapters/
│   │   ├── providers/
│   │   │   ├── base.py               # Protocol per docs/contracts/provider-interface.md
│   │   │   ├── anthropic_adapter.py
│   │   │   └── openai_adapter.py
│   │   ├── qdrant_adapter.py
│   │   ├── redis_adapter.py
│   │   ├── clerk_adapter.py
│   │   └── stripe_adapter.py
│   ├── workers/
│   │   ├── queue.py                  # arq or rq; ingestion + retention jobs
│   │   └── tasks/
│   │       ├── chunking.py
│   │       ├── embedding.py
│   │       └── retention_cleanup.py  # 30-day raw sensitive log cleanup
│   └── alembic/                      # migrations; first migration matches db-schema.md
└── tests/
    ├── unit/
    ├── integration/
    └── safety/                       # mirrors tests/safety/ at repo root
```

## 3. Frontend Layout

```
web/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                      # standalone chat
│   ├── (admin)/
│   │   ├── corpus/page.tsx           # approval queue
│   │   ├── queries/page.tsx          # query log
│   │   └── flagged/page.tsx
│   └── api/                          # thin proxy routes to backend (auth-attached)
├── components/
│   ├── chat/
│   │   ├── ChatComposer.tsx
│   │   ├── AnswerPanel.tsx
│   │   ├── CitationPanel.tsx
│   │   └── ReframingDisclosure.tsx
│   ├── admin/
│   │   ├── ApprovalQueue.tsx
│   │   ├── QueryLog.tsx
│   │   └── FlaggedList.tsx
│   └── ui/                           # shadcn-style primitives
├── lib/
│   ├── api-client.ts                 # generated from openapi.yaml
│   ├── schemas/                      # generated zod validators from docs/schemas/
│   └── auth.ts                       # Clerk wrapper
└── tests/
```

Component prop contracts are in `docs/contracts/frontend-components.md`.

### Server-Sent Events (SSE) for /query progress

The `POST /query` endpoint accepts an optional `streamProgress: true` body field. When set, the server may upgrade the response to `text/event-stream` over the same path (clients send `Accept: text/event-stream`). The OpenAPI contract (`docs/api/openapi.yaml`) does **not** model the SSE media type — the typed JSON shape there is the cache-hit and final-event payload only. SSE event grammar:

- `event: progress` — JSON payload `{ "stage": "<a1|a3|a4|a5|a6>", "elapsedMs": <int> }`. Sent zero or more times during a fresh model run; never sent for cache hits.
- `event: done` — JSON payload is the full `VerifiedResponse` per `verified-response.schema.json`. Sent exactly once at the end.
- `event: error` — JSON payload is the standard `ApiError` envelope. Sent at most once; terminates the stream.

Cache hits return a single `done` event followed by stream close; no `progress` events are emitted. Frontend implementation (`web/lib/api-client.ts`) must consume the stream via `EventSource` or fetch+ReadableStream; see `frontend-components.md` for `<ChatComposer>` behavior.

## 4. Layering Rules (Hard)

The dependency direction is one-way. Violations are a code-review block.

```
api  →  domain/services  →  domain/agents
                       ↘ repositories  →  adapters
                       ↘ adapters
```

- **`api/`** translates HTTP ↔ services. No business logic. No direct provider/Qdrant/Redis calls.
- **`domain/agents/`** are pure functions over typed inputs/outputs (the JSON schemas). They call providers only through `adapters/providers/`. They never touch SQL or Redis directly.
- **`domain/services/`** orchestrate agents and repositories. They own transactions and cache decisions.
- **`repositories/`** are the only layer allowed to write SQL. Each method returns typed domain models.
- **`adapters/`** are the only layer allowed to call external SDKs (Anthropic, OpenAI, Qdrant, Redis, Clerk, Stripe). They expose a domain-shaped interface.
- **`workers/`** consume the same services and repositories; they never duplicate logic.

If a feature needs a new external dependency, it goes in a new `adapters/` module, not inline in a service.

## 5. Contract-First Development

All inter-layer boundaries are typed against `docs/schemas/*.json`.

- Pydantic models in `app/domain/models/` are generated/maintained 1:1 from `docs/schemas/`. Do not invent new fields in Python without first updating the schema.
- The frontend uses zod validators generated from the same schemas (`web/lib/schemas/`).
- The OpenAPI file at `docs/api/openapi.yaml` is the public HTTP contract; the frontend's `api-client.ts` is generated from it.
- New endpoints require: (a) OpenAPI update, (b) request/response schema in `docs/schemas/`, (c) error codes from `docs/contracts/error-taxonomy.md`, (d) at least one integration test.

## 6. Tenant Context Propagation

- Every request goes through `core/middleware.py`, which resolves the Clerk JWT to a `Principal` (`docs/schemas/principal.schema.json`) and binds it to the request scope.
- Repositories require the `Principal` (or at minimum `tenant_id`) as a parameter. There is no global "current tenant" lookup — pass it explicitly.
- Qdrant filters always include `tenant_id` AND `approved=true`. This is enforced by `adapters/qdrant_adapter.py`; agents never construct raw filter dicts.
- Cache keys are computed by `services/cache_service.py` per `docs/contracts/cache-key.md`. No ad-hoc string concatenation.

## 7. Observability

All log lines go through `structlog` with the redaction filter from `core/logging.py`. The line shape is fixed in `docs/contracts/observability.md`. Every request gets a `runId` (ULID) returned in the `X-Run-Id` response header and stamped on every downstream log.

## 8. Naming Conventions

- Python files: `snake_case.py`. Classes: `PascalCase`. Functions: `snake_case`. Constants: `UPPER_SNAKE`.
- Schema names: `kebab-case.schema.json` matching their `$id` (e.g., `evidence-packet.schema.json`).
- Pydantic models: same name as the schema title (e.g., `EvidencePacket`).
- Test files: `test_<unit_under_test>.py`. Safety tests live under `tests/safety/`.
- React components: `PascalCase.tsx`. Hooks: `useCamelCase`. Files in `app/` follow Next.js routing.

### 8.1 Field Naming Across Layers

The same logical field is spelled differently in different layers. Each boundary translates explicitly; nothing is auto-converted by reflection. The rule is one-line:

- **JSON wire payloads** (HTTP requests/responses, JSON Schemas under `docs/schemas/`, OpenAPI in `docs/api/openapi.yaml`, frontend zod validators): `camelCase`. Example: `tenantId`, `corpusVersion`, `quoteOverlapRatio`.
- **PostgreSQL columns** (DDL in `docs/contracts/db-schema.md`, SQLAlchemy column names, raw SQL in scripts): `snake_case`. Example: `tenant_id`, `corpus_version`, `quote_overlap_ratio`.
- **Qdrant payload keys and filter keys**: `snake_case`, identical to the Postgres column names. Example: `tenant_id`, `approved`, `corpus_version`. The Qdrant adapter MUST use these literal keys; tests assert the exact filter-dict shape.
- **Python code outside the boundary layers**: `snake_case` for variables and function parameters (Python convention). Pydantic models expose `camelCase` aliases for JSON serialization via `Field(alias=...)` and `model_config = ConfigDict(populate_by_name=True)`.

Translation responsibilities:

| Boundary | Owner | Direction |
|---|---|---|
| HTTP ↔ Pydantic domain model | `app/api/` route handler via Pydantic alias config | both ways |
| Pydantic domain model ↔ SQLAlchemy ORM row | `app/repositories/` repository class | both ways |
| Pydantic domain model ↔ Qdrant payload/filter | `adapters/qdrant_adapter.py` | both ways |
| Pydantic domain model ↔ Redis cache value | `services/cache_service.py` | both ways |

Hard rules:

- Never JSON-serialize a SQLAlchemy row directly. Always pass through the Pydantic model so the wire shape is camelCase.
- Never construct a raw Qdrant filter dict in agent code. Build a `RetrievalPlan`, hand it to `qdrant_adapter`, and the adapter writes `{"tenant_id": principal.tenantId, "approved": True, ...}`.
- Never read `tenant_id` from a request body or query string. Always derive it from `Principal.tenantId` (which is camelCase on the model and `tenant_id` after the adapter writes it). See `docs/contracts/auth-context.md`.
- A unit test in each adapter package asserts the exact translated key set so a misspelling is caught at CI time, not in production.

## 9. Toolchain

- **Python**: 3.12. Dependency manager: `uv`. Lint: `ruff`. Type-check: `mypy --strict` for `app/domain/`, `--standard` elsewhere. Test: `pytest` + `pytest-asyncio`. Logging: `structlog`. Settings: `pydantic-settings`. ORM: `sqlalchemy` 2.x async. Migrations: `alembic`.
- **Node**: 20 LTS. Package manager: `pnpm`. Lint: `eslint` + `@next/eslint-plugin-next`. Format: `prettier`. Type-check: `tsc --noEmit`. Test: `vitest` + `@testing-library/react`. CSS: `tailwindcss`.

Versions and the full dep list are pinned in `docs/contracts/scaffold-contract.md`.

## 10. Forbidden Patterns

These will fail review:

- A provider SDK import outside `adapters/providers/`.
- A raw SQL string outside `repositories/`.
- A Redis or Qdrant call outside the matching adapter.
- An `os.environ` read outside `core/config.py`.
- A `print` or `logging.getLogger` outside `core/logging.py`.
- A request handler returning anything other than the schema-validated response model.
- Any "TODO" left without an issue link.
- Concatenated cache keys.
- Tenant context resolved from the request body (it must come from auth).
- A hardcoded model/provider name (use the certified `ModelRoute` registry).

## 11. Self-Improvement

When implementation reveals that a contract is wrong, ambiguous, or insufficient, the fix order is:

1. Update the schema, ADR, or contract markdown first.
2. Open a follow-up task card if the change has scope beyond the current card.
3. Then update the code.

Do not silently work around contracts. If the change is large, raise it before coding.

## 12. Phase 2 Retrieval Enhancements (do not build in Phase 1)

The following enhancements are deferred to Phase 2 but must be designed into A3's return type now so they can be added without breaking the A4 contract.

### A3 Return Type Requirement (enforce in Phase 1)

`a3_retrieval.py` must return a typed list of `ScoredChunk` objects rather than raw Qdrant hit dicts:

```python
@dataclass
class ScoredChunk:
    chunk: Chunk
    score: float   # cosine similarity from Qdrant
    rank: int      # 1-based rank within the returned set
```

This interface is required in Phase 1 so that a reranker can be inserted between A3 scoring and A4 admission in Phase 2 without changing A4's input contract.

### Cross-Encoder Reranking (Phase 2)

After Qdrant returns `k` candidates, a cross-encoder reranker re-scores each `ScoredChunk` against the `semanticQuery` before A4 admission gates. This improves precision for long Patristic arguments where a passage may be semantically adjacent but not the most directly relevant.

- The reranker is invoked inside `a3_retrieval.py`, gated by a `RetrievalPlan.rerank: bool` field (default `False` in Phase 1, `True` in Phase 2 certified routes).
- Candidates for evaluation: `cross-encoder/ms-marco-MiniLM-L-6-v2` (self-hosted, fast) or Cohere Rerank API (managed, latency cost).
- The reranker must not alter the `ScoredChunk` schema — it updates `score` and `rank` only.
- A4 admission gates operate on the reranked list identically to the unreranked list.
