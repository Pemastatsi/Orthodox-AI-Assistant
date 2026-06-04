#!/usr/bin/env bash
#
# REC-009 schema-to-code generators (SCAFFOLD — see scripts/codegen/README.md).
#
# Regenerates the committed `_generated/` artifacts from the canonical schemas, or, with
# `--check`, verifies they are up to date (the CI drift gate). Generators run ephemerally via
# `uvx` / `pnpm dlx`, so NO pyproject.toml / package.json / lockfile changes are needed — the
# only requirement is network egress to fetch the tools.
#
# NOTE: artifacts are intentionally NOT generated in Phase 1 (this is the scaffold). Enabling is a
# future, owner-approved step: run `make codegen` once, review, and commit the output; the CI
# `codegen-check` step then activates automatically (it is guarded on the `_generated/` dirs
# existing). The exact generator flags below may need tuning on first real run.
set -euo pipefail

CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

SCHEMAS="docs/schemas"
OPENAPI="docs/api/openapi.yaml"
PY_OUT="backend/app/domain/models/_generated"
TS_CLIENT="web/lib/api-client.generated.ts"
ZOD_OUT="web/lib/schemas/_generated"

generate() {
  local py_out="$1" ts_client="$2" zod_out="$3"
  mkdir -p "$py_out" "$zod_out" "$(dirname "$ts_client")"

  # 1) Pydantic v2 models from the JSON Schemas.
  uvx --from datamodel-code-generator datamodel-codegen \
    --input "$SCHEMAS" --input-file-type jsonschema \
    --output "$py_out" --output-model-type pydantic_v2.BaseModel \
    --use-standard-collections --use-schema-description --snake-case-field

  # 2) TypeScript types for the frontend API client from the OpenAPI spec.
  pnpm dlx openapi-typescript "$OPENAPI" -o "$ts_client"

  # 3) Zod validators from the JSON Schemas (one module per schema).
  for f in "$SCHEMAS"/*.json; do
    name="$(basename "$f" .schema.json)"
    pnpm dlx json-schema-to-zod -i "$f" -o "$zod_out/$name.ts"
  done
}

if [ "$CHECK" -eq 1 ]; then
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  generate "$tmp/models" "$tmp/api-client.generated.ts" "$tmp/schemas"
  rc=0
  diff -ruN "$PY_OUT" "$tmp/models" || rc=1
  diff -ruN "$TS_CLIENT" "$tmp/api-client.generated.ts" || rc=1
  diff -ruN "$ZOD_OUT" "$tmp/schemas" || rc=1
  if [ "$rc" -ne 0 ]; then
    echo "codegen drift: generated artifacts differ from the schemas. Run 'make codegen' and commit." >&2
    exit 1
  fi
  echo "codegen-check OK — generated artifacts match the schemas."
else
  generate "$PY_OUT" "$TS_CLIENT" "$ZOD_OUT"
  echo "codegen complete — review and commit: $PY_OUT, $TS_CLIENT, $ZOD_OUT"
fi
