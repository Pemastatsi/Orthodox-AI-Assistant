# Observability

Status: Canonical
Date: 2026-05-02

This document defines the structured-log shape, trace propagation, redaction rules, and metrics inventory. Implemented in `app/core/logging.py`.

## Principles

- All log output is **structured JSON**, one event per line. No free-form strings.
- Every request has a `runId` (ULID). It is returned in the `X-Run-Id` response header and stamped on every downstream log line for that request.
- Sensitive fields are redacted by the logger, not by callers. Callers may pass raw text; the redactor strips it before serialization.
- Logs go to stdout. Railway aggregates. Production retention and analytics tooling do not see raw sensitive text (ADR 0005).

## Log Line Schema

Every line conforms to the following schema. Optional fields may be omitted; required fields are always present.

```json
{
  "ts": "2026-05-01T13:42:01.123Z",
  "level": "info",
  "event": "query.completed",
  "traceId": "01HZX7ABC...",
  "tenantId": "tn_orthodoxethos",
  "userId": "u_01HZ...",
  "runId": "01HZX7ABC...",
  "service": "backend",
  "version": "0.1.0",
  "stage": "a5_composer",
  "durationMs": 1452,
  "outcome": "ok",
  "modelRouteId": "a5_compose_anthropic@2026-05-01.1",
  "code": null,
  "details": {}
}
```

### Required fields

| Field | Type | Notes |
|---|---|---|
| `ts` | string (ISO 8601 with ms, UTC) | `YYYY-MM-DDTHH:MM:SS.sssZ`. |
| `level` | enum: `debug`, `info`, `warn`, `error` | `error` requires `code`. |
| `event` | string `<domain>.<action>` | e.g., `query.started`, `ingest.failed`, `cache.hit`. |
| `service` | enum: `backend`, `worker`, `web` | Source process. |
| `version` | string | Semver of the running build. |

### Conditionally required

| Field | Required when |
|---|---|
| `traceId` | Always for request-scoped events. Equal to `runId` for query pipeline events. |
| `tenantId` | Always once auth resolves. |
| `userId` | Always once auth resolves. |
| `runId` | Always for `query.*` and `pipeline.*` events. |
| `stage` | When the event is inside the A1–A6 pipeline. Enum: `a1_a2_query_analyzer`, `a3_retrieval`, `a4_evidence_packager`, `a5_composer`, `a6_verifier`, `cache_lookup`, `cache_store`. |
| `durationMs` | For any `*.completed` event. |
| `outcome` | For any `*.completed` event. Enum: `ok`, `fallback`, `error`, `skipped`. |
| `code` | For `level: error`. Must match a code in `docs/contracts/error-taxonomy.md`. |

### Optional

`details` may carry additional structured context. **Must not** include raw sensitive query text, raw answer text, secrets, or full chunk text. Permitted: counts, sizes, hashes, IDs, durations.

## Trace ID Propagation

- Incoming requests with a valid `X-Run-Id` header reuse it; otherwise the middleware generates a new ULID.
- Every outbound provider/Qdrant/Redis/Stripe/Clerk call carries the trace ID in adapter logs.
- Worker tasks read the trace ID from the queued job payload; they never invent a new one if continuing existing work.

## Redaction Rules

The logger applies a redactor before serialization. Inputs that pass through `details` are scanned for the following keys (case-insensitive) and the value replaced with `"[redacted]"`:

```
password, secret, token, api_key, authorization, cookie, set-cookie,
private_key, signing_key, hmac, otp, mfa, ssn, dob, credit_card, card_number,
cvv, pan, query_text, raw_query, raw_answer, chunk_text, source_text
```

`raw_query` and `query_text` are also redacted because raw sensitive query text never enters logs (ADR 0005). The orchestrator passes a hashed `queryNormalizedHash` instead.

