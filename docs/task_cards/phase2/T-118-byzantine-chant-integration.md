# T-118: Byzantine Chant Integration

## Goal

Implement the Byzantine Chant integration: lookup traditional chant recordings from the locally hosted licensed audio set when troparia or hymns are referenced in an answer. Display playable chant links via `<ChantReference>` components. No billing meter. No AI-synthesized audio — ever.

## Required Reads

- [`docs/contracts/multimedia-integration-contract.md`](../../contracts/multimedia-integration-contract.md) — sourcing rules, chant reference fields, fallback.
- [`docs/contracts/artifact-provider-interface.md`](../../contracts/artifact-provider-interface.md) — `ChantProvider` protocol.
- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — chant reference rendering.

## Files In Scope

- `backend/app/adapters/artifact_providers/chant/curated_adapter.py` — implement `ChantProvider`; replaces stub.
- `backend/data/chant/` — curated chant metadata JSON + audio files (mp3/ogg) or CDN URL references.
- `backend/app/api/v1/chant.py` — `GET /chant/lookup?text={reference}&tradition={tradition}` endpoint.
- `web/components/artifacts/ChantReferenceCard.tsx` — inline playable card with hymn title, tone, tradition, attribution, and audio player.

## Acceptance Tests

1. `GET /chant/lookup?text=Troparion+of+Nativity` returns ≥ 1 `ChantReference` from the curated set (once curated set is populated).
2. `audioUrl` resolves to a platform CDN signed URL.
3. Fallback when no chant found: empty list; UI renders text-only reference.
4. AI synthesis API never called (assert in adapter tests).
5. All items in curated set have `licenseType` metadata.
6. `<ChantReferenceCard>` plays audio inline; keyboard accessible (Space = play/pause).

## Forbidden Scope

- AI-synthesized chant (permanent prohibition).
- Third-party streaming service integration at render time.
- Chant recordings of non-Orthodox or disputed tradition without annotation.
