# ADR 0015: Multi-Meter Billing Model

Date: 2026-05-19
Status: Accepted

## Context

ADR 0005 established a single Stripe meter (`served_answer_count`) for Phase 1. This is appropriate for plain Q&A but breaks down in Phase 2 because different artifact types have dramatically different cost profiles:

- A plain Q&A response costs approximately $0.007 in LLM + embedding fees.
- A generated study packet (A5-class composition with evidence coverage check) costs approximately $0.15–0.40 depending on corpus size.
- A two-voice audio overview (8–12 minutes of TTS) costs approximately $0.12–$2.16 depending on the provider route.
- A graph or timeline render costs near zero in LLM fees (data assembly is deterministic once the evidence packet exists).

Charging the same per-unit rate for all of these would either make Q&A unaffordable or make audio/document generation unsustainably cheap. A multi-meter model — one meter per cost class — allows fair pricing without feature gating: all features are available on all paid tiers; what scales is the volume allowance per meter.

## Decision

Introduce three Stripe usage meters. All are billed via existing Stripe Metered Billing. All features are available on every paid tier. Tier caps scale volume per meter; overage is billed at a defined markup.

## Meter Definitions

### Meter 1: `served_answer_count` (existing, unchanged)
Increments for every user-visible Q&A response (fresh or cached, including cached answers, as established in ADR 0005). Tier 1 rich-text variants (markdown, Mermaid, mind map rendered inline) are delivered as part of the Q&A response and do not increment a separate meter.

### Meter 2: `generated_artifact_count` (new)
Increments for each successfully generated artifact of the following types:
- All Tier 3 generated documents (Study Packet, Sermon Outline, Slide Deck, Catechism Lesson Plan, Parish Bulletin, Bishop Briefing, Syllabus Bundle, Feast-Day Bundle, Parish FAQ).
- All Tier 2 visual artifacts that require a new LLM-assisted composition step (Lineage Graph, Dispute Map, Manuscript Witness Tree — because these require A5-class synthesis to assemble node/edge data from the evidence packet). Pure layout-and-render steps on pre-assembled graph data do not increment.
- Does not increment for: mind map / outline view (derived deterministically from the verified response), citation network (derived from chunk metadata, no LLM call), council timeline (assembled from structured corpus data).
- Cached artifact hits (same inputs, artifact within TTL) do not increment.

### Meter 3: `audio_minutes_generated` (new)
Increments by the number of minutes of TTS audio generated (rounded up to the nearest minute). Applies to Tier 4 audio overviews only. Cached audio playback does not increment.

## Tier Caps (EUR pricing, Greek theological market)

| Tier | Monthly price | `served_answer_count` | `generated_artifact_count` | `audio_minutes_generated` |
|---|---|---|---|---|
| Free / Demo | €0 | 30 | 2 | 5 |
| Scholar | €19/month | 400 | 10 | 30 |
| Parish / Community | €59/month | 2,000 | 50 | 120 |
| Seminary / Faculty | €179/month | 6,000 | 200 | 400 |
| Enterprise | €600–1,500 (custom) | Negotiated (high) | Negotiated (high) | Negotiated (high) |

Annual pricing: 2 months free (10 months paid). Recommended framing for academic and ecclesiastical buyers with annual budget cycles.

## Overage Policy

When a tenant exceeds a meter cap mid-cycle:
1. The tenant receives an in-app notification and email at 80% and 100% of cap.
2. At 100%, the tenant is offered: (a) upgrade to the next tier, (b) purchase an overage pack (see below), or (c) wait until the next billing cycle reset.
3. If no overage option is selected within 24 hours, the relevant capability is soft-blocked (Q&A continues; the capped feature type returns a `quota_exceeded` response).
4. Overage packs (per-unit, billed immediately): Q&A 100 answers = €2; Artifacts 10 = €3; Audio 30 minutes = €4.

## Billing Implementation

Extends `billing_usage` table with two new columns: `generatedArtifactCount` and `audioMinutesGenerated`. Both follow the same monthly rolling row pattern established in ADR 0005. Stripe webhook idempotency applies to all three meters via separate `stripeUsageRecordId_*` fields.

New Stripe meters are registered under names: `served_answer_count` (existing), `generated_artifact_count` (new), `audio_minutes_generated` (new).

The `STRIPE_USAGE_METER` env var (Phase 1) is superseded by three separate env vars:
```
STRIPE_METER_ANSWERS=served_answer_count
STRIPE_METER_ARTIFACTS=generated_artifact_count
STRIPE_METER_AUDIO=audio_minutes_generated
```

## Feature Parity Rule

Every paid tier has access to all five output tiers defined in ADR 0013. Volume caps are the only differentiator. There is no feature gating by tier. This rule is permanent; future pricing changes may adjust caps but may not reintroduce feature gating without a new ADR superseding this rule.

## Rules

1. Three Stripe meters; see definitions above. No additional meters without a new ADR.
2. Meter increments are idempotent via per-record `stripeUsageRecordId` fields, as established in ADR 0005.
3. All features are available on all paid tiers; only volume caps differ.
4. Overage is soft-blocked (capability unavailable, not account-blocked); Q&A is never blocked by artifact or audio overage.
5. Free / Demo tier capped at 30 Q&A / 2 artifacts / 5 audio minutes; no credit card required for free tier.
6. Enterprise tenants negotiate caps directly; no hard cap in code for Enterprise rows (cap field may be `null` = unlimited).
7. Cached artifacts and cached audio do not increment their respective meters.
8. Stripe meters are reported on the same daily-rollup schedule as `served_answer_count` (established in ADR 0005).
9. `STRIPE_USAGE_METER` env var is deprecated; the three new vars replace it. T-107 handles the migration.

## Tests

- Meter increment: generate an artifact; assert `billing_usage.generatedArtifactCount` increments by 1.
- Meter increment: generate a 3-minute audio overview; assert `billing_usage.audioMinutesGenerated` increments by 3.
- Cache non-increment: generate the same artifact twice; assert `generatedArtifactCount` increments only once.
- Cap enforcement: set `generatedArtifactCount` cap to 2; generate 3 artifacts; assert third returns `quota_exceeded`.
- Q&A isolation: exhaust `generatedArtifactCount` cap; assert Q&A (`served_answer_count`) is unaffected.
- Idempotency: report the same artifact generation twice with the same `stripeUsageRecordId`; assert Stripe is called only once.
- Enterprise unlimited: set tenant cap to `null`; assert generation proceeds past any numeric threshold.
