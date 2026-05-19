# Workflow Orchestration Contract

Status: Canonical
Date: 2026-05-19
ADR: 0013, 0016

This document defines the orchestration logic for artifact generation workflows: the state machine, evidence coverage check, A5-class composition step, A6-equivalent provenance verification, approval gates, retry policy, and audit trail. For the lifecycle state definitions, see ADR 0016.

## Pipeline Stages

Artifact generation runs through these stages in order:

```
1. INTAKE        — Validate request, check billing cap, validate sourceRunId.
2. EVIDENCE      — Load evidence packet; run coverage check.
3. GENERATE      — Invoke ArtifactProvider.generate() with evidence packet.
4. VERIFY        — Invoke ArtifactProvider.verify_citation_provenance().
5. ROUTE         — Determine approval requirement; route to PENDING_REVIEW or COMPLETE.
6. COMPLETE      — Store artifact with status=approved (non-approval types) or pending_review.
```

Failure at any stage transitions the artifact to `status='failed'` with a `failureReason` field.

## Stage 1: Intake

1. Validate `ArtifactRequest` against `artifact-request.schema.json`.
2. Check `billing_usage` for the requesting tenant: if `generatedArtifactCount >= cap`, return `quota_exceeded` and abort.
3. Resolve the `sourceRunId` to a `run_traces` row: must exist, must belong to the requesting tenant, must have `status='completed'`. Otherwise fail with `invalid_source_run`.
4. Check if an identical artifact is in cache (cache key defined in `artifact-spec-contract.md`); if so, return the cached artifact without creating a new row.
5. Insert an `artifacts` row with `status='requested'`; write `audit_entries` row `action='artifact_requested'`.

## Stage 2: Evidence Coverage Check

1. Load the `EvidencePacket` from the `run_traces` row.
2. Assert all admitted chunks have `approved=true` and belong to the requesting tenant. Any non-compliant chunk → fail with `evidence_integrity_violation`.
3. Run coverage checks per ADR 0016:
   - Minimum admitted chunks (5 standard, 10 high-stakes).
   - Minimum source diversity (≥ 3 distinct approved sources).
   - Citation health (no `broken` citations; ≤ 20% `degraded`).
   - Coverage threshold (≥ 0.85 high-stakes, ≥ 0.70 standard).
4. If any check fails → update `artifacts.status='failed'`, `failureReason='insufficient_evidence_coverage'`, write audit row; return `insufficient_evidence` to caller.
5. Update `artifacts.status='evidence_check'`; write audit row `action='evidence_check_passed'`.

## Stage 3: Artifact Generation

1. Resolve the active `ArtifactProvider` route from env var (`ACTIVE_ARTIFACT_ROUTE_*`).
2. Assert the route `certification_status='certified'`; fail with `uncertified_route` if not.
3. Call `provider.generate(request, evidence_packet, route_id)`.
4. Generation timeout: 120 seconds for visual artifacts and audio; 240 seconds for large generated documents (Syllabus Bundle, Bishop Briefing). On timeout → fail with `artifact_generation_timeout`.
5. Update `artifacts.status='generating'`; write audit row.

### A5-Class Composition (Tier 3 documents and LLM-assisted graphs)

For artifact types requiring LLM composition (all Tier 3 documents; `lineage_graph`, `dispute_map`, `manuscript_witness_tree`):

The composition prompt enforces:
- Closed-corpus rule: all claims must trace to admitted evidence chunks. Model is shown only the evidence packet content.
- Artifact-type structure: the model outputs a typed JSON structure matching the target schema.
- Citation requirement: every factual claim in the output JSON carries one or more `citationRefs`.
- Safety gate: the output is checked against A6 safety rules before returning (same `handling` taxonomy as Q&A).

One structured-output retry is permitted if the model returns malformed JSON (mirrors `provider-interface.md` retry policy). A second failure → `status='failed'`, `failureReason='composition_format_error'`.

## Stage 4: Provenance Verification