The `stages[].notes` field on a `RunTrace` is governed by the same prohibition: it MUST NOT contain raw query text, raw answer text, raw chunk text, secrets, or any value listed in the redaction inventory. Agents writing to `notes` should restrict themselves to small structured tokens (e.g., `'rule_matched: pastoral_divorce_001'`) and rely on `details` for richer audit-relevant data already covered by the redaction filter.

## Event Catalog

Authoritative list. Engineers add to this list when introducing a new event. Every served request emits exactly one `query.completed` event and persists exactly one `run_traces` row, regardless of whether the request reached A5 or short-circuited via hard-safety.

### query.*
- `query.received` — request landed; auth not yet resolved.
- `query.classified` — A1/A2 finished; carries `sensitivityPrimary`, `handling`, `preliminaryConfidenceTier`.
- `query.retrieved` — A3 finished; carries `candidateCount`.
- `query.evidence_packed` — A4 finished; carries `admittedCount`, `suppressedCount`, `confidenceTier`.
- `query.composed` — A5 finished; carries `modelRouteId`, `promptTokens`, `completionTokens`.
- `query.verified` — A6 finished; carries `verifierPassed`.
- `query.completed` — request done; carries final `handling`, `confidenceTier`, `cacheHit`, `durationMs`.
- `query.failed` — request errored; carries `code`.

### cache.*
- `cache.hit`, `cache.miss`, `cache.store`, `cache.invalidated`.

### ingest.*
- `ingest.received`, `ingest.extracted`, `ingest.chunked`, `ingest.embedded`, `ingest.queued_for_review`, `ingest.failed`.

### admin.*
- `admin.chunk_approved`, `admin.chunk_rejected`, `admin.raw_sensitive_view`, `admin.tenant_config_updated`.

### auth.*
- `auth.token_invalid`, `auth.org_missing`, `auth.tenant_resolved`.

### provider.*
- `provider.call_started`, `provider.call_completed`, `provider.refused`, `provider.invalid_response`.

### webhook.*
- `webhook.received`, `webhook.signature_failed`, `webhook.replay`, `webhook.processed`.

### worker.*
- `worker.retention.started` — sensitive-log retention worker run begins; carries `target_table='raw_sensitive_logs'`.
- `worker.retention.completed` — run finished; carries `deleted_count`, `durationMs`, `next_run_at`. Emitted on every run so Phase-1→2 exit criterion #8 ("retention cleanup has executed at least once successfully") is observable.
- `worker.retention.failed` — run errored; carries `code` from the error taxonomy.
- `worker.embedding.completed` — ingestion or backfill embedding batch finished; carries `chunks_processed`, `embedding_model`.

## Metrics

Recorded as counter increments in the structured log (`event` ending in a state). Prometheus exporter is **deferred to Phase 2**; for Phase 1, exit-criterion accounting is computed by `scripts/exit_criteria_dashboard.py` (a small Python script that reads `run_traces` and prints each criterion's current value). The metric names listed below are the contract for the future exporter and the column names emitted by the dashboard script. Phase 1 minimum:

| Metric | Type | Labels | Source event |
|---|---|---|---|
| `served_answer_count` | counter | `tenantId`, `cacheHit` | `query.completed` |
| `fresh_model_run_count` | counter | `tenantId`, `modelRouteId` | `query.composed` (cache miss only) |
| `a6_pass_rate` | counter pair | `tenantId` | `query.verified` (passed/failed) |
| `cache_hit_rate` | counter pair | `tenantId` | `cache.hit` / `cache.miss` |
| `red_tier_rate` | counter | `tenantId`, `confidenceTier` | `query.completed` |
| `query_latency_ms` | histogram | `tenantId`, `cacheHit` | `query.completed.durationMs` |
| `provider_failure_count` | counter | `provider`, `code` | `provider.call_completed` (outcome=error) |
| `safety_block_count` | counter | `tenantId`, `riskFlags` | `query.completed` (handling=block_with_redirect) |

## Sample Log Line — Validates

The sample at the top of this file validates against the schema described here. Tests in `tests/unit/test_logging.py` (when scaffold lands) load this exact line and assert all required fields are present and typed correctly.
