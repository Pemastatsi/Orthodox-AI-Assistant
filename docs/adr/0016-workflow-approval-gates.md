# ADR 0016: Workflow Approval Gates

Date: 2026-05-19
Status: Accepted

## Context

Tier 3 generated documents (Bishop Briefing, Syllabus Bundle, Catechism Lesson Plan, Parish FAQ Draft, Feast-Day Bundle) carry institutional weight. A Bishop Briefing issued under a diocese's name, or a Catechism Guide distributed to adult inquirers, can cause pastoral harm if it contains citations that — while technically from the approved corpus — have been composed in a misleading or contextually inappropriate way. The institutional buyers in the target market (seminary departments, Orthodox Ethos, diocesan offices) will not adopt generated documents without a human sign-off step.

This is the key differentiator from general-purpose document-generation tools: we provide an approval workflow that gives institutional authorities control over what gets exported and distributed under their name.

## Decision

High-stakes generated artifacts follow a mandatory multi-state approval workflow before export is permitted. Low-stakes artifacts (inline graphs, timelines, mind maps, audio overviews for personal use) do not require approval and transition directly to `ready` on successful generation and verification.

## Workflow Lifecycle

All artifacts have `status` drawn from the following states:

```
requested → evidence_check → generating → verifying → pending_review → approved → exported
                                                                       ↓
                                                                     rejected
                                          ↓ (on any failure)
                                        failed
```

### State Definitions

| State | Description |
|---|---|
| `requested` | Artifact generation request received; inputs validated; billing cap checked. |
| `evidence_check` | Evidence coverage check running: minimum admitted chunks, minimum source diversity, citation health thresholds. |
| `generating` | A5-class composition running; artifact content being assembled from evidence packet. |
| `verifying` | A6-equivalent provenance verification running over artifact content. |
| `pending_review` | Applies only to approval-required artifact types. Artifact is complete and verified; waiting for admin/owner sign-off. |
| `approved` | Admin or owner has approved the artifact. Available for export. |
| `exported` | Artifact has been exported at least once. Remains exportable. |
| `rejected` | Admin or owner rejected the artifact. Exportable only to the approving admin for reference. Not user-visible. |
| `failed` | Generation, verification, or evidence check failed. User-visible error with reason. |

### Approval-Required Artifact Types

The following artifact types require `status='approved'` before export is available to the requesting user:

- `bishop_briefing`
- `syllabus_bundle`
- `catechism_lesson_plan`
- `parish_faq_draft`
- `feast_day_bundle`
- `parish_bulletin_insert`

The following artifact types do NOT require approval and may be exported once `status='ready'` (skipping `pending_review`):

- All Tier 2 visual artifacts (graphs, timelines, maps).
- `study_packet`, `sermon_outline`, `slide_deck` — self-service; the requesting user takes responsibility.
- Audio overviews — personal use only; not distributed.
- Tier 1 rich-text and Tier 5 multimedia overlays — ephemeral; not exported as standalone documents.

## Evidence Coverage Check

Before generation begins, the `evidence_check` step enforces:

1. **Minimum admitted chunks:** ≥ 5 chunks admitted for simple document types; ≥ 10 for high-stakes types.
2. **Minimum source diversity:** chunks must span ≥ 3 distinct approved sources.
3. **Citation health:** no admitted chunk may have `citationHealth='broken'`; ≤ 20% of admitted chunks may have `citationHealth='degraded'`.
4. **Coverage threshold:** the coverage score (proportion of artifact sections with at least one supporting citation) must be ≥ 0.85 for high-stakes types, ≥ 0.70 for standard types.

If the evidence check fails, the artifact moves to `failed` with `failureReason='insufficient_evidence_coverage'` and the user receives guidance on expanding the tenant corpus.

## Roles and Permissions

| Action | Required Role |
|---|---|
| Request artifact generation | `member` or above |
| View artifact preview (pending_review) | `admin` or `owner` |
| Approve artifact | `admin` or `owner` |
| Reject artifact | `admin` or `owner` |
| Export approved artifact | `member` (the original requester) or `admin` or `owner` |
| Export rejected artifact | `admin` or `owner` only |
| View audit trail for artifact | `admin` or `owner` |

The approval action writes an `audit_entries` row with `action='artifact_approved'`, `resource_type='artifact'`, `resource_id=artifactId`, `actorRole`, and `actorUserId`.

## Audit Trail

Every state transition writes an `audit_entries` row. The `details` JSON field carries:
- For `evidence_check` transitions: coverage score, admitted chunk count, source count.
- For `approved` / `rejected` transitions: reviewer comments (free text, max 1,000 chars), evidence coverage score, `citationRefs` hash.
- For `exported` transitions: export format, file size, timestamp.

## Reviewer Interface

The admin `<WorkflowApprovalQueue>` component (see `docs/contracts/frontend-components.md`) surfaces:
- Artifact type, requesting user, timestamp.
- Evidence coverage score and source list.
- Full artifact preview with inline citation markers.
- Approve / Reject / Request Changes buttons (Request Changes leaves artifact in `pending_review` with a comment, allowing the tenant to re-generate against an expanded corpus).

## Rules

1. Approval-required artifact types MUST NOT be exportable before `status='approved'`; the API returns `artifact_pending_approval` if export is attempted on a `pending_review` artifact.
2. The evidence coverage check MUST run before generation begins; generation must not start if the check fails.
3. Every state transition MUST write an `audit_entries` row before the state change is committed.
4. Rejected artifacts are soft-deleted from the member view; the admin retains access for reference and re-use of citations.
5. Approval is per artifact instance, not per artifact type; changing the evidence packet or tenant corpus requires a new generation and a new approval cycle.
6. The approval role (`admin` or `owner`) is scoped to the tenant; cross-tenant approval is impossible.
7. Approval notification to the requesting user (in-app only in Phase 2; email notifications deferred to Phase 3).
8. Workflow timeout: artifacts stuck in `pending_review` for > 30 days are auto-expired to `failed` with `failureReason='approval_timeout'`.

## Tests

- State machine: assert all valid state transitions are permitted; assert all invalid transitions are rejected.
- Approval gate: attempt to export a `pending_review` artifact; assert `artifact_pending_approval` error.
- Evidence coverage check: submit a generation request with < 5 admitted chunks; assert `failed` with `insufficient_evidence_coverage`.
- Audit trail: approve an artifact; assert `audit_entries` row with correct fields written atomically with the state change.
- Role enforcement: member attempts to approve; assert `forbidden_role`.
- Tenant scope: admin from tenant B attempts to approve artifact from tenant A; assert 404 (not 403, to avoid resource existence disclosure).
- Timeout: set an artifact to `pending_review` with `createdAt` = 31 days ago; run the expiry worker; assert `status='failed'`, `failureReason='approval_timeout'`.
