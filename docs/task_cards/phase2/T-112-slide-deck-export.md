# T-112: Slide Deck Export

## Goal

Implement the Slide Deck artifact type: LLM-assisted outline generation from the evidence packet, rendered as a PPTX and/or Marp HTML slide deck with speaker notes and citation refs per slide. Increments `generated_artifact_count`. Certifies the `marp_v1` and `pptxgenjs_v1` `SlideRenderer` routes.

## Required Reads

- [`docs/schemas/slide-deck.schema.json`](../../schemas/slide-deck.schema.json).
- [`docs/contracts/export-format-contract.md`](../../contracts/export-format-contract.md) — PPTX format spec, citation per-slide.
- [`docs/contracts/artifact-provider-interface.md`](../../contracts/artifact-provider-interface.md) — `SlideRenderer` protocol.
- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — `<SlidePreview>` component.
- [`docs/contracts/workflow-orchestration-contract.md`](../../contracts/workflow-orchestration-contract.md) — pipeline stages.

## Files In Scope

- `backend/app/adapters/artifact_providers/slides/marp_adapter.py` — implement `SlideRenderer`; replaces stub from T-103.
- `backend/app/domain/services/slide_deck_composer.py` — A5-class outline composition; max 7 bullet points per slide; speaker notes from evidence.
- `web/components/artifacts/SlidePreview.tsx` — slide-by-slide viewer; speaker notes toggle.
- `.env.example` — `ACTIVE_ARTIFACT_ROUTE_SLIDES`.

## Acceptance Tests

1. `POST /artifacts` with `artifactType='slide_deck'` produces a valid `SlideDeckArtifact`.
2. `POST /artifacts/{id}/export?format=pptx` returns valid PPTX with citation refs on each slide.
3. Speaker notes present on content slides.
4. Final "Sources" slide lists all cited works.
5. `billing_usage.generatedArtifactCount` increments by 1.

## Forbidden Scope

- Reveal.js interactive HTML route (stub; certifiable in a later amendment).
- Video export.
