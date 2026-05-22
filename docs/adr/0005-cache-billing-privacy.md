# ADR 0005: Cache, Billing, and Sensitive Log Privacy

Date: 2026-04-26
Status: Accepted

## Context

Caching reduces cost, but user-visible answers still create product value. Sensitive theological, pastoral, and medical queries may contain private information.

## Decision

Count every user-visible answer as served usage. Track fresh model runs separately for cost. Store sensitive logs redacted by default, with tightly controlled raw retention during private beta.

## Rules

1. MVP Stripe meter is `served_answer_count`.
2. Cache hits increment served-answer usage.
3. Fresh model executions increment `fresh_model_run_count`.
4. Response cache TTL defaults to 1 hour.
5. Cache keys include tenant, normalized query, role, session hash when applicable, corpus version, prompt version, model routes, schema version, and config/calendar version.
6. Follow-up questions include session context in the cache key.
7. Sensitive logs store `query_text_redacted` by default.
8. Raw sensitive text may be encrypted, admin-only, audited, and retained for 30 days during private beta.

   **Encryption strategy (Phase 1):** Application-level envelope encryption using AES-256-GCM. The data key is a base64-encoded 32-byte secret stored in Railway secret manager as `SENSITIVE_LOG_DATA_KEY_BASE64` and read at process start; `key_version` (column on `raw_sensitive_logs`) records which key version produced each ciphertext. Rotation is operator-driven: deploy with a new secret, set `key_version` to the new label on writes, decrypt-on-read tries each known key by version. Phase 2 will migrate to a managed KMS (AWS KMS, GCP KMS, or HashiCorp Vault) — tracked as a Phase 2 ticket. Rationale: Railway has no built-in KMS; bringing in an external KMS during private beta adds operational complexity disproportionate to risk for a small admin-only audience.

9. Raw sensitive logs are never sent to analytics tools.

## Reranker / Managed-Inference Egress (REC-016, REC-018 amendment)

Phase 1 may route reranker inference to two non-local destinations: **Cohere Rerank v3.5** (managed API, REC-016) and **Modal-hosted bge-reranker-v2-m3** (per-second-billed GPU, REC-018). Both destinations receive the user's query plus ~20 candidate chunk texts per reranked call. The data classification per CLAUDE.md §1 applies:

- **Chunk text leaving to a reranker is Confidential, not Sensitive.** Chunks are tenant-approved Patristic content; they do not contain user PII, secrets, or payment data. Confidential egress is allowed under CLAUDE.md §1 without per-call founder approval, but each managed reranker is subject to the standard third-party vendor review at certification time (route promotion through ADR-0004).
- **Per-tenant opt-in.** Routing to a managed reranker is gated by `tenant.config.rerankerRoutePreference` (ADR-0012 §"Greek-stress fallback path"). The default value is `'bge_local'`; tenants must explicitly select a managed route, making the egress choice visible per tenant.
- **No logging of chunk text on the egress side.** The reranker adapter MUST NOT log the chunk text or the query in structlog or OTel attributes (covered by the existing redaction rules in `observability.md`). The route invocation row records only the `route_id`, chunk count, and latency.
- **Modal isolation.** The Modal-hosted reranker runs in a Modal-managed container that exposes only the inference endpoint; Modal does not retain inputs after the request. Modal's data-processing terms are referenced in the third-party-vendor review at certification time.

This egress amendment is encoded in `tests/integration/test_reranker_egress.py`: the adapter under test is run against a synthetic chunk containing a sentinel string; the test asserts the sentinel does NOT appear in any structlog/OTel artifact for that request.

## Tests

- Cache invalidates when any key component changes.
- Cache hits count as served answers but not fresh model runs.
- Sensitive log views create audit rows.
- Retention cleanup removes expired raw sensitive text.
