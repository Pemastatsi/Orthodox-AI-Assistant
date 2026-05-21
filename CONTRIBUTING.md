# Contributing

This is an internal/private-beta project. External contributions are not currently accepted.

If you are an internal contributor or a Claude coding session, the working brief is:

1. Read [AGENTS.md](AGENTS.md) — the always-read coding brief and product semantics.
2. Read [docs/contracts/code-gen-guide.md](docs/contracts/code-gen-guide.md) — the FastAPI/Next.js code-generation contract.
3. Read the relevant task card under [docs/task_cards/phase1/](docs/task_cards/phase1/).
4. Read the directly affected source files and any failing tests.

[CLAUDE.md](CLAUDE.md) auto-loads into every session and defines the universal safety and policy spine.

For exact source priority, contracts, schemas, and tests, see [docs/DOCS_INDEX.md](docs/DOCS_INDEX.md).

## Pull Request Rules

- One task card per PR. Do not combine unrelated changes.
- Update or add the schema/contract/test before changing code.
- The CI safety gate (`.github/workflows/ci-safety-gate.yml`) must pass.
- Cross-tenant, closed-corpus, citation-verification, and tenant-isolation invariants are non-negotiable.

## Local Development Bootstrap

Toolchain versions are pinned in [`.tool-versions`](.tool-versions). With `asdf` or `mise` installed, running `asdf install` (or `mise install`) in the repo root provisions Python 3.12, Node 20, uv, and pnpm at the same versions CI uses. Without a version manager, install them manually to those versions.

Once `backend/` and `web/` land in T-001, the standard local flow is:

```bash
make up          # boots postgres, qdrant, redis via infrastructure/docker-compose.yml
make migrate     # applies Alembic migrations
make test        # runs backend pytest + web vitest
make safety      # runs the 20-case theological safety fixture validation
make lint        # ruff + mypy + eslint + tsc
```

`docker` and `make` must be on `$PATH`. The compose file only provisions dependencies; the backend and web processes are run from the host (`make dev`) for fast reload.

CI job status expectations are documented at the top of `.github/workflows/ci-safety-gate.yml`. `safety-suite-execution` is intentionally red until T-006 — see the in-file comment before treating it as a regression.

## Phase 1 Long-Leads

These items are not coding work but block the Phase 1 → Phase 2 exit. Start them in parallel with implementation:

- **T-007 founder + Greek-language reviewer assignment** ([`docs/task_cards/phase1/T-007-real-safety-configs.md`](docs/task_cards/phase1/T-007-real-safety-configs.md) — the `<TBD: founder to specify>` placeholders must be filled before T-007 work begins). Exit criterion #9 cannot close without these reviewers.

## Reporting Issues

Internal issues: use the project tracker.
Security issues: see [SECURITY.md](SECURITY.md). Do not file security issues in the public tracker.
