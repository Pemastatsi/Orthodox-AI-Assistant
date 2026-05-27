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
7. Prompt templates are version-controlled artifacts under `/prompts/` per `docs/contracts/prompt-management.md` (GS-3). The `prompt_version` field stamped on every `ModelRoute` row corresponds to a versioned file path under `/prompts/`; embedded string-literal prompts in agent code are forbidden. Any change to a file under `/prompts/` triggers a CI gate (safety-suite + retrieval-eval) before the change can merge, regardless of whether the in-database route was already certified for the prior `prompt_version`.

## Route Certification Protocol

A `model_routes` row may serve user traffic only when `certification_status='certified'`. The transition from any other status to `certified` is governed by:

1. **Authority.** Only a user with `role='owner'` may PATCH `certification_status` to `certified`. Other admin actions (`draft`/`experiment`/`deprecated`) may be performed by `admin` or `owner`.
2. **Passing definition.** A "passing" safety-suite run means: every one of the 20 canonical cases in `tests/safety/test_20_queries.py::CANONICAL_SAFETY_CASES` produces both `outcome.handling == case.expected_handling` and `outcome.sensitivityPrimary == case.expected_sensitivity` when executed against the candidate route through the standard A1–A6 pipeline. No tolerance for YELLOW where the case expects GREEN, etc.
3. **Aggregation: `safety_suite_runs`.** A safety-suite execution produces 20 `run_traces` rows (one per case). The harness MUST insert a single `safety_suite_runs` row that aggregates them, with:
   - `safety_suite_run_id`: ULID assigned at the start of the suite execution.
   - `purpose`/`provider`/`model`/`prompt_version`/`schema_version`: copied from the candidate route under test.
   - `case_count`: 20 (CHECK-constrained).
   - `case_run_ids`: array of exactly 20 `run_traces.run_id` values, ordered by case `id`.
   - `passed`: `true` only if every case satisfies the passing definition above; otherwise `false`.
   - `failure_summary`: empty when `passed=true`; per-failed-case detail when `passed=false`.
   - `initiated_by`: the `users.user_id` that started the suite.
   On insert, an `audit_entries` row with `action='safety_suite_run_completed'`, `resource_type='safety_suite_run'`, `resource_id=safety_suite_run_id` MUST be written. See `docs/contracts/db-schema.md` §`safety_suite_runs`.
4. **Recording on the route.** The certifying owner sets `model_routes.safety_suite_run_id` to the **`safety_suite_runs.safety_suite_run_id`** of the passing aggregate (NOT to a single `run_traces.run_id`); `certified_by` to their `users.user_id`; and `certified_at` to the timestamp. The PATCH writes an `audit_entries` row with `action='model_route_certified'`. The API MUST refuse the certification PATCH when the referenced `safety_suite_runs` row does not exist, has `passed=false`, or has a different `purpose`/`prompt_version`/`schema_version` triple than the route being certified.
5. **Startup enforcement.** Service startup loads the active route ids from `.env` (`ACTIVE_MODEL_ROUTE_*`) and refuses to start if any active id resolves to a row whose `certification_status != 'certified'` or whose `deprecated_at IS NOT NULL`.
6. **Revocation.** A regression flips the row to `deprecated`; the service refuses the next deploy until a different certified route is named in `.env`. Revocation is `admin`+ but never required to be `owner` (you should be able to take a bad route out fast).

## Prompt-Version Lifecycle (GS-3)

Prompt templates are first-class certified artifacts, on par with provider/model/schema. The lifecycle:

1. **Authoring.** A new prompt version is committed as a new file under `/prompts/{stage}/{language}/{version}.{j2,yaml}` per `docs/contracts/prompt-management.md`. The directory layout makes `prompt_version` a path identifier, not a free-form string. Editing an existing file in place is forbidden — version it.
2. **CI gate.** A diff under `/prompts/` triggers the safety-suite (`backend/tests/safety/test_20_queries_harness.py`) and retrieval-eval suites in CI against a candidate `ModelRoute` that references the new `prompt_version`. The PR cannot merge with either suite red.
3. **Route certification.** Promoting a route from `experiment` to `certified` requires both (a) a passing safety-suite aggregate per the protocol above and (b) the `prompt_version` referenced by the route corresponds to an existing file under `/prompts/`. The API MUST refuse the certification PATCH when the prompt file is missing from disk.
4. **Forensic auditability.** The `RunTrace.stages[].details.promptVersion` and `model_route_invocations.prompt_version` fields preserve which prompt version served which user, so post-incident analysis can reconstruct exactly which template wording was active for any historical query.

The runtime piece of decision register row 6 — admin-facing free-form prompt editing with preview + rollback — remains post-MVP. The lifecycle above governs platform-authored prompt templates only.

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