1. Call `provider.verify_citation_provenance(artifact, evidence_packet)`.
2. The method checks: every `citationRef` in the artifact resolves to an admitted chunk; every cited claim has quote overlap ≥ 70% (applying `docs/contracts/quote-overlap-algorithm.md` logic); no unapproved chunks are referenced.
3. If `provenanceReport.allClaimsVerified=false` → `status='failed'`, `failureReason='provenance_verification_failed'`; write audit row with `provenanceReport` in `details`.
4. Update `artifacts.status='verifying'`; on success update to `status='ready'` (pre-routing); write audit row `action='provenance_verified'`.

## Stage 5: Approval Routing

If the artifact type is in the approval-required list (ADR 0016):
- Update `artifacts.status='pending_review'`.
- Write audit row `action='artifact_pending_review'`.
- Trigger in-app notification to admin/owner users of the tenant.

If not approval-required:
- Update `artifacts.status='approved'` (implicit auto-approval for non-gated types).
- Increment `generated_artifact_count` billing meter.
- Write audit row `action='artifact_auto_approved'`.

## Stage 6: Export

Export is triggered by `POST /artifacts/{artifactId}/export`. Not part of the generation pipeline but gated on it:

1. Assert `artifact.status='approved'` or `artifact.status='exported'`.
2. For approval-required types: assert `artifact.approvalRecord.approvedBy` is non-null.
3. Call `ExportProvider.export(artifact, format, branding)`.
4. Store the exported file in tenant-scoped object storage; return a signed URL.
5. Update `artifacts.status='exported'`; write audit row `action='artifact_exported'` with `details.format` and `details.fileSizeBytes`.
6. For first export: increment `generated_artifact_count` billing meter if not already incremented (auto-approved types already incremented at Stage 5; approval-gated types increment on first export).

## Retry Policy

| Failure type | Retry | Notes |
|---|---|---|
| `composition_format_error` (malformed JSON) | 1 automatic retry | Mirrors LLM structured-output retry in `provider-interface.md` |
| `artifact_generation_timeout` | No automatic retry | Caller may re-submit |
| `provider_unavailable` | No automatic retry | Mirrors ADR 0004 outage policy |
| `rate_limited` | Backoff per `Retry-After` header | Max 2 retries; report to caller if both fail |
| `insufficient_evidence_coverage` | No retry | Corpus expansion required |
| `provenance_verification_failed` | No retry | Corpus correction required |

## Audit Trail

Every stage transition writes an `audit_entries` row:

| Action | `resource_type` | `details` content |
|---|---|---|
| `artifact_requested` | `artifact` | `artifactType`, `sourceRunId` |
| `evidence_check_passed` | `artifact` | `admittedChunkCount`, `sourceCount`, `coverageScore` |
| `evidence_check_failed` | `artifact` | `failureReason`, `coverageScore` |
| `artifact_auto_approved` | `artifact` | `artifactType`, `provenance.allClaimsVerified` |
| `artifact_pending_review` | `artifact` | `artifactType`, `provenance.coverageScore` |
| `artifact_approved` | `artifact` | `approverUserId`, `reviewerComment`, `provenance.coverageScore` |
| `artifact_rejected` | `artifact` | `approverUserId`, `reviewerComment` |
| `provenance_verified` | `artifact` | `allClaimsVerified`, `verifiedClaimCount` |
| `provenance_verification_failed` | `artifact` | `unverifiedClaimCount`, `failedCitationRefs` |
| `artifact_exported` | `artifact` | `format`, `fileSizeBytes`, `signedUrlExpiry` |
| `artifact_expired` | `artifact` | `failureReason='approval_timeout'` |

## Approval Expiry Worker

A background worker (arq task, runs hourly) queries for artifacts with `status='pending_review'` and `createdAt < now() - 30 days`. For each: update `status='failed'`, `failureReason='approval_timeout'`; write `audit_entries` row. The requesting user receives an in-app notification.

## Forbidden

- Starting Stage 3 (generation) before Stage 2 (evidence check) passes.
- Incrementing the billing meter before provenance verification passes.
- Transitioning an artifact to `approved` or `exported` with `provenance.allClaimsVerified=false`.
- Running the generation pipeline synchronously in the HTTP request handler; all stages run as arq tasks.
- Writing an `audit_entries` row after (not before) the state change it describes; audit rows must be written atomically with the state transition in the same database transaction.
