# Schema-to-code generators (REC-009)

**Status: scaffold.** The wiring (Makefile targets, generator script, `.gitattributes`, guarded CI
step) is in place, but **no `_generated/` artifacts are produced yet** and **no dependencies are
installed**. This was a deliberate scope decision; enabling is a future, owner-approved step (below).

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
the tools. This is why the scaffold keeps CI green: it touches no lockfile, and the CI drift check is
guarded to skip until artifacts exist.

```
make codegen        # (re)generate all three artifact sets
make codegen-check  # fail if regenerating would change the committed artifacts (CI gate)
```

## Enabling (future, owner-approved)

1. Confirm network egress for `uvx` / `pnpm dlx` in the dev + CI environments.
2. Run `make codegen`; review the output (alias/casing conventions — the hand-written `WireModel`
   uses `alias_generator=to_camel`; tune the `datamodel-codegen` flags in `generate.sh` to match).
3. Commit the `_generated/` artifacts. The guarded CI `codegen-check` step in the `contracts` job
   (`.github/workflows/ci-safety-gate.yml`) activates automatically once the dirs exist.
4. If pinned tool versions are preferred over ephemeral runners, add the three tools as dev
   dependencies (`uv add --dev datamodel-code-generator`; `pnpm add -D openapi-typescript
   json-schema-to-zod`) and drop the `uvx` / `pnpm dlx` prefixes in `generate.sh`. That step is a
   genuine dependency install (CLAUDE.md §6, High-risk) and needs explicit approval.
