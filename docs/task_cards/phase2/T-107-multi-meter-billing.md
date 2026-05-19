# T-107: Multi-Meter Billing

## Goal

Extend the Phase 1 billing layer to support three Stripe meters per ADR 0015: `served_answer_count` (existing), `generated_artifact_count` (new), `audio_minutes_generated` (new). Deprecate `STRIPE_USAGE_METER` env var; introduce three replacement vars. Implement billing cap enforcement middleware for artifacts and audio. Extend the `billing_usage` schema and the Stripe reporting job.

## Required Reads

- [`docs/adr/0015-multi-meter-billing.md`](../../adr/0015-multi-meter-billing.md) — meter definitions, tier caps, overage policy.
- [`docs/adr/0005-cache-billing-privacy.md`](../../adr/0005-cache-billing-privacy.md) — existing billing architecture.
- [`docs/contracts/db-schema.md`](../../contracts/db-schema.md) — `billing_usage` table; extend with new columns.
- [`docs/schemas/billing-usage.schema.json`](../../schemas/billing-usage.schema.json) — add new meter fields.
- [`docs/api/openapi.yaml`](../../api/openapi.yaml) — extend `QuotaExceeded` response model with per-meter detail.
- [`docs/contracts/workflow-orchestration-contract.md`](../../contracts/workflow-orchestration-contract.md) — Stage 1 billing cap check.

## Files In Scope

**Backend:**
- `backend/app/domain/services/billing_service.py` — add `increment_artifact_count(tenant_id)`, `increment_audio_minutes(tenant_id, minutes)`, `check_artifact_cap(tenant_id)`, `check_audio_cap(tenant_id)`.
- `backend/app/domain/services/artifact_service.py` — call `check_artifact_cap` at Stage 1 (Intake); call `increment_artifact_count` at Stage 5 (auto-approve) or first export.
- `backend/app/tasks/stripe_reporting_job.py` — extend to report all three meters to Stripe; idempotent per `stripeUsageRecordId_artifacts` and `stripeUsageRecordId_audio`.
- `backend/app/alembic/versions/0005_billing_multi_meter.py` — add `generatedArtifactCount`, `audioMinutesGenerated`, `stripeUsageRecordId_artifacts`, `stripeUsageRecordId_audio` to `billing_usage`.
- `docs/schemas/billing-usage.schema.json` — add new columns.
- `docs/api/openapi.yaml` — extend `QuotaExceeded` with `meterName`, `currentCount`, `cap`.
- `.env.example` — add `STRIPE_METER_ANSWERS`, `STRIPE_METER_ARTIFACTS`, `STRIPE_METER_AUDIO`; deprecate `STRIPE_USAGE_METER` (keep with deprecation note).

## Acceptance Tests

1. `billing_usage` table migration adds `generatedArtifactCount` (default 0), `audioMinutesGenerated` (default 0), `stripeUsageRecordId_artifacts`, `stripeUsageRecordId_audio`.
2. Generating an artifact increments `generatedArtifactCount` by 1.
3. Generating a 3-minute audio overview increments `audioMinutesGenerated` by 3.
4. Cache hits do not increment either new meter.
5. `check_artifact_cap` with a Scholar tenant (cap=10) and `generatedArtifactCount=10` returns cap-exceeded; `POST /artifacts` returns 402 `quota_exceeded` with `meterName='generated_artifact_count'`.
6. Exhausting `generatedArtifactCount` cap does not block Q&A (`served_answer_count` unaffected).
7. `stripe_reporting_job` reports all three meters; Stripe is called at most once per `stripeUsageRecordId_*` (idempotency verified by mock).
8. Enterprise tenant with `cap=null` proceeds past any numeric threshold.
9. `STRIPE_USAGE_METER` env var prints a deprecation warning at startup but does not fail.

## Forbidden Scope

- Feature gating by tier (ADR 0015: all features on all paid tiers; only caps differ).
- Changing the `served_answer_count` increment logic.
- Email notifications for cap exhaustion (deferred to Phase 3).
- Stripe subscription management UI (out of Phase 2 scope).
