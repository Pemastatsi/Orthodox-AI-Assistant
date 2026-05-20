# Scaffold Contract

Status: Canonical
Date: 2026-05-11

This document is the meta-contract for T-001. It cites every upstream contract and turns the architecture in `docs/contracts/code-gen-guide.md` into a concrete repository scaffold. T-001 ships exactly what is listed below — no more, no less.

## Upstream Contracts (Required Reads Before Scaffolding)

- [code-gen-guide.md](code-gen-guide.md) — directory layout, layering rules, naming conventions.
- [auth-context.md](auth-context.md) — Clerk JWT resolution, Principal shape.
- [provider-interface.md](provider-interface.md) — provider Protocol + error taxonomy.
- [parser-interface.md](parser-interface.md) — Parser Protocol + ParsedBlock shape (ADR-0008).
- [chunking-contract.md](chunking-contract.md) — hierarchical chunking algorithm (ADR-0009).
- [vector-store-interface.md](vector-store-interface.md) — VectorStore Protocol + tenant-isolation invariant (ADR-0010).
- [cache-key.md](cache-key.md) — canonical cache-key recipe + fixtures.
- [error-taxonomy.md](error-taxonomy.md) — ApiError codes used in OpenAPI.
- [observability.md](observability.md) — log shape, X-Run-Id propagation.
- [db-schema.md](db-schema.md) — first migration content.
- [api-versioning.md](api-versioning.md) — version field formats.
- [quote-overlap-algorithm.md](quote-overlap-algorithm.md) — A6 spec.
- [safety-config-format.md](safety-config-format.md) — YAML format and validation.
- [frontend-components.md](frontend-components.md) — component contracts.
- All schemas in `docs/schemas/` and the OpenAPI in `docs/api/openapi.yaml`.

T-001 does not reinterpret, expand, or contradict these documents.

## Repository Tree (T-001 ships these files only)

```
backend/
├── pyproject.toml
├── README.md                      # one-liner; points to AGENTS.md
├── alembic.ini
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI factory; /health endpoint only at T-001
│   ├── api/__init__.py
│   ├── api/v1/__init__.py
│   ├── core/__init__.py
│   ├── core/config.py             # pydantic-settings; reads .env
│   ├── core/logging.py            # structlog setup with redaction filter
│   ├── core/auth.py               # placeholder Clerk verifier; raises NotImplementedError
│   ├── core/errors.py             # ApiError + exception classes
│   ├── core/middleware.py         # X-Run-Id middleware only at T-001
│   ├── adapters/__init__.py
│   ├── adapters/providers/__init__.py
│   ├── adapters/providers/base.py # Protocol from provider-interface.md
│   ├── adapters/parsers/__init__.py
│   ├── adapters/parsers/base.py            # Parser Protocol per parser-interface.md (ADR-0008)
│   ├── adapters/parsers/pdfplumber_parser.py  # stub (raises NotImplementedError; impl in T-002)
│   ├── adapters/parsers/tesseract_parser.py   # stub (raises NotImplementedError; impl in T-002)
│   ├── adapters/parsers/vision_parser.py      # Phase 2 stub; always raises NotImplementedError
│   ├── adapters/vector_store/__init__.py
│   ├── adapters/vector_store/base.py       # VectorStore Protocol per vector-store-interface.md (ADR-0010)
│   ├── adapters/vector_store/qdrant_store.py  # stub (raises NotImplementedError; impl in T-002)
│   ├── domain/__init__.py
│   ├── domain/agents/__init__.py  # empty stubs for a1..a6 (raise NotImplementedError)
│   ├── domain/services/__init__.py
│   ├── domain/repositories/__init__.py
│   ├── domain/models/__init__.py  # one pydantic file per docs/schemas/
│   ├── workers/__init__.py
│   └── alembic/
│       ├── env.py
│       └── versions/
│           └── 0001_initial.py    # full DDL from db-schema.md
└── tests/
    ├── __init__.py
    ├── unit/__init__.py
    ├── integration/__init__.py
    └── safety/
        └── test_20_queries_harness.py   # imports CANONICAL_SAFETY_CASES from repo root tests/

web/
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json
├── next.config.mjs
├── tailwind.config.ts
├── postcss.config.mjs
├── README.md                      # points to AGENTS.md
├── app/
│   ├── layout.tsx
│   ├── page.tsx                   # placeholder "Phase 1 scaffold" landing
│   ├── error.tsx                  # generic error boundary
│   ├── loading.tsx
│   └── api/health/route.ts        # GET → 200 ok
├── components/
│   └── ui/skeleton/Skeleton.tsx
├── lib/
│   ├── api-client.ts              # generated from openapi (placeholder file with TODO)
│   ├── i18n/
│   │   └── errors.en.json         # stub i18n error strings; one entry per code in error-taxonomy.md
│   └── schemas/                   # generated zod (placeholder TODO)
└── tests/
    └── smoke.test.ts

infrastructure/
├── Dockerfile.backend
├── Dockerfile.web
├── docker-compose.yml             # postgres, qdrant, redis
└── railway.toml

.env.example
Makefile
ruff.toml
mypy.ini
pyproject.toml -> backend/pyproject.toml   # workspace marker; not actually a symlink, just a comment
```

