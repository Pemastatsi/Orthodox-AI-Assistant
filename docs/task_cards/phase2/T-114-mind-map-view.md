# T-114: Mind Map / Outline View

## Goal

Implement the Mind Map artifact: hierarchical outline derived deterministically from the verified response structure. No LLM call (derived from headings and sections already present in the Markdown answer from T-101). Does not increment `generated_artifact_count`. Renders inline alongside the answer.

## Required Reads

- [`docs/schemas/mind-map.schema.json`](../../schemas/mind-map.schema.json).
- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — `<MindMapView>` contract.
- [`docs/adr/0013-rich-output-format-strategy.md`](../../adr/0013-rich-output-format-strategy.md) — mind map is Tier 2 but deterministic; no artifact meter.

## Files In Scope

- `backend/app/domain/services/mind_map_assembler.py` — parse Markdown headings/sections from the verified response to build `MindMapArtifact`.
- `web/components/artifacts/MindMapView.tsx` — expandable/collapsible node tree; default expand depth 2.

## Acceptance Tests

1. `POST /artifacts` with `artifactType='mind_map'` and a rich-text verified response produces a valid `MindMapArtifact`.
2. `billing_usage.generatedArtifactCount` does NOT increment.
3. Expand/collapse works in `<MindMapView>`.
4. Mind map degrades gracefully when the source answer has no heading structure (root node = query text; no children).

## Forbidden Scope

- LLM-generated mind map enrichment (deterministic only).
- LLM calls of any kind in the assembler.
