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

## Reporting Issues

Internal issues: use the project tracker.
Security issues: see [SECURITY.md](SECURITY.md). Do not file security issues in the public tracker.