## Backend `pyproject.toml`

Use **uv** as the dependency manager. Pin majors only; rely on `uv.lock` for exact pins.

Required runtime deps:
- `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`
- `sqlalchemy>=2`, `alembic`, `asyncpg`, `psycopg[binary]`
- `qdrant-client`
- `redis`, `arq`
- `anthropic`, `openai`
- `clerk-backend-sdk` (or HTTP-only Clerk verifier if SDK unavailable)
- `stripe`
- `structlog`, `httpx`, `tenacity`, `ulid-py`
- `pyyaml`

Required dev deps:
- `pytest`, `pytest-asyncio`, `pytest-cov`
- `ruff`, `mypy`, `types-pyyaml`

Python: `requires-python = ">=3.12,<3.13"`.

## Frontend `package.json`

Use **pnpm**. Pin majors.

Required runtime:
- `next` 14, `react` 18, `react-dom` 18
- `@clerk/nextjs`
- `tailwindcss`, `autoprefixer`, `postcss`
- `lucide-react`
- `zod`

Required dev:
- `typescript`, `@types/node`, `@types/react`, `@types/react-dom`
- `eslint`, `@next/eslint-plugin-next`, `@typescript-eslint/eslint-plugin`, `@typescript-eslint/parser`
- `prettier`
- `vitest`, `@testing-library/react`, `@testing-library/dom`, `jsdom`

Node: `"engines": { "node": ">=20 <21", "pnpm": ">=9" }`.

## `.env.example`

The full var inventory derived from upstream contracts. Names are stable.

