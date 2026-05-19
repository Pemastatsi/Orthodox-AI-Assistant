# T-119: Holy Land + Monastery Map

## Goal

Implement the Monastery Map artifact: an interactive Leaflet map with self-hosted tiles showing patriarchates, monastic houses, Holy Land pilgrimage sites, council locations, and corpus reference sites. GeoJSON data is a static curated dataset; no runtime calls to a third-party mapping API. `corpus_reference` layer is populated from entities in the evidence packet. No billing meter for the base map (deterministic assembly).

## Required Reads

- [`docs/contracts/multimedia-integration-contract.md`](../../contracts/multimedia-integration-contract.md) — map data sources, tile server, fallback behavior.
- [`docs/contracts/artifact-provider-interface.md`](../../contracts/artifact-provider-interface.md) — `MapRenderer` protocol.
- [`docs/schemas/geographic-overlay.schema.json`](../../schemas/geographic-overlay.schema.json).
- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — `<MonasteryMap>` contract.

## Files In Scope

- `backend/app/adapters/artifact_providers/map/leaflet_adapter.py` — implement `MapRenderer`; replaces stub.
- `backend/data/geo/orthodox_sites.geojson` — curated GeoJSON dataset (patriarchates, monasteries, Holy Land sites, council locations).
- `backend/app/domain/services/geo_overlay_assembler.py` — assembles `GeographicOverlayArtifact` from static dataset + corpus entity references.
- `web/components/artifacts/MonasteryMap.tsx` — Leaflet map with self-hosted tiles; marker click → detail panel.
- `web/public/tiles/` — self-hosted tile files (MBTiles converted to static tiles or served from tile server).
- `.env.example` — `TILE_SERVER_URL` (internal; not third-party).

## Acceptance Tests

1. `POST /artifacts` with `artifactType='monastery_map'` produces a valid `GeographicOverlayArtifact`.
2. All markers have `lat`, `lng`, `name`.
3. `corpus_reference` layer markers correspond to admitted chunk location entities.
4. Map renders without third-party network requests (assert no calls to `tile.openstreetmap.org`, `api.mapbox.com`, etc.).
5. Tile server unavailability: map renders with markers on blank canvas; non-blocking banner shown.
6. `billing_usage.generatedArtifactCount` does NOT increment.

## Forbidden Scope

- Third-party tile API calls at render time.
- Mapbox route certification (stub; certifiable in a future amendment for Enterprise tenants).
- Real-time geolocation of users.
