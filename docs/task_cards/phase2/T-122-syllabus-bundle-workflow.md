# T-122: Syllabus Bundle Workflow

## Goal

Implement the Syllabus Bundle artifact: a full course outline for seminary use with weekly sessions, reading assignments, and learning objectives, each grounded in the approved corpus. Approval-gated. Reuses the approval workflow infrastructure from T-121.

## Required Reads

- [`docs/adr/0016-workflow-approval-gates.md`](../../adr/0016-workflow-approval-gates.md).
- [`docs/contracts/workflow-orchestration-contract.md`](../../contracts/workflow-orchestration-contract.md).
- [`docs/contracts/export-format-contract.md`](../../contracts/export-format-contract.md).

## Files In Scope

- `backend/app/domain/services/syllabus_composer.py` — A5-class composition; week-by-week structure; learning objectives per session.
- `.env.example` — `ACTIVE_MODEL_ROUTE_ARTIFACT_COMPOSE_SYLLABUS`.

## Acceptance Tests

1. `POST /artifacts` with `artifactType='syllabus_bundle'` reaches `pending_review` after verification.
2. Evidence coverage ≥ 10 admitted chunks.
3. Every weekly session has at least one `citationRef`.
4. Approval flow (approve → export) produces valid DOCX/PDF.
5. `audit_entries` trail complete.

## Forbidden Scope

- Auto-approval.
- Generating syllabi from general academic sources (closed-corpus only).
