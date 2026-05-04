# ADR 0004: Model Provider Routing

Date: 2026-04-26 (amended 2026-05-02 to add Route Certification Protocol and Provider Outage Policy sections)
Status: Accepted

## Context

The project should support provider swaps and experiments, but theological behavior must be certified. "Plug and play" cannot mean arbitrary production model switching.

## Decision

Build a provider interface from day one. Only certified provider/model/prompt/schema routes may serve production users.

## Interface

**Authoritative source for the interface surface:** `docs/contracts/provider-interface.md`. The methods listed below capture the original ADR scope; current additions (notably `embed_texts`, `supports_embeddings`, `supports_json_mode`) are documented in the contract file and surface in the `LLMProvider` Protocol there. Treat any conflict between this ADR section and `provider-interface.md` as resolved in favor of the contract.

Provider adapters expose:

- `generate_structured`
- `generate_text`
- `stream_text`
- `count_tokens`
- `supports_prompt_cache`
- `supports_batch`

## Rules

1. A1/A2 may run as one structured low-cost `QueryAnalyzer` call.
2. A4 remains deterministic in MVP.
3. A5 uses the highest-scrutiny certified composition route.
4. A6 runs deterministic checks before any optional verifier model call.
5. Every production route is certified by provider, model, prompt version, schema version, and safety-suite result.
6. Experiments may be logged but cannot serve users until certified.

## Route Certification Protocol

A `model_routes` row may serve user traffic only when `certification_status='certified'`. The transition from any other status to `certified` is governed by:

1. **Authority.** Only a user with `role='owner'` may PATCH `certification_status` to `certified`. Other admin actions (`draft`/`experiment`/`deprecated`) may be performed by `admin` or `owner`.
2. **Passing definition.** A "passing" safety-suite run means: every one of the 20 canonical cases in `tests/safety/test_20_queries.py` produces both `outcome.handling == case.expected_handling` and `outcome.sensitivityPrimary == case.expected_sensitivity` when executed against the candidate route through the standard A1–A6 pipeline. No tolerance for YELLOW where the case expects GREEN, etc.
3. **Recording.** The certifying owner sets `safety_suite_run_id` to the `run_traces.run_id` of the passing run; `certified_by` to their `users.user_id`; and `certified_at` to the timestamp. The PATCH writes an `audit_entries` row with `action='model_route_certified'`.
4. **Startup enforcement.** Service startup loads the active route ids from `.env` (`ACTIVE_MODEL_ROUTE_*`) and refuses to start if any active id resolves to a row whose `certification_status != 'certified'` or whose `deprecated_at IS NOT NULL`.
5. **Revocation.** A regression flips the row to `deprecated`; the service refuses the next deploy until a different certified route is named in `.env`. Revocation is `admin`+ but never required to be `owner` (you should be able to take a bad route out fast).

## Provider Outage Policy (Phase 1)

When the certified provider for a purpose returns 5xx, times out, or rate-limits:

1. There is **no automatic cross-provider fallback** in Phase 1. The request fails with the matching code from `docs/contracts/error-taxonomy.md` (`provider_unavailable` 503, `rate_limited` 429, etc.) and `Retry-After` populated when the provider supplied one.
2. Within-provider retries are bounded by the adapter's existing retry policy (one structured-output reformat retry per `provider-interface.md`).
3. The user is shown a generic "service is temporarily unavailable" message; no provider name is leaked in the user-facing text.
4. The orchestrator does not auto-degrade the request to a different `purpose` (e.g., it will not silently skip A5 composition and return a stub answer).

Cross-provider failover is deferred to Phase 3+ and requires a follow-up ADR per the rule above.

## Tests

- Unknown route names fail configuration validation.
- Model swaps require a recorded safety-suite pass.
- A4 has no model route in MVP.
- Structured calls validate output against schemas.
- Startup test: setting an active route to a row with `certification_status='draft'` causes the service to refuse to start with a clear error.
- Authorization test: a user with `role='admin'` who PATCHes a route to `certified` receives `forbidden_role`.
- Outage test: when the provider adapter raises `ProviderUnavailableError`, the API returns 503 `provider_unavailable` with no automatic fallback to an alternate certified route.
