# T-103: Artifact Provider Abstraction

## Goal

Implement the full `ArtifactProvider` protocol hierarchy and the provider registry / certification flow. This task builds the infrastructure layer that all subsequent artifact tasks (T-104–T-125) depend on. The concrete adapters for graph rendering, TTS, maps, morphology, iconography, and chant are stubs in this task; their certification happens in the tasks that use them.

## Required Reads

- [`docs/contracts/artifact-provider-interface.md`](../../contracts/artifact-provider-interface.md) — full interface hierarchy.
- [`docs/adr/0014-artifact-provider-abstraction.md`](../../adr/0014-artifact-provider-abstraction.md) — certification model.
- [`docs/contracts/provider-interface.md`](../../contracts/provider-interface.md) — `LLMProvider` pattern to mirror.
- [`docs/adr/0004-model-provider-routing.md`](../../adr/0004-model-provider-routing.md) — `model_routes` certification lifecycle.
- [`docs/contracts/db-schema.md`](../../contracts/db-schema.md) — `model_routes` table extensions for artifact-namespace purposes.
- [`docs/schemas/model-route.schema.json`](../../schemas/model-route.schema.json) — add artifact-namespace `purpose` values.

## Files In Scope

**Backend:**
- `backend/app/adapters/artifact_providers/base.py` — `ArtifactProvider`, `GraphRenderer`, `ExportProvider`, `TTSProvider`, `SlideRenderer`, `MapRenderer`, `MorphologyProvider`, `IconographyProvider`, `ChantProvider` Protocols.
- `backend/app/adapters/artifact_providers/graph/d3_adapter.py` — `GraphRenderer` stub (raises `NotImplementedError`; certifiable placeholder for T-105).
- `backend/app/adapters/artifact_providers/tts/openai_tts_adapter.py` — `TTSProvider` stub (certifiable placeholder for T-106).
- `backend/app/adapters/artifact_providers/slides/marp_adapter.py` — `SlideRenderer` stub (for T-112).
- `backend/app/adapters/artifact_providers/map/leaflet_adapter.py` — `MapRenderer` stub (for T-119).
- `backend/app/adapters/artifact_providers/morphology/morphgnt_adapter.py` — `MorphologyProvider` stub (for T-115).
- `backend/app/adapters/artifact_providers/iconography/curated_adapter.py` — `IconographyProvider` stub (for T-117).
- `backend/app/adapters/artifact_providers/chant/curated_adapter.py` — `ChantProvider` stub (for T-118).
- `backend/app/domain/services/artifact_provider_registry.py` — loads active routes from env vars; validates `certification_status='certified'`; startup enforcement.
- `backend/app/core/config.py` — all `ACTIVE_ARTIFACT_ROUTE_*` env vars.
- `.env.example` — all `ACTIVE_ARTIFACT_ROUTE_*` env vars (empty defaults; absence disables cleanly).
- `docs/schemas/model-route.schema.json` — add artifact-namespace `purpose` enum values.

**Tests:**
- `tests/unit/test_artifact_provider_registry.py` — startup rejection of draft routes; missing env vars disable cleanly; correct adapter returned per purpose.

## Acceptance Tests

1. `ArtifactProvider` Protocol is `@runtime_checkable`; all concrete adapter stubs satisfy it at import time.
2. Startup with an `ACTIVE_ARTIFACT_ROUTE_GRAPH` env var pointing to a `draft` model-route row raises `ConfigurationError`.
3. Startup with a missing `ACTIVE_ARTIFACT_ROUTE_GRAPH` env var succeeds; `GraphRenderer` feature reports unavailable.
4. `artifact_provider_registry.get_provider('artifact_graph')` returns the `D3Adapter` stub when a certified route is configured.
5. Calling `D3Adapter.generate(...)` raises `NotImplementedError` (stub behavior; replaced in T-105).
6. `ArtifactProvider.verify_citation_provenance` is a required method; a Protocol subclass that omits it fails the `runtime_checkable` check.
7. `model-route.schema.json` validates a row with `purpose='artifact_graph'`.
8. `redocly lint docs/api/openapi.yaml` exits 0.

## Forbidden Scope

- Implementing any concrete artifact generation (that is the job of T-104–T-125).
- Adding Stripe meter reporting (T-107).
- Adding the `artifacts` database table migration (T-102 owns that).
- Certifying any adapter route (stubs only in this task).
