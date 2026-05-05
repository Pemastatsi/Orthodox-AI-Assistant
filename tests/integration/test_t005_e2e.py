"""End-to-end integration test stub for T-005 (cache, logs, billing).

Audit finding: A-14
Context citations:
  - docs/task_cards/phase1/T-005-cache-logs-billing.md (Acceptance Tests
    references this exact test path).
  - docs/contracts/cache-key.md
  - docs/schemas/run-trace.schema.json
  - docs/contracts/db-schema.md billing_usage and run_traces tables
  - docs/contracts/phase1-implementation-contract.md "Run-trace persistence is unconditional"

Skipped until T-001 (backend scaffold) and T-005 (cache/logs/billing) land.
"""
import pytest

pytest.importorskip("app", reason="awaits T-001 backend scaffold")


def test_cache_hit_persists_run_trace_with_runId():
    """A cache hit still mints a runId, persists a run_traces row, and
    increments served_answer_count without incrementing freshModelRunCount.

    Steps the implementation MUST satisfy when T-005 lands:
      1. Submit a query that misses cache; record runId_first.
      2. Submit the same query again so it hits cache; record runId_second.
      3. Assert runId_first != runId_second (each request gets its own runId).
      4. Assert both run_traces rows exist and the second has cacheHit=true,
         stages contain a 'cache_lookup' record with outcome='ok', and the
         final usage shows servedAnswerCount=1, freshModelRunCount=0.
      5. Assert the second response carries servedFromCache=true (per
         verified-response.schema.json).
      6. Assert billing_usage for the period reflects two served_answer_count
         increments and one fresh_model_run_count increment.
      7. Assert the cache key produced by the request matches the V1 vector
         in docs/contracts/cache-key.md when the inputs equal V1's inputs.
    """
    pytest.skip(
        "pending T-005 implementation: cache_hit_persists_run_trace_with_runId "
        "requires the cache service, run_traces persistence, and billing meters"
    )