```bash
# --- Service ---
APP_ENV=development          # development | staging | production
SERVICE_VERSION=0.0.1
LOG_LEVEL=info

# --- Postgres ---
DATABASE_URL=postgresql+asyncpg://orthodox:orthodox@localhost:5432/orthodox

# --- Redis ---
REDIS_URL=redis://localhost:6379/0
RESPONSE_CACHE_TTL_SECONDS=3600

# --- Qdrant ---
QDRANT_URL=                      # in-network Railway URL or Qdrant Cloud endpoint
QDRANT_COLLECTION=patristic      # or per-tenant collection name pattern
QDRANT_API_KEY=                  # leave blank for self-hosted Qdrant without auth

# --- Auth ---
AUTH_PROVIDER=dev                # dev | clerk; default behavior in scaffold is dev for local. APP_ENV=production refuses to boot if AUTH_PROVIDER=dev (see auth-context.md §Development Mode).

# --- Clerk ---
CLERK_SECRET_KEY=sk_test_REPLACE_ME
CLERK_PUBLISHABLE_KEY=pk_test_REPLACE_ME
CLERK_JWT_ISSUER=https://REPLACE_ME.clerk.accounts.dev
CLERK_AUTHORIZED_PARTIES=http://localhost:3000

# --- PDF Parsing (T-002 ingestion) ---
TESSERACT_BINARY_PATH=/usr/bin/tesseract
TESSERACT_LANGUAGE_PACK_PATH=/usr/share/tesseract-ocr/4.00/tessdata

# --- Stripe ---
STRIPE_SECRET_KEY=sk_test_REPLACE_ME
STRIPE_WEBHOOK_SECRET=whsec_REPLACE_ME
STRIPE_USAGE_METER=served_answer_count

# --- LLM providers ---
ANTHROPIC_API_KEY=REPLACE_ME
OPENAI_API_KEY=REPLACE_ME

# --- Make.com webhooks ---
MAKE_WEBHOOK_SECRET=REPLACE_ME   # HMAC secret; can be left as REPLACE_ME until the Make.com integration is activated (Phase 2). The endpoint returns 501 until then.

# --- Sensitive log encryption ---
SENSITIVE_LOG_DATA_KEY_BASE64=   # base64-encoded AES-256 key for application-level envelope encryption of raw sensitive logs; rotate via Railway secret manager. Required when APP_ENV=production.
SENSITIVE_LOG_RETENTION_DAYS=30

# --- Versions (read at startup) ---
ACTIVE_SCHEMA_VERSION=2026-05-01.1
ACTIVE_PROMPT_VERSION_A1A2=qa_analyze@2026-05-01.1
ACTIVE_PROMPT_VERSION_A5=a5_compose@2026-05-01.1
ACTIVE_MODEL_ROUTE_A1A2=qa_analyze_anthropic@2026-05-01.1
ACTIVE_MODEL_ROUTE_A5=a5_compose_anthropic@2026-05-01.1
ACTIVE_MODEL_ROUTE_EMBEDDING=embedding_openai@2026-05-01.1
ACTIVE_MODEL_ROUTE_VERIFIER=               # optional; absence disables A6 judge (deterministic citation checks still run)
ACTIVE_MODEL_ROUTE_RERANK=                 # optional; absence disables A3 reranking (dense+hybrid retrieval still runs); see ADR-0012
ACTIVE_MODEL_ROUTE_RETRIEVAL_EVAL_JUDGE=   # optional; absence disables Ragas-style LLM-judge metrics in retrieval-eval CI (deterministic Recall@K/Precision@K still run); see docs/contracts/retrieval-eval-suite.md

# --- Frontend ---
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_REPLACE_ME
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

## `Dockerfile.backend`

Multi-stage. Stage 1: install uv and `uv sync --frozen --no-dev`. Stage 2: copy `app/` and run `uvicorn app.main:app --host 0.0.0.0 --port 8000`. Healthcheck hits `/health`.

## `Dockerfile.web`

Multi-stage. Stage 1: `pnpm install --frozen-lockfile && pnpm build`. Stage 2: `next start -p 3000`.

## `docker-compose.yml`

Three services for local dev:

- `postgres` (image `postgres:16`, port 5432, volume).
- `qdrant` (image `qdrant/qdrant:latest`, port 6333, volume).
- `redis` (image `redis:7-alpine`, port 6379).

Backend and web are run from the host (`make dev`) so reload is fast. The compose file exists only for the dependencies.

## `railway.toml`

Two services: `backend` (Dockerfile.backend) and `web` (Dockerfile.web). Postgres and Redis are Railway-managed plugins. **Qdrant is a Railway custom-Docker service** (deployed from `qdrant/qdrant:latest` or pointed at an external host such as Qdrant Cloud) — it is not a Railway-managed plugin. The `railway.toml` declares the Qdrant service alongside the backend and frontend; the `QDRANT_URL` env var points at the in-network service URL, and `QDRANT_API_KEY` is set when the Qdrant instance has authentication enabled (leave blank for self-hosted unauthenticated dev). Health checks point at `/health` (backend) and `/api/health` (web).

## `Makefile`

```make
.PHONY: dev test safety lint typecheck migrate up down

dev:        ## Start backend + web with deps in compose
	docker compose -f infrastructure/docker-compose.yml up -d
	(cd backend && uv run uvicorn app.main:app --reload --port 8000) &
	(cd web && pnpm dev)

test:
	(cd backend && uv run pytest -q)
	(cd web && pnpm test --run)

safety:
	pytest tests/safety -v

lint:
	(cd backend && uv run ruff check . && uv run mypy app)
	(cd web && pnpm lint && pnpm typecheck)

typecheck: lint

migrate:
	(cd backend && uv run alembic upgrade head)

up:
	docker compose -f infrastructure/docker-compose.yml up -d

down:
	docker compose -f infrastructure/docker-compose.yml down
