# Schema-to-code generators (REC-009)

**Status: enabled (REC-009 active).** The generators are wired (Makefile targets, generator script,
`.gitattributes`, CI drift gate) and the `_generated/` artifacts are committed. Generation runs the
tools **ephemerally** (pinned `uvx` / `pnpm dlx`) — **no project dependencies are installed**. The
hand-written models (`backend/app/domain/models/*.py`) and Zod schemas (`web/lib/schemas.ts`) remain
the source of truth; the generated artifacts are additive and gated for drift only.

The goal (T-008, REC-009): generate the three downstream artifacts from the canonical contracts
instead of hand-maintaining them, and fail CI if they drift — making "update the schema first" a
mechanical rule rather than a review habit.

## Source → target

| Generator | Source | Target | Tool |
|---|---|---|---|
| Pydantic v2 models | `docs/schemas/*.schema.json` | `backend/app/domain/models/_generated/` | `datamodel-code-generator` |
| TS API client types | `docs/api/openapi.yaml` | `web/lib/api-client.generated.ts` | `openapi-typescript` |
| Zod validators | `docs/schemas/*.schema.json` | `web/lib/schemas/_generated/` | `json-schema-to-zod` |

The existing **hand-written** models (`backend/app/domain/models/*.py`) and Zod schemas
(`web/lib/schemas.ts`) remain the source of truth until the generated artifacts are reviewed and
adopted. Generation is **additive** (writes to `_generated/`); it does not overwrite them.

## How it runs (no manifest changes)

`make codegen` / `make codegen-check` call `scripts/codegen/generate.sh`, which runs every tool
**ephemerally** via `uvx` (Python) and `pnpm dlx` (Node). Nothing is added to `pyproject.toml`,
`package.json`, `uv.lock`, or `pnpm-lock.yaml`; the only requirement is **network egress** to fetch
the (pinned) tools. The CI `codegen-check` step (in the `contracts` job, guarded on the `_generated/`
dirs) runs on every PR and fails on drift.

```
make codegen        # (re)generate all three artifact sets
make codegen-check  # fail if regenerating would change the committed artifacts (CI gate)
```

## Determinism (why the drift gate is stable)

`make codegen-check` regenerates into a temp dir and diffs against the committed artifacts, so
generation must be byte-reproducible. Three measures ensure that:

1. **Pinned tool versions** in `generate.sh`: `datamodel-code-generator==0.61.0`,
   `openapi-typescript@7.13.0`, `json-schema-to-zod@2.8.1`. CI fetches the same versions
   ephemerally, so output matches. Bumping a pin is a deliberate edit + a `make codegen` re-commit.
2. **`--disable-timestamp`** on `datamodel-codegen` (the only nondeterministic header line).
3. **`--formatters builtin`** so Pydantic formatting does not depend on floating `black` / `isort`
   versions.

The generated artifacts are not hand-maintained, so they are excluded from the other gates: ruff via
`extend-exclude` (`ruff.toml`), mypy via `ignore_errors` for `app.domain.models._generated.*`
(`mypy.ini`), and eslint / tsc via `ignorePatterns` / `exclude` (`web/.eslintrc.json`,
`web/tsconfig.json`).

## Regenerating after a schema change

Run `make codegen`, then review and commit the `_generated/` diff. If you forget, the `contracts` CI
job's `codegen-check` step fails on the drift. To pin the tools as dev dependencies instead of
ephemeral runners, add them (`uv add --dev datamodel-code-generator`; `pnpm add -D
openapi-typescript json-schema-to-zod`) and drop the `uvx` / `pnpm dlx` prefixes in `generate.sh` —
that is a genuine dependency install (CLAUDE.md §6, High-risk) and needs explicit approval.
