# T-123: Catechism Lesson Plan Workflow

## Goal

Implement the Catechism Lesson Plan artifact: structured adult inquirer / catechumen modules with doctrine topics, discussion questions, and assigned readings. Approval-gated (pastoral document distributed to catechumens). Reuses T-121 approval infrastructure.

## Required Reads

- [`docs/adr/0016-workflow-approval-gates.md`](../../adr/0016-workflow-approval-gates.md).
- [`docs/contracts/workflow-orchestration-contract.md`](../../contracts/workflow-orchestration-contract.md).

## Files In Scope

- `backend/app/domain/services/catechism_composer.py` — A5-class; modular lessons; target reading level: adult newcomers.
- `.env.example` — `ACTIVE_MODEL_ROUTE_ARTIFACT_COMPOSE_CATECHISM`.

## Acceptance Tests

1. `POST /artifacts` with `artifactType='catechism_lesson_plan'` reaches `pending_review`.
2. ≥ 3 lesson modules, each with `citationRefs`.
3. Approval → export → DOCX/PDF with footnotes.
4. `audit_entries` trail complete.

## Forbidden Scope

- Catechism content outside the approved corpus.
- Auto-approval.