```

## `ruff.toml`, `mypy.ini`, `pytest.ini`

- `ruff.toml`: line length 100, target Python 3.12, ruleset `E,F,I,UP,B,SIM,RET,ARG,N`. Per-file ignores for `app/alembic/versions/` (autogenerated migrations).
- `mypy.ini`: `strict = True` for `app/domain/*`, `python_version = 3.12`, `plugins = pydantic.mypy`. `ignore_missing_imports` only for `qdrant_client.*` until Qdrant ships type stubs.
- `pytest.ini`: `asyncio_mode = auto`, `testpaths = tests backend/tests`.

## Development-Mode Auth (`AUTH_PROVIDER`)

The placeholder in `app/core/auth.py` (per the existing tree) is governed by the `AUTH_PROVIDER` env var. The full behavior contract is in `auth-context.md` §Development Mode; this section records the scaffold-level wiring T-001 must emit.

- `AUTH_PROVIDER=dev` (default in `.env.example` for local development):
  - `app/core/auth.py` reads an `X-Dev-Principal` request header containing a base64-encoded JSON `Principal` (shape per `docs/schemas/principal.schema.json`). When the header is present and decodable, that Principal is used.
  - When the header is absent, a hardcoded test Principal is returned with `tenantId="dev-tenant"`, `role="member"`, and all other fields populated with safe defaults documented in `auth-context.md`.
  - No Clerk JWKS verification is performed.
- `AUTH_PROVIDER=clerk` (required for staging and production):
  - Full Clerk JWKS verification per `auth-context.md`. The `X-Dev-Principal` header is ignored.

**Boot guard.** `app/main.py` performs a startup check: when `APP_ENV=production` AND `AUTH_PROVIDER=dev`, the application raises `ProductionAuthConfigError` and refuses to boot. This mirrors the existing safety-config production boot guard pattern.

The constructor for `app/core/auth.py` also logs a single INFO line at startup with `auth_provider=<value>` and `app_env=<value>` so ops can confirm the resolved mode without grepping config.

## What T-001 Does Not Build

- A1–A6 logic. Stubs only.
- Real Clerk verification. Placeholder that returns a hardcoded test Principal in `APP_ENV=development`.
- Real Qdrant indexing. Adapter with method signatures and `NotImplementedError` bodies.
- The chat UI. Placeholder landing page only.
- Admin screens.
- Stripe billing.
- Real model routes. The model-route registry is seeded with one row per active route in the first migration but the certification flow is T-005.

## Acceptance Criteria for T-001

T-001 is complete when:

1. `make up && make migrate && make test && make safety && make lint` exits 0 on a clean checkout.
2. `curl -fsS localhost:8000/health` returns `{"status":"ok","version":"..."}`.
3. `curl -fsS localhost:3000/api/health` returns 200.
4. `redocly lint docs/api/openapi.yaml` exits 0.
5. The first Alembic migration applies and contains every table from db-schema.md.
6. `app/adapters/providers/base.py` defines the `LLMProvider` Protocol exactly per provider-interface.md.
7. `app/domain/models/` contains a pydantic model per JSON schema in `docs/schemas/`, generated or hand-written, that round-trips a fixture instance.
8. The CI workflow at `.github/workflows/ci-safety-gate.yml` runs to green on a PR that ships only this scaffold.
9. No hardcoded secret, no `os.environ` read outside `core/config.py`, no provider SDK import outside `adapters/providers/`, no `pdfplumber`/`pytesseract` import outside `adapters/parsers/`, no `qdrant_client` import outside `adapters/vector_store/`.
10. Frontend i18n: `web/lib/i18n/errors.en.json` exists with at minimum a stub entry for each error `code` listed in `error-taxonomy.md` (use `"<code>": "<short user-facing string>"`); the smoke test "unknown error code → fallback to `errors.en.json#unknown_error`" is set up in T-001 (test body may be a TODO until T-006).
11. `app/adapters/parsers/base.py` defines the `Parser` Protocol and the `ParsedPage` / `ParsedBlock` dataclasses exactly per `parser-interface.md`. The three concrete parsers (`pdfplumber_parser.py`, `tesseract_parser.py`, `vision_parser.py`) exist as `NotImplementedError` stubs whose class shapes match the Protocol.
12. `app/adapters/vector_store/base.py` defines the `VectorStore` Protocol and the `ChunkPayload` / `VectorFilter` / `ScoredChunk` dataclasses exactly per `vector-store-interface.md`, including the runtime `ValueError("tenant_id required")` guard on `search` and `delete_by_filter` and the "no mixed-tenant batches" guard on `upsert`. `qdrant_store.py` exists as a stub whose method shapes match the Protocol.
13. `app/core/auth.py` honors `AUTH_PROVIDER=dev` by reading the `X-Dev-Principal` header (or returning the documented fallback Principal). `app/main.py` raises `ProductionAuthConfigError` at startup when `APP_ENV=production` AND `AUTH_PROVIDER=dev`.

## Notes on Discipline

- T-001 is the only task card opened during scaffold. T-002 through T-006 stay closed until T-001 is reviewed and merged.
- If a contract is found wrong during scaffold (typo, contradiction, ambiguity), the contract is fixed first. Code does not work around contracts.
- New hygiene files (`.gitignore`, etc.) shipped in S11 of the documentation hardening plan are already on disk; T-001 does not recreate them.

## Phase 2 Deferrals (informational, not part of T-001)

- Six `ACTIVE_MODEL_ROUTE_*` env vars (`A1A2`, `A5`, `EMBEDDING`, `VERIFIER`, `RERANK`, `RETRIEVAL_EVAL_JUDGE`) are individually pinned for Phase 1 simplicity. The last three are blank-by-default — absence disables the corresponding optional stage cleanly per the comments in `.env.example`. Phase 2 may consolidate them into a `system_config` DB table with a startup loader that overlays env-var overrides; tracked as a Phase 2 ergonomics ticket.
