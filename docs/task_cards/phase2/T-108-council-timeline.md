# T-108: Council Timeline

## Goal

Implement the Council Timeline artifact: an interactive horizontal scrolling timeline of ecumenical and local councils with linked canons and key decisions. Assembly is deterministic (no LLM call) — data is derived from structured corpus metadata and the evidence packet. Renders client-side.

## Required Reads

- [`docs/schemas/council-timeline.schema.json`](../../schemas/council-timeline.schema.json).
- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — `<CouncilTimelineView>` contract.
- [`docs/adr/0013-rich-output-format-strategy.md`](../../adr/0013-rich-output-format-strategy.md) — council timeline does not increment `generated_artifact_count` (deterministic assembly).

## Files In Scope

- `backend/app/domain/services/council_timeline_assembler.py` — deterministic assembly from corpus chunk metadata; no LLM call.
- `web/components/artifacts/CouncilTimelineView.tsx` — horizontal scrollable timeline; era filter; council detail panel.
- `docs/schemas/council-timeline.schema.json` — (already exists; no changes needed).

## Acceptance Tests

1. `POST /artifacts` with `artifactType='council_timeline'` produces a valid `CouncilTimelineArtifact` without an LLM call.
2. Every event has at least one `citationRef`.
3. Events are sorted by `year` ascending.
4. `<CouncilTimelineView>` renders without errors; era filter changes visible events.
5. `billing_usage.generatedArtifactCount` does NOT increment (deterministic type).

## Forbidden Scope

- LLM-assisted council description generation (deterministic assembly only).
- Council data from outside the approved corpus (closed-corpus rule applies).
