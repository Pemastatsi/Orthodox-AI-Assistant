# T-124: Parish Bulletin Insert Workflow

## Goal

Implement the Parish Bulletin Insert artifact: a short-form A5-page layperson-grade explainer of a theological topic for distribution in a parish bulletin. Approval-gated (distributed publicly under the parish name). Reuses T-121 approval infrastructure. Uses A5 page size PDF export with simplified citation style.

## Required Reads

- [`docs/adr/0016-workflow-approval-gates.md`](../../adr/0016-workflow-approval-gates.md).
- [`docs/contracts/export-format-contract.md`](../../contracts/export-format-contract.md) — Parish Bulletin Insert uses A5 format with simplified in-text citations.
- [`docs/contracts/workflow-orchestration-contract.md`](../../contracts/workflow-orchestration-contract.md).

## Files In Scope

- `backend/app/domain/services/parish_bulletin_composer.py` — A5-class; layperson reading level; max 500 words; citations as parenthetical.
- `.env.example` — `ACTIVE_MODEL_ROUTE_ARTIFACT_COMPOSE_PARISH_BULLETIN`.

## Acceptance Tests

1. `POST /artifacts` with `artifactType='parish_bulletin_insert'` reaches `pending_review`.
2. Body ≤ 600 words; citations are parenthetical (not footnotes) per A5 format spec.
3. Approval → export → A5 PDF.
4. `audit_entries` trail complete.

## Forbidden Scope

- Auto-approval.
- Footnote citations (parenthetical only for this type per export-format-contract).
