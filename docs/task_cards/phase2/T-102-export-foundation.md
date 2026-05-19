# T-102: Export Foundation

## Goal

Implement PDF and DOCX export of any verified Q&A response. This is the simplest document-generation case: no LLM composition step, no workflow approval — the user asks to export the answer they already received, and the system formats it with citation footnotes and tenant branding. Establishes the `ExportProvider` infrastructure that all Tier 3 document generation (T-104, T-121–T-125) will reuse.

## Required Reads

- [`docs/contracts/artifact-spec-contract.md`](../../contracts/artifact-spec-contract.md) — artifact envelope, lifecycle.
- [`docs/contracts/artifact-provider-interface.md`](../../contracts/artifact-provider-interface.md) — `ExportProvider` protocol.
- [`docs/contracts/export-format-contract.md`](../../contracts/export-format-contract.md) — PDF/DOCX specs, citation footnoting, branding.
- [`docs/adr/0013-rich-output-format-strategy.md`](../../adr/0013-rich-output-format-strategy.md) — Tier 3 scope.
- [`docs/adr/0014-artifact-provider-abstraction.md`](../../adr/0014-artifact-provider-abstraction.md) — certification model.
- [`docs/adr/0015-multi-meter-billing.md`](../../adr/0015-multi-meter-billing.md) — `generated_artifact_count` meter.
- [`docs/contracts/db-schema.md`](../../contracts/db-schema.md) — `artifacts` table.
- [`docs/schemas/artifact.schema.json`](../../schemas/artifact.schema.json) — envelope schema.
- [`docs/schemas/artifact-request.schema.json`](../../schemas/artifact-request.schema.json) — request schema.
- [`docs/api/openapi.yaml`](../../api/openapi.yaml) — add `/artifacts` endpoints.

## Files In Scope

**Backend:**
- `backend/app/adapters/artifact_providers/` — new directory; `base.py` (ArtifactProvider Protocol), `export/react_pdf_adapter.py`, `export/docxjs_adapter.py`.
- `backend/app/domain/models/artifacts.py` — `Artifact`, `ArtifactRequest`, `ProvenanceReport`, `CostEstimate`.
- `backend/app/domain/services/artifact_service.py` — orchestration (Intake + Evidence + Generate + Verify stages for export type).
- `backend/app/domain/services/artifact_cache.py` — artifact cache key, get/set.
- `backend/app/api/v1/artifacts.py` — `POST /artifacts`, `GET /artifacts/{id}`, `POST /artifacts/{id}/export`.
- `backend/app/alembic/versions/0002_artifacts.py` — `artifacts` table migration.
- `backend/app/core/config.py` — `ACTIVE_ARTIFACT_ROUTE_EXPORT_PDF`, `ACTIVE_ARTIFACT_ROUTE_EXPORT_DOCX`.
- `docs/api/openapi.yaml` — `/artifacts` endpoints, `Artifact` response component, `ArtifactRequest` request component.
- `web/components/artifacts/ExportButton.tsx` — export trigger component.
- `web/components/artifacts/ArtifactStatusBadge.tsx` — status display.

**Config / env:**
- `.env.example` — add `ACTIVE_ARTIFACT_ROUTE_EXPORT_PDF`, `ACTIVE_ARTIFACT_ROUTE_EXPORT_DOCX`.

## Acceptance Tests

1. `POST /artifacts` with `artifactType='study_packet'` on a verified Q&A run returns `artifact.status='requested'` and a valid `artifactId`.
2. Within 30 seconds the artifact transitions to `status='approved'` (no approval gate for `study_packet`).
3. `POST /artifacts/{id}/export?format=pdf` returns a `Content-Type: application/pdf` binary response.
4. The exported PDF contains citation footnotes for every cited claim (verified by `tests/artifacts/test_export_citation_injection.py`).
5. `POST /artifacts/{id}/export?format=docx` returns a valid DOCX with the `OrthodoxAI_References` endnote section.
6. Attempting export on a non-existent artifact returns 404.
7. Cross-tenant artifact access attempt returns 404.
8. `billing_usage.generatedArtifactCount` increments by 1 after first export.
9. Identical artifact request (same `evidencePacketHash`, `locale`, `outputFormats`) returns cached artifact; `generatedArtifactCount` does not increment again.
10. Artifact provider route with `certification_status='draft'` is rejected at startup.

## Forbidden Scope

- Approval-gated artifact types (those are T-121–T-125).
- Audio (T-106) or PPTX (T-112).
- LLM-assisted composition (T-104 and later).
- Fetching external images or assets at export time.
- Generating artifacts without a valid `sourceRunId`.
