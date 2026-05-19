# T-110: Citation Network Graph

## Goal

Implement the Citation Network artifact: a force-directed graph showing which fathers cite which other fathers, with edge thickness proportional to citation frequency. Assembly is deterministic from chunk metadata — no LLM call. Does not increment `generated_artifact_count`.

## Required Reads

- [`docs/schemas/citation-network.schema.json`](../../schemas/citation-network.schema.json).
- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — `<CitationNetworkView>` contract.
- [`docs/contracts/artifact-provider-interface.md`](../../contracts/artifact-provider-interface.md) — `GraphRenderer` protocol.

## Files In Scope

- `backend/app/domain/services/citation_network_assembler.py` — deterministic assembly from `chunks` metadata (no LLM call).
- `web/components/artifacts/CitationNetworkView.tsx` — D3 force-directed graph; edge thickness = frequency.

## Acceptance Tests

1. `POST /artifacts` with `artifactType='citation_network'` produces a valid `CitationNetworkArtifact` without LLM call.
2. All `chunkIds` in nodes belong to the requesting tenant.
3. `billing_usage.generatedArtifactCount` does NOT increment.
4. `minEdgeWeight` filter applied before rendering; edges below threshold hidden.

## Forbidden Scope

- LLM inference of citation relationships (deterministic metadata only).
