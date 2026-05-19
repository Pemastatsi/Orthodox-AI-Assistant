# Artifact Specification Contract

Status: Canonical
Date: 2026-05-19
ADR: 0013

This document defines the artifact type taxonomy, the common `Artifact` envelope, lifecycle states, caching rules, and the relationship between artifacts and the Q&A evidence pipeline. It is the primary source for Phase 2 artifact implementation. See `docs/schemas/artifact.schema.json` for the machine-readable schema.

## Artifact Type Taxonomy

Every artifact has an `artifactType` drawn from the following canonical set:

### Tier 2 — Visual Artifacts

| Type | Schema | Approval required | Artifact meter |
|---|---|---|---|
| `lineage_graph` | `lineage-graph.schema.json` | No | Yes (LLM-assisted assembly) |
| `council_timeline` | `council-timeline.schema.json` | No | No (deterministic assembly) |
| `citation_network` | `citation-network.schema.json` | No | No (chunk metadata only) |
| `dispute_map` | `dispute-map.schema.json` | No | Yes (LLM-assisted assembly) |
| `manuscript_witness_tree` | `manuscript-witness-tree.schema.json` | No | Yes (LLM-assisted assembly) |
| `mind_map` | `mind-map.schema.json` | No | No (derived from verified response) |

### Tier 3 — Generated Documents

| Type | Schema | Approval required | Artifact meter |
|---|---|---|---|
| `study_packet` | `study-packet.schema.json` | No | Yes |
| `sermon_outline` | `sermon-outline.schema.json` | No | Yes |
| `slide_deck` | `slide-deck.schema.json` | No | Yes |
| `catechism_lesson_plan` | `catechism-lesson-plan.schema.json` | **Yes** | Yes |
| `parish_bulletin_insert` | `parish-bulletin-insert.schema.json` | **Yes** | Yes |
| `bishop_briefing` | `bishop-briefing.schema.json` | **Yes** | Yes |
| `syllabus_bundle` | `syllabus-bundle.schema.json` | **Yes** | Yes |
| `feast_day_bundle` | `feast-day-bundle.schema.json` | **Yes** | Yes |
| `parish_faq_draft` | `parish-faq-draft.schema.json` | **Yes** | Yes |

### Tier 4 — Audio Overviews

| Type | Schema | Approval required | Artifact meter |
|---|---|---|---|
| `audio_overview` | `audio-overview.schema.json` | No | Audio meter (minutes) |

### Tier 5 — Orthodox-Unique Overlays

| Type | Schema | Approval required | Artifact meter |
|---|---|---|---|
| `bilingual_passage` | `bilingual-passage.schema.json` | No | No (morphology query only) |
| `liturgical_overlay` | `liturgical-context.schema.json` | No | No |
| `iconographic_card` | `iconographic-card.schema.json` | No | No |
| `monastery_map` | `geographic-overlay.schema.json` | No | No |
| `disputation_response` | (uses `verified-response.schema.json`) | No | Yes (LLM-assisted) |

## Artifact Envelope (`artifact.schema.json`)

Every artifact shares these top-level fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `artifactId` | string (ULID) | yes | Unique artifact identifier. |
| `tenantId` | string | yes | Owning tenant. |
| `requestingUserId` | string | yes | User who triggered generation. |
| `artifactType` | enum | yes | One of the canonical types above. |
| `status` | enum | yes | Lifecycle state (see ADR 0016). |
| `sourceRunId` | string (ULID) | yes | The `run_traces.run_id` of the Q&A pipeline run that produced the evidence packet. |
| `evidencePacketHash` | string | yes | SHA-256 of the serialized `EvidencePacket` used; locks the artifact to its evidence. |
| `citationRefs` | array of strings | yes | All `chunk_id` values cited in the artifact content. Non-empty required before `status` leaves `verifying`. |
| `artifactRouteId` | string | yes | The `model_routes.routeId` of the `ArtifactProvider` that rendered this artifact. |
| `locale` | string | yes | BCP 47 locale (e.g., `en`, `el`, `sl`). |
| `outputFormats` | array of strings | yes | Available export formats (e.g., `["pdf", "docx"]`). |
| `contentHash` | string | yes | SHA-256 of the rendered artifact content; used for cache lookup and tamper detection. |
| `provenance` | `ProvenanceReport` | yes | Output of `verify_citation_provenance`; includes `allClaimsVerified`, `verifiedClaimCount`, `unverifiedClaimCount`. |
| `approvalRecord` | `ApprovalRecord \| null` | yes | Non-null only for approval-required types after approval/rejection. |
| `failureReason` | string \| null | yes | Non-null when `status='failed'`. |
| `createdAt` | ISO 8601 | yes | |
| `updatedAt` | ISO 8601 | yes | |
| `exportedAt` | ISO 8601 \| null | yes | Timestamp of first successful export. |

Type-specific fields are defined in the per-type schemas listed above.

## Generation Request

Every artifact generation request (`artifact-request.schema.json`) contains:

| Field | Type | Required | Description |
|---|---|---|---|
| `tenantId` | string | yes | |
| `requestingUserId` | string | yes | |
| `artifactType` | enum | yes | |
| `sourceRunId` | string | yes | Must reference a completed, tenant-matching `run_traces` row with non-empty evidence packet. |
| `locale` | string | yes | |
| `outputFormats` | array | yes | At least one. |
| `generationOptions` | object | no | Type-specific options (e.g., slide count, language level, include discussion questions). |

The request does NOT accept an `evidencePacketId` directly; the pipeline fetches the evidence packet from the `run_traces` row to prevent tampering.

## Lifecycle

Full state machine defined in ADR 0016. Summary:

```
requested → evidence_check → generating → verifying → [pending_review?] → approved/exported
                                                                         ↓
                                                                       failed
```

Artifacts that do not require approval skip `pending_review` and transition directly from `verifying` to `ready` (a derived presentational status — not stored; `approved=null` + `status='exported'` is the query pattern).

## Caching

Artifacts are cached by a key that includes:

| Component | Source |
|---|---|
| `tenantId` | Principal |
| `artifactType` | Request |
| `evidencePacketHash` | Derived from source run |
| `artifactRouteId` | Active certified route |
| `locale` | Request |
| `generationOptionsHash` | SHA-256 of serialized `generationOptions` |
| `tenantBrandingVersion` | `tenants.config.brandingVersion` |

Cache TTL: 6 hours (longer than Q&A because artifact generation is more expensive). Cached artifacts do not increment the `generated_artifact_count` meter.

## Closed-Corpus Provenance Rules

1. `citationRefs` must be non-empty before the artifact leaves `verifying`.
2. `provenance.allClaimsVerified` must be `true` for the artifact to reach `approved` or `exported`.
3. An artifact with `provenance.allClaimsVerified=false` is stored as `status='failed'` with `failureReason='provenance_verification_failed'`.
4. The `evidencePacketHash` is stored immutably; re-generating the artifact against a new evidence packet creates a new artifact row.

## Forbidden

- Generating an artifact without a valid `sourceRunId` pointing to a completed run.
- Storing an artifact with an empty `citationRefs` array.
- Transitioning an artifact to `exported` when `provenance.allClaimsVerified=false`.
- Returning a cached artifact from a different tenant.
- Generating artifacts from candidate (unreviewed) graph edges or unapproved chunks.
