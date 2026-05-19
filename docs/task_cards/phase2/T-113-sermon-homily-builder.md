# T-113: Sermon/Homily Builder

## Goal

Implement the Sermon Outline artifact: structured homily from a Gospel pericope with patristic commentary blocks, an outline for each main point, and a conclusion. LLM-assisted. Exports as DOCX and PDF. Increments `generated_artifact_count`. Not approval-gated (self-service).

## Required Reads

- [`docs/schemas/sermon-outline.schema.json`](../../schemas/sermon-outline.schema.json).
- [`docs/contracts/export-format-contract.md`](../../contracts/export-format-contract.md).
- [`docs/contracts/workflow-orchestration-contract.md`](../../contracts/workflow-orchestration-contract.md).

## Files In Scope

- `backend/app/domain/services/sermon_composer.py` — A5-class; outputs `SermonOutlineArtifact`.
- `web/components/artifacts/DocumentPreview.tsx` — reused from T-102 for sermon preview.

## Acceptance Tests

1. Valid `SermonOutlineArtifact` produced with `pericope`, `introduction`, ≥ 1 `point`, `conclusion`.
2. Every point has at least one `citationRef` and at least one `patristicCommentary` entry.
3. `provenance.allClaimsVerified=true`.
4. DOCX export contains citation footnotes; PDF export has footnotes.
5. `billing_usage.generatedArtifactCount` increments by 1.

## Forbidden Scope

- Audio synthesis of the sermon (T-106 handles audio; not automatically triggered here).
- Approval gate (sermon outline is self-service).
