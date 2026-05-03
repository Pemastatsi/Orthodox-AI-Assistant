# API & Schema Versioning

Status: Canonical
Date: 2026-05-02

This document defines version formats and rollover rules for every "version" identifier in the system. A consistent format is required because cache keys (`docs/contracts/cache-key.md`) and route certification (`docs/schemas/model-route.schema.json`) depend on these versions.

## Canonical Version Format

```
YYYY-MM-DD.NN
```

- `YYYY-MM-DD` is the calendar date of the first activation in any environment.
- `NN` is a 1+ digit serial within that day, starting at `1`.
- Examples: `2026-05-01.1`, `2026-05-01.2`, `2026-12-31.10`.

This format is used for: `schemaVersion`, `promptVersion`, `corpusVersion`, `configVersion`, `calendarVersion`, `modelRouteId` (suffix), safety-config `version` field, and the `routeId` suffix.

The format is **lex-sortable** (within a year). Integer compare on `(YYYY-MM-DD, NN)` gives chronological order.

## Public HTTP API Versioning

- The public API is mounted under `/api/v1`. The `v1` segment increments only on **breaking** changes.
- Within `/api/v1`, additive changes (new optional fields, new endpoints, new error codes) are allowed without bumping the segment.
- Every response that carries a typed body includes a `schemaVersion` field (per `docs/schemas/verified-response.schema.json`). Clients SHOULD compare this against the version they were generated for and warn on mismatch.

## Deprecation Policy

When a public endpoint, field, or error code is to be removed:

1. Mark it `deprecated` in `docs/api/openapi.yaml` (using the OpenAPI `deprecated: true` flag) and in this document.
2. Send the `Sunset` HTTP header on every response from the deprecated path, per RFC 8594. Format: `Sunset: <RFC 7231 HTTP-date>`.
3. Deprecation period is **90 days** minimum. Removal earlier than 90 days requires founder sign-off.
4. After removal, return `410 Gone` with `code: "deprecated_removed"` for at least one further release.

## Schema Version Source of Truth

| Version | Source | Bumped when |
|---|---|---|
| `schemaVersion` | The schema's `$id` and a header comment in each `docs/schemas/*.schema.json`. The active value is in `app/core/config.py:ACTIVE_SCHEMA_VERSION`. | Any breaking change to a schema. Add-only changes do not bump. |
| `promptVersion` | Row in `prompt_versions` table; `prompt_version` column. | Any change to prompt body. |
| `corpusVersion` | Per-tenant column on `tenants.config.corpusVersion`, written by ingestion. | New approved chunks land or a chunk is reapproved with different text. |
| `configVersion` | `tenants.config_version`. | Any update to safe-config fields. |
| `calendarVersion` | `tenants.config.calendarProfile.version`. | Calendar profile change (fixed-feast or Paschalion). |
| `modelRouteId` | Full route id including the version suffix (`<name>@YYYY-MM-DD.NN`). Stored in `model_routes.route_id`; used directly in cache keys and certified-route lookups. | New certification of a provider/model/prompt/schema combination produces a new `routeId`. |

## Schema `$id` Versioning

JSON Schemas in `docs/schemas/` carry a stable `$id` (e.g., `verified-response.schema.json`) and an internal `description` noting the schema version. The `$id` itself does not embed a version because consumers use the `schemaVersion` field on responses to switch parsing logic.

If a schema undergoes a breaking change:

1. Create a new file `<name>.v2.schema.json` alongside the original.
2. Update the OpenAPI to reference both during the deprecation window using `oneOf`.
3. Update `ACTIVE_SCHEMA_VERSION` once the rollout is complete.
4. Remove the old file only after the deprecation period.

## Cache Implications

Per `docs/contracts/cache-key.md`, the cache key is derived from a stable serialization of:

- `tenantId`, normalized query, role, sessionHash (if applicable), `corpusVersion`, `promptVersion`, `modelRouteId`, `schemaVersion`, `configVersion`, `calendarVersion`.

Bumping any version **invalidates the cache** for that scope by changing the key. This is intentional. Therefore version bumps should be batched where possible to avoid unnecessary cache stampedes.

## Contract Doc Versioning

Markdown contracts in `docs/contracts/` carry a `Date:` line in the front matter. Material edits update the date. The index (`docs/DOCS_INDEX.md`) shows the current canonical date.

ADRs are immutable once `Accepted`. A correction or evolution opens a new ADR that supersedes the previous one and references it in its `Status:` line.

## Forbidden

- Mixing version formats (no semver, no integers, no UUIDs).
- Changing a version retroactively (a published `routeId` or `corpusVersion` is permanent).
- Skipping the cache-invalidation effect of a version bump (do not "ignore" a bump in the cache key recipe).
- Embedding a customer name, environment name, or secret in any version string.
