# T-111: Manuscript Witness Tree

## Goal

Implement the Manuscript Witness Tree artifact: a tree visualization of textual transmission lineage from manuscript families through critical editions to modern translations. LLM-assisted assembly (extracts transmission relationships from the evidence packet). Increments `generated_artifact_count`.

## Required Reads

- [`docs/schemas/manuscript-witness-tree.schema.json`](../../schemas/manuscript-witness-tree.schema.json).
- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — `<ManuscriptWitnessTreeView>` contract.
- [`docs/contracts/workflow-orchestration-contract.md`](../../contracts/workflow-orchestration-contract.md) — LLM composition pipeline.

## Files In Scope

- `backend/app/domain/services/manuscript_tree_composer.py` — A5-class composition; hierarchical tree assembly.
- `web/components/artifacts/ManuscriptWitnessTreeView.tsx` — D3 tree layout; node type icons (MSS, edition, translation).

## Acceptance Tests

1. Valid `ManuscriptWitnessTreeArtifact` produced; validates against schema.
2. Every node has at least one `citationRef`.
3. `provenance.allClaimsVerified=true`.
4. `billing_usage.generatedArtifactCount` increments by 1.

## Forbidden Scope

- Manuscript data outside the approved corpus.
