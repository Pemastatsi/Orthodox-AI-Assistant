# Error Taxonomy

Status: Canonical
Date: 2026-05-02

This document defines the canonical error codes used in the `ApiError` envelope (`docs/schemas/api-error.schema.json`). Every non-2xx response carries one code from this table. Internal services raise typed exceptions that map 1:1 to a code at the API boundary in `core/errors.py`.

## Code Format

- Codes are `lower_snake_case`, prefix-grouped by domain.
- A code is **stable** once it appears in this table. Renaming a code is a breaking change to consumers.
- Codes never carry tenant-specific or sensitive substrings.

## Codes

| Code | HTTP | Retryable | User-visible | Description |
|---|---|---|---|---|
| `auth_missing_token` | 401 | no | yes | No bearer token supplied. |
| `auth_invalid_token` | 401 | no | yes | Token failed Clerk verification or is expired. |
| `auth_missing_org` | 401 | no | yes | Token authenticates a user but no Clerk org claim is present (multi-org user has not selected one). |
| `tenant_not_found` | 404 | no | yes | Clerk org ID has no mapped active tenant. |
| `tenant_inactive` | 403 | no | yes | Tenant exists but is suspended, trial-expired, or closed. |
| `tenant_mismatch` | 403 | no | no | Request body or path references a tenant that does not match the authenticated principal. |
| `forbidden_role` | 403 | no | yes | Authenticated principal lacks the required role/scope. |
| `forbidden_visibility` | 403 | no | no | Resource visibility excludes the principal's role (e.g., admin_only chunk requested by member). |
| `validation_failed` | 422 | no | yes | Request body fails schema validation. `details.fieldErrors` lists offending fields. |
| `unsupported_media_type` | 415 | no | yes | Upload sourceType not one of `[pdf, txt, md, docx]`. |
| `not_found` | 404 | no | yes | Generic resource-not-found (run, ingest job, chunk). |
| `corpus_empty` | 409 | no | yes | Tenant has no approved chunks; closed-corpus answers cannot be served. |
| `unapproved_chunk` | 409 | no | no | Internal: an unapproved chunk reached the admission boundary. Indicates a logic bug; never returned to the user. |
| `safety_blocked` | 200 | no | yes | Safety policy returned `block_with_redirect`. Returned with 200 inside `VerifiedResponse`, NOT as an error envelope; listed here only because pastoral filters use this `reason_code`. |
| `verifier_failed` | 200 | no | yes | A6 rejected the composed answer. Returned inside `VerifiedResponse` with `verification.passed=false`; the API responds 200 with `handling=insufficient_evidence`. |
| `quota_exceeded` | 402 | no | yes | Tenant has exceeded billing quota for the period. |
| `rate_limited` | 429 | yes | yes | Per-tenant or per-user rate limit hit. `retryAfterSeconds` populated. |
| `provider_unavailable` | 503 | yes | yes | Anthropic or OpenAI returned 5xx or timeout. |
| `provider_refused` | 502 | no | yes | Provider returned a structured refusal that cannot be reframed safely. |
| `provider_invalid_response` | 502 | yes | no | Provider returned content that failed schema validation. Usually a transient. |
| `cache_unavailable` | 503 | yes | no | Redis is down. Service degrades but does not fail the request unless the cache is required (e.g., cache-store path of a fresh run). |
| `qdrant_unavailable` | 503 | yes | yes | Vector store is down. |
| `db_unavailable` | 503 | yes | yes | Postgres is down or transaction failed. |
| `ingest_invalid` | 422 | no | yes | Uploaded file failed extraction or virus scan. |
| `ingest_too_large` | 413 | no | yes | Uploaded file exceeds tenant size limit. |
| `webhook_bad_signature` | 401 | no | no | Stripe / Clerk / Make.com HMAC verification failed. |
| `webhook_replay` | 409 | no | no | Webhook idempotency key has already been processed. |
| `precondition_failed` | 412 | no | yes | Optimistic-concurrency check failed (e.g., `If-Match` on `PATCH /tenant/config` did not match the current `configVersion`). The client should `GET` the resource, merge changes, and retry. |
| `internal_error` | 500 | no | yes | Catch-all for unexpected exceptions. The traceId is the only customer-facing handle. |

## Non-Code Reasons

These identifiers appear in `FlaggedQuery.flagReason` (analytics) but are **not** API error codes. They are listed here for cross-reference only:

- `hard_safety_trigger` — flag-reason for queries that matched a `hard_trigger: true` rule in `config/sensitivity_keywords.yaml`. The user-facing handling is `block_with_redirect`, returned with HTTP 200 inside `VerifiedResponse`. Not returned as an `ApiError`.
- `red_tier`, `insufficient_evidence`, `block_with_redirect`, `verifier_failed`, `user_reported` — also flag-reasons; same rule applies (analytics only, not API codes).

## Mapping Rules

1. Every uncaught exception in the API layer becomes `internal_error`. The original exception is logged with the `traceId`; the response body never includes the exception message.
2. Internal-only codes (`tenant_mismatch`, `unapproved_chunk`, `provider_invalid_response`, `forbidden_visibility`, `webhook_bad_signature`, `webhook_replay`) are logged with full context but the user-facing message is generic ("Request could not be completed") to avoid leaking internal state.
3. `retryable: yes` codes set `retryAfterSeconds`. The frontend honors it; clients SHOULD respect it.
4. Codes 4xx with `user-visible: yes` are surfaced verbatim by the frontend with a localized message lookup keyed by `code`. Codes with `user-visible: no` show a generic error UI.

## Adding a Code

To add a code:

1. Append a row above with all five columns.
2. Add the code to the `enum` list in `app/core/errors.py` (when the backend exists).
3. Reference it from at least one OpenAPI response in `docs/api/openapi.yaml`.
4. If user-visible, add a localized message stub to the frontend.

Removing a code is a breaking API change; mark it `deprecated` in this table for at least one full release before deletion.
