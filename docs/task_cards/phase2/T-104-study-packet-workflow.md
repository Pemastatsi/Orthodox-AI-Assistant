# T-104: Study Packet Workflow

## Goal

Implement the Study Packet artifact type end-to-end: LLM-assisted A5-class composition from an evidence packet, provenance verification, export to PDF/DOCX, and multi-meter billing. This is the first artifact type to use LLM composition and establishes the full workflow orchestration pipeline for all Tier 3 document types. The Study Packet does not require approval (non-gated type).

## Required Reads

- [`docs/contracts/workflow-orchestration-contract.md`](../../contracts/workflow-orchestration-contract.md) — full pipeline stages.
- [`docs/contracts/artifact-spec-contract.md`](../../contracts/artifact-spec-contract.md) — artifact envelope, evidence coverage checks.
- [`docs/schemas/study-packet.schema.json`](../../schemas/study-packet.schema.json) — target output schema.
- [`docs/adr/0013-rich-output-format-strategy.md`](../../adr/0013-rich-output-format-strategy.md) — closed-corpus provenance rule.
- [`docs/adr/0016-workflow-approval-gates.md`](../../adr/0016-workflow-approval-gates.md) — Study Packet is NOT approval-gated.
- [`docs/adr/0015-multi-meter-billing.md`](../../adr/0015-multi-meter-billing.md) — `generated_artifact_count`.
- [`docs/contracts/export-format-contract.md`](../../contracts/export-format-contract.md) — PDF/DOCX output.
- [`docs/contracts/provider-interface.md`](../../contracts/provider-interface.md) — A5-class composition uses `LLMProvider.generate_structured`.
- [`docs/adr/0004-model-provider-routing.md`](../../adr/0004-model-provider-routing.md) — `purpose='artifact_compose_study_packet'` route.

## Files In Scope

**Backend:**
- `backend/app/domain/services/artifact_service.py` — implement full 6-stage orchestration pipeline for `study_packet` type.
- `backend/app/domain/services/study_packet_composer.py` — A5-class composition; uses `LLMProvider.generate_structured` with `StudyPacket` JSON schema; enforces closed-corpus rules.
- `backend/app/domain/services/provenance_verifier.py` — `verify_citation_provenance` implementation; quote-overlap check per `docs/contracts/quote-overlap-algorithm.md`.
- `backend/app/tasks/artifact_tasks.py` — arq task wrappers for each pipeline stage; run_in_background=true.
- `backend/app/alembic/versions/0003_artifact_workflow.py` — `audit_entries` action enum extension for artifact actions.
- `docs/schemas/study-packet.schema.json` — (already exists; no changes needed).
- `.env.example` — `ACTIVE_MODEL_ROUTE_ARTIFACT_COMPOSE_STUDY_PACKET`.

**Frontend:**
- `web/components/artifacts/DocumentPreview.tsx` — paginated document preview.
- `web/app/artifacts/[artifactId]/page.tsx` — artifact detail route.

## Acceptance Tests

1. `POST /artifacts` with `artifactType='study_packet'` and a valid `sourceRunId` creates an artifact row and enqueues the pipeline.
2. Within 60 seconds the artifact reaches `status='approved'` (auto-approved, no gate).
3. The generated `StudyPacket` JSON validates against `study-packet.schema.json`.
4. Every section in the packet has at least one `citationRef` pointing to an admitted chunk.
5. `provenance.allClaimsVerified=true` on the stored artifact.
6. A composition attempt with `admittedChunkCount < 5` fails with `failureReason='insufficient_evidence_coverage'`.
7. A composition attempt that produces a claim without a citationRef fails provenance verification; artifact `status='failed'`.
8. `POST /artifacts/{id}/export?format=pdf` returns a PDF with citation footnotes in every section.
9. `billing_usage.generatedArtifactCount` increments by 1 after pipeline completes (not after export).
10. `audit_entries` has rows for `artifact_requested`, `evidence_check_passed`, `artifact_auto_approved` in the correct order.
11. Composition arq task is idempotent: re-queuing the same `artifactId` does not generate a second artifact.

## Forbidden Scope

- Approval gates (Study Packet is non-gated; gated types are T-121–T-125).
- Audio export of the study packet (T-106).
- Slide deck export (T-112).
- Catechism, Bishop Briefing, or other document types (separate task cards).
- Free-form prompt editing for the composition step.
