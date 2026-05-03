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
9. Raw sensitive logs are never sent to analytics tools.

## Tests

- Cache invalidates when any key component changes.
- Cache hits count as served answers but not fresh model runs.
- Sensitive log views create audit rows.
- Retention cleanup removes expired raw sensitive text.
