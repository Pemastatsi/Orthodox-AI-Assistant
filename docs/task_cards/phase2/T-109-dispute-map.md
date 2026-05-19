# T-109: Dispute Map

## Goal

Implement the Dispute Map artifact: side-by-side theological position comparison (Orthodox, Catholic, Protestant, heterodox) with per-claim evidence anchors and contested-status badges. LLM-assisted assembly from the evidence packet. Increments `generated_artifact_count`.

## Required Reads

- [`docs/schemas/dispute-map.schema.json`](../../schemas/dispute-map.schema.json).
- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — `<DisputeMapView>` contract.
- [`docs/contracts/workflow-orchestration-contract.md`](../../contracts/workflow-orchestration-contract.md) — LLM composition pipeline.
- [`docs/adr/0013-rich-output-format-strategy.md`](../../adr/0013-rich-output-format-strategy.md) — Tier 2 LLM-assisted types increment the artifact meter.

## Files In Scope

- `backend/app/domain/services/dispute_map_composer.py` — A5-class composition; outputs `DisputeMapArtifact` JSON.
- `web/components/artifacts/DisputeMapView.tsx` — side-by-side columns; contested badge; evidence anchor popovers.
- `.env.example` — `ACTIVE_MODEL_ROUTE_ARTIFACT_COMPOSE_DISPUTE_MAP`.

## Acceptance Tests

1. `POST /artifacts` with `artifactType='dispute_map'` produces a valid `DisputeMapArtifact`.
2. Every position has at least one `citationRef`.
3. Claims with `status='insufficient_evidence'` render a visible badge; no fabricated content.
4. `provenance.allClaimsVerified=true`.
5. `billing_usage.generatedArtifactCount` increments by 1.

## Forbidden Scope

- Cross-tradition data sourced outside the approved corpus.
- Fabricating positions for traditions not represented in the evidence packet.
