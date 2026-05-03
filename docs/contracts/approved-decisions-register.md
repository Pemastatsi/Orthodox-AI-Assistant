# Approved Decisions Register

Status: Canonical
Date: 2026-04-26

This register preserves approved decisions extracted from archived planning drafts. Use it when a task needs a specific decision not covered in `AGENTS.md`, ADRs, schemas, or task cards.

## Founder Decisions

| Area | Decision |
|---|---|
| Phase 1 tenancy | Tenant-aware admin UX and tenant-isolated data paths from day 1. |
| Theological review | Founder reviews internal beta; external Orthodox reviewer required before public or paid launch. |
| Beta scope | Phase 1 is internal/private beta. |
| Sensitive logs | Redacted by default; raw text encrypted, admin-only, audited, 30-day private-beta retention. |
| Model strategy | Provider abstraction from day 1; only certified routes serve users. |
| EU data region | Keep `data_region`; EU-only hosting is not a Phase 1 blocker. |
| Cached billing | Cached answers count as served answers; fresh model runs tracked separately. |
| Citation detail | Target exact quote span plus page/timestamp, source/work, father, hashes, approval, and origin. |
| Study packets | Not in MVP; schemas/hooks only until Q&A is stable. |
| Tenant prompts | Safe config fields only in MVP; no free-form base prompt editing. |

## Clarification Decisions

| Item | Decision |
|---|---|
| A. Sensitivity taxonomy | Use `sensitivityPrimary` plus `riskFlags`; hard triggers bypass two-stage gate. |
| B. Sensitivity keywords | Keep tunable keyword YAML with hard safety triggers separated from medical terms. |
| C. Answer mode selection | `scholarly_dispute` is available to all users for explicit dispute/comparison queries. |
| D. Tier thresholds | Confidence thresholds are tenant-tunable safe config, not hardcoded forever. |
| E. Phase 1 A2/A4 | Use stable interfaces; Phase 1 QueryAnalyzer and deterministic A4 enforce tenant and visibility gates. |
| F. Reframing UX | Sensitive reframing is transparent; no "view as originally asked" pseudo-control. |
| G. A6 verification | Deterministic checks first; 70% quote-overlap default; optional low-cost consistency judge only. |
| H. Clerk mapping | Clerk org maps to internal tenant; tenant is resolved from auth context, not request body trust. |
| I. Calendar style | Use `calendar_profile` with independent fixed-feast and Paschalion settings. |
| J. Call 5 schema | Source hash is SHA-256 of raw bytes before processing; extraction method includes version string. |
| K. Permissions | Content managers see sensitive/flagged content redacted; audit raw sensitive views. |
| L. Safety queries | Queries 11-20 are canonical fixtures; changes require founder sign-off and safety-suite run. |
| M. Streaming | Draft-answer streaming rejected for MVP; stream progress only, final answer after A6. |
| N. Session cache | Full cache key includes prompt, corpus, role, config, calendar, model route, schema, and session where applicable. |
| O. Make.com HMAC | Webhooks require timestamp window, nonce/replay protection, idempotency key, and secret rotation. |
| P. PAG-RAG | Phase 2+ lineage graph; only approved edges enter evidence and answer claims. |

## Optimization Decisions

| Item | Decision |
|---|---|
| 1. Multi-tenant day 1 | Accepted; every tenant surface and data path is tenant-aware. |
| 2. Confidence/handling split | Accepted; confidence, sensitivity, risk flags, and handling are separate. |
| 3. Attestation day 1 | Store attestation/source integrity fields early to avoid re-ingestion. |
| 4. Flagged embeddings | Store flagged query embeddings; model upgrades require dimension-aware backfill. |
| 5. Father/work grouping | Cross-reference panels group by father and work. |
| 6. Prompt versioning | Admin-only, post-MVP free-form versions require preview, rollback, and safety gate. |
| 7. Starter corpus | Treat starter corpus as virtual tenant; enforce uniqueness at DB layer. |
| 8. Regex post-filter | Pastoral forbidden phrases live in safety config; changes require safety-suite run. |
| 9. Retrieval explainability | Evidence packets include retrieval explanation metadata. |
| 10. Rate limiting | Per-tenant rate limiting is accepted. |
| 11. Cost telemetry | Per-tenant cost dashboard is accepted. |
| 12. Batch progress | Batch ingestion tracks progress and failures. |
| 13. Citation format | Use canonical citation formatter shared by answer modes and exports. |
| 14. API versioning | Version public response schemas. |
| 15. Query clustering | Auto-cluster flagged queries after core query path is stable. |
| 16. Answer schemas | Answer mode outputs use typed schemas. |
| 17. Embedding upgrades | Document and test embedding model upgrade procedure. |
| 18. CI safety gate | Theological safety regression runs in CI. |
| 19. Shadow A/B | Rejected until post-production traffic and evaluation infrastructure exist. |
| 20. Scoped approvals | Phase 3+ downward-only delegation; admins cannot grant beyond their scope. |
