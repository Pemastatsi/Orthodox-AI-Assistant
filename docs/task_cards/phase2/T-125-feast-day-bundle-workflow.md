# T-125: Feast-Day Bundle Workflow

## Goal

Implement the Feast-Day Bundle artifact: liturgical occasion learning material combining the feast's theological significance, relevant patristic readings, iconography cross-references, and chant references. Approval-gated. Reuses T-121 approval infrastructure. Integrates with the Liturgical Calendar Overlay (T-116) and Iconographic Cards (T-117) and Chant (T-118).

## Required Reads

- [`docs/adr/0016-workflow-approval-gates.md`](../../adr/0016-workflow-approval-gates.md).
- [`docs/contracts/multimedia-integration-contract.md`](../../contracts/multimedia-integration-contract.md) — icon and chant cross-reference rules.
- [`docs/schemas/liturgical-context.schema.json`](../../schemas/liturgical-context.schema.json) — feast day context.
- [`docs/contracts/workflow-orchestration-contract.md`](../../contracts/workflow-orchestration-contract.md).

## Files In Scope

- `backend/app/domain/services/feast_day_composer.py` — A5-class; feast theological significance + icon cross-refs + chant cross-refs + patristic readings; outputs a structured bundle.
- `.env.example` — `ACTIVE_MODEL_ROUTE_ARTIFACT_COMPOSE_FEAST_DAY`.

## Acceptance Tests

1. `POST /artifacts` with `artifactType='feast_day_bundle'` and a feast-related evidence packet reaches `pending_review`.
2. Bundle contains: feast overview, ≥ 1 patristic reading section with citations, icon cross-refs list, chant cross-refs list.
3. Every textual claim has a `citationRef`.
4. Icon cross-refs point to entries in the curated iconography set (no AI-generated images).
5. Approval → export → DOCX/PDF with provenance watermark.
6. `audit_entries` trail complete.
7. Feast-Day Bundle generation fails with `insufficient_evidence_coverage` if the evidence packet has no feast-related chunks.

## Forbidden Scope

- Auto-approval.
- AI-generated iconographic content.
- Open-web feast day information.
