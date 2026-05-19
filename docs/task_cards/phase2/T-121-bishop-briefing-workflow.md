# T-121: Bishop Briefing Workflow

## Goal

Implement the Bishop Briefing artifact type: an institutional decision-support document generated for hierarchical use. Approval-gated (requires admin/owner sign-off before export). Establishes the full approval workflow UI (`<WorkflowApprovalQueue>`) and the `pending_review` → `approved` → `exported` state machine for all subsequent approval-gated types (T-122–T-125).

## Required Reads

- [`docs/adr/0016-workflow-approval-gates.md`](../../adr/0016-workflow-approval-gates.md) — approval lifecycle, roles, audit trail.
- [`docs/contracts/workflow-orchestration-contract.md`](../../contracts/workflow-orchestration-contract.md) — Stage 5 approval routing for high-stakes types.
- [`docs/contracts/export-format-contract.md`](../../contracts/export-format-contract.md) — DOCX/PDF format spec; provenance watermark.
- [`docs/contracts/rich-output-rendering.md`](../../contracts/rich-output-rendering.md) — `<WorkflowApprovalQueue>` contract.

## Files In Scope

- `backend/app/domain/services/bishop_briefing_composer.py` — A5-class composition; institutional tone; decision-support structure.
- `backend/app/api/v1/artifacts.py` — `POST /artifacts/{id}/approve`, `POST /artifacts/{id}/reject` endpoints.
- `backend/app/alembic/versions/0006_artifact_approvals.py` — `approvalRecord` JSONB column on `artifacts` table.
- `web/app/admin/artifacts/[artifactId]/review/page.tsx` — approval review page.
- `web/components/artifacts/WorkflowApprovalQueue.tsx` — admin queue with Approve / Reject / Request Changes.
- `.env.example` — `ACTIVE_MODEL_ROUTE_ARTIFACT_COMPOSE_BISHOP_BRIEFING`.

## Acceptance Tests

1. `POST /artifacts` with `artifactType='bishop_briefing'` transitions to `status='pending_review'` after verification (not `approved`).
2. `POST /artifacts/{id}/export` with `status='pending_review'` returns 422 `artifact_pending_approval`.
3. `POST /artifacts/{id}/approve` with admin role transitions to `status='approved'`.
4. `POST /artifacts/{id}/approve` with member role returns 403 `forbidden_role`.
5. After approval, `POST /artifacts/{id}/export` returns valid DOCX with provenance watermark.
6. `audit_entries` has rows for `artifact_pending_review`, `artifact_approved`, `artifact_exported` in order.
7. `POST /artifacts/{id}/reject` transitions to `status='rejected'`; member loses export access.
8. Approval timeout worker: artifact in `pending_review` for 31 days → `status='failed'`, `failureReason='approval_timeout'`.
9. Evidence coverage ≥ 10 admitted chunks (high-stakes threshold) before generation begins.
10. `<WorkflowApprovalQueue>` lists the artifact with Approve/Reject buttons; clicking Approve calls the API.

## Forbidden Scope

- Cross-tenant approval (admin from another tenant cannot approve).
- Auto-approval for `bishop_briefing` type.
- Email notifications for approval events (deferred to Phase 3).
