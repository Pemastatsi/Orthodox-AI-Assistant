# T-001: Scaffold Repository And Contracts

## Goal

Create the initial application scaffold around the canonical contracts without changing product behavior. The exact tree, dependency lists, env vars, Dockerfiles, Makefile, and acceptance criteria are defined in [`docs/contracts/scaffold-contract.md`](../../contracts/scaffold-contract.md). This task card does not redefine them.

## Required Reads

- [`docs/contracts/scaffold-contract.md`](../../contracts/scaffold-contract.md) — the meta-contract; this is the primary source.
- [`docs/contracts/code-gen-guide.md`](../../contracts/code-gen-guide.md) — architecture and layering rules.
- [`docs/contracts/db-schema.md`](../../contracts/db-schema.md) — first Alembic migration content.
- [`docs/contracts/auth-context.md`](../../contracts/auth-context.md) — Principal shape.
- [`docs/contracts/provider-interface.md`](../../contracts/provider-interface.md) — LLMProvider Protocol.
- [`docs/contracts/observability.md`](../../contracts/observability.md) — log/middleware shape.
- [`docs/api/openapi.yaml`](../../api/openapi.yaml) and all schemas in [`docs/schemas/`](../../schemas/).

## Files In Scope

Exactly the files listed in the "Repository Tree" section of the scaffold contract. Adding files outside that list requires updating the scaffold contract first.

## Acceptance Tests

Defined in the "Acceptance Criteria for T-001" section of the scaffold contract. Summary:

1. `make up && make migrate && make test && make safety && make lint` exits 0.
2. `/health` (backend) and `/api/health` (web) return 200.
3. `redocly lint docs/api/openapi.yaml` exits 0.
4. First Alembic migration creates every table in `db-schema.md`.
5. `app/adapters/providers/base.py` matches `provider-interface.md` exactly.
6. `app/domain/models/` mirrors every schema in `docs/schemas/`.
7. CI workflow runs to green on this PR.
8. No hardcoded secrets; no `os.environ` outside `core/config.py`; no provider SDK import outside `adapters/providers/`.

## Forbidden Scope

- Implementing A1–A6 logic. Stubs only.
- Adding Clerk JWT verification beyond a development placeholder that returns a hardcoded test Principal when `APP_ENV=development`.
- Implementing Qdrant indexing or retrieval. Adapter signatures only.
- Building the chat UI. Placeholder landing page only.
- Building admin screens.
- Wiring Stripe.
- Writing or modifying any ADR.
- Moving archived/reference docs back to root.
- Adding files outside the scaffold contract's tree without updating the contract first.

## Acceptance — Wave 4 Additions

- **F-24:** `web/lib/i18n/errors.en.json` exists with at least one stub entry per error code in `error-taxonomy.md`. Smoke test: unknown error code falls back to `errors.en.json#unknown_error`.
