# T-117: Iconographic Reference Cards

## Goal

Implement the Iconographic Reference Card feature: lookup icons from the locally hosted curated licensed set relevant to the theological topic of an answer. Display `<IconCard>` components alongside the answer panel. No billing meter. No AI-generated images — ever. The curated set must be populated with at least 20 canonical icons before this feature is enabled.

## Required Reads

- [`docs/contracts/multimedia-integration-contract.md`](../../contracts/multimedia-integration-contract.md) — sourcing rules, licensing, fallback.
- [`docs/contracts/artifact-provider-interface.md`](../../contracts/artifact-provider-interface.md) — `IconographyProvider` protocol.
- [`docs/schemas/iconographic-card.schema.json`](../../schemas/iconographic-card.schema.json).
- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — `<IconCard>` contract.

## Files In Scope

- `backend/app/adapters/artifact_providers/iconography/curated_adapter.py` — implement `IconographyProvider`; replaces stub; serves from locally hosted curated set.
- `backend/data/icons/` — curated icon metadata JSON + image files (PNG/WebP) or CDN URL references.
- `backend/app/api/v1/iconography.py` — `GET /iconography/lookup?concept={concept}` endpoint.
- `web/components/artifacts/IconCard.tsx` — icon image + theological caption + corpus cross-ref link.

## Acceptance Tests

1. `GET /iconography/lookup?concept=theosis` returns ≥ 1 `IconCard` from the curated set.
2. `imageUrl` resolves to a platform CDN URL (not a third-party URL); image loads.
3. Fallback when no icon found: empty list returned; UI renders "No canonical icon available" placeholder.
4. AI-generation API is never called (assert no `openai.images` or similar call in adapter tests).
5. All icons in curated set have `licenseType` metadata; items without a valid license fail schema validation.
6. `<IconCard>` renders alt text; image has correct aspect ratio without layout shift.

## Forbidden Scope

- AI-generated images (permanent prohibition; certification fails if the adapter calls an image generation API).
- Web scraping icons from third-party sites.
- User-contributed icons without platform admin review.
