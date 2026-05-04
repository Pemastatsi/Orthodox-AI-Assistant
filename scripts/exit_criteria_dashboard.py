"""Phase 1 → 2 exit-criteria dashboard.

Audit finding: F-22
Context citations:
  - docs/contracts/phase1-implementation-contract.md — "Phase 1 → Phase 2 Exit Criteria" (9 criteria)
  - docs/contracts/observability.md — metric names + run_traces schema
  - docs/contracts/db-schema.md — run_traces, audit_entries, chunks, sources,
      billing_usage, raw_sensitive_logs table DDL
  - AGENTS.md "Cache, Billing, Logs": served_answer_count, fresh_model_run_count

Dependency chain on Wave 1 schemas:
  - T-001: backend scaffold, run_traces table, audit_entries table
  - T-002: chunks, sources tables
  - T-005: billing_usage, raw_sensitive_logs, retention worker
  - T-006: audit_entries rows for founder_phase2_signoff

Usage:
  python scripts/exit_criteria_dashboard.py --db-url postgresql://user:pass@host/db

Each criterion function returns:
  (criterion_name: str, current_value: str, threshold: str, passing: bool)

Implementation bodies raise NotImplementedError until Phase 1 → 2 dashboard
work lands. The SQL that WOULD be run is included as a comment.
"""
from __future__ import annotations

import argparse
import sys


# ---------------------------------------------------------------------------
# Criterion stub functions (one per Phase 1 → 2 exit criterion)
# ---------------------------------------------------------------------------


def criterion_1_safety_suite_stability(db_url: str) -> tuple[str, str, str, bool]:
    """Exit criterion #1: test_20_queries.py passes in CI for 14 consecutive
    calendar days with no override.

    This criterion is measured via CI run history, not a DB query. The dashboard
    will read from an audit_entries row written by the CI gate job.

    SQL (when implemented):
        SELECT COUNT(DISTINCT DATE(created_at)) AS passing_days
        FROM audit_entries
        WHERE action = 'ci_safety_suite_passed'
          AND created_at >= NOW() - INTERVAL '14 days'
          AND details->>'override' IS NULL
        ORDER BY created_at DESC;
        -- Pass when passing_days = 14 (no gap allowed).
    """
    raise NotImplementedError("pending Phase 1 → 2 dashboard work: criterion_1_safety_suite_stability")


def criterion_2_internal_traffic_threshold(db_url: str) -> tuple[str, str, str, bool]:
    """Exit criterion #2: at least 50 distinct internal queries served end-to-end.

    Cache hits and misses both count. Includes hard-safety blocks (they persist
    a run_traces row per phase1-implementation-contract.md run-trace guarantee).

    SQL (when implemented):
        SELECT COUNT(DISTINCT run_id) AS served_count
        FROM run_traces
        WHERE finished_at IS NOT NULL
          AND provider_error_code IS NULL;
        -- Pass when served_count >= 50.
    """
    raise NotImplementedError("pending Phase 1 → 2 dashboard work: criterion_2_internal_traffic_threshold")


def criterion_3_red_rate_ceiling(db_url: str) -> tuple[str, str, str, bool]:
    """Exit criterion #3: 7-day rolling RED rate <= 30% of served answers.

    Formula (from phase1-implementation-contract.md "RED Rate Ceiling — Definition"):
        red_rate = count(finalConfidenceTier='RED' AND finalHandling != 'block_with_redirect')
                 / count(finalHandling != 'block_with_redirect')
        over last 7 calendar days.
    Hard-safety blocks excluded from both numerator and denominator.
    Cache hits ARE included.

    SQL (when implemented):
        WITH base AS (
            SELECT
                SUM(CASE WHEN final_confidence_tier = 'RED' THEN 1 ELSE 0 END) AS red_count,
                COUNT(*) AS total_count
            FROM run_traces
            WHERE finished_at IS NOT NULL
              AND provider_error_code IS NULL
              AND final_handling != 'block_with_redirect'
              AND finished_at >= NOW() - INTERVAL '7 days'
        )
        SELECT
            red_count,
            total_count,
            ROUND(red_count::numeric / NULLIF(total_count, 0), 4) AS red_rate
        FROM base;
        -- Pass when red_rate <= 0.30 (and total_count > 0).
    """
    raise NotImplementedError("pending Phase 1 → 2 dashboard work: criterion_3_red_rate_ceiling")


def criterion_4_latency_target(db_url: str) -> tuple[str, str, str, bool]:
    """Exit criterion #4: p95 query latency < 8000 ms at /api/v1/query boundary,
    last 7 days, cache misses included, ingestion-only requests excluded.

    SQL (when implemented):
        SELECT
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_latency_ms
        FROM run_traces
        WHERE finished_at IS NOT NULL
          AND provider_error_code IS NULL
          AND is_ingestion_only = FALSE
          AND finished_at >= NOW() - INTERVAL '7 days';
        -- Pass when p95_latency_ms < 8000.
    """
    raise NotImplementedError("pending Phase 1 → 2 dashboard work: criterion_4_latency_target")


def criterion_5_tenant_isolation_invariant(db_url: str) -> tuple[str, str, str, bool]:
    """Exit criterion #5: zero cross-tenant evidence admissions, cache-hit leaks,
    log-read leaks, or admin-view leaks across the entire deployment history.

    Measured via integration tests (tests/integration/test_tenant_isolation.py).
    Dashboard reports last CI result for that test module as an audit_entries row.

    SQL (when implemented):
        SELECT details->>'result' AS last_result,
               details->>'run_at' AS run_at
        FROM audit_entries
        WHERE action = 'ci_tenant_isolation_passed'
        ORDER BY created_at DESC
        LIMIT 1;
        -- Pass when last_result = 'pass'.
    """
    raise NotImplementedError("pending Phase 1 → 2 dashboard work: criterion_5_tenant_isolation_invariant")


def criterion_6_founder_review_pass(db_url: str) -> tuple[str, str, str, bool]:
    """Exit criterion #6: at least one audit_entries row with
    action='founder_phase2_signoff' for the tenant, with >= 20 reviewedRunIds
    and >= 3 distinct sensitivityCategoriesCovered, actor is owner.

    SQL (when implemented):
        SELECT
            ae.audit_id,
            ae.actor_user_id,
            ae.created_at,
            jsonb_array_length(ae.details->'reviewedRunIds') AS reviewed_count,
            jsonb_array_length(ae.details->'sensitivityCategoriesCovered') AS sensitivity_count
        FROM audit_entries ae
        JOIN users u ON u.user_id = ae.actor_user_id
        WHERE ae.action = 'founder_phase2_signoff'
          AND ae.resource_type = 'tenant'
          AND u.role = 'owner'
          AND jsonb_array_length(ae.details->'reviewedRunIds') >= 20
          AND jsonb_array_length(ae.details->'sensitivityCategoriesCovered') >= 3
        ORDER BY ae.created_at DESC
        LIMIT 1;
        -- Pass when at least one row returned.
    """
    raise NotImplementedError("pending Phase 1 → 2 dashboard work: criterion_6_founder_review_pass")


def criterion_7_corpus_health(db_url: str) -> tuple[str, str, str, bool]:
    """Exit criterion #7: Orthodox Ethos tenant has >= 100 approved chunks
    spanning at least 5 distinct sources.

    SQL (when implemented):
        SELECT
            COUNT(c.chunk_id) AS approved_chunk_count,
            COUNT(DISTINCT c.source_id) AS distinct_source_count
        FROM chunks c
        JOIN sources s ON s.source_id = c.source_id
        WHERE c.tenant_id = 'tn_orthodoxethos'
          AND c.approved = TRUE
          AND s.approved = TRUE;
        -- Pass when approved_chunk_count >= 100 AND distinct_source_count >= 5.
    """
    raise NotImplementedError("pending Phase 1 → 2 dashboard work: criterion_7_corpus_health")


def criterion_8_operational_basics(db_url: str) -> tuple[str, str, str, bool]:
    """Exit criterion #8: all runs produce a RunTrace; served_answer_count Stripe
    meter has at least one billing period; retention worker has emitted at least
    one successful worker.retention.completed event with deleted_count >= 0.

    SQL (when implemented):
        -- (a) All finished runs have a run_trace row:
        SELECT COUNT(*) AS runs_without_trace
        FROM billing_usage bu
        LEFT JOIN run_traces rt ON rt.run_id = bu.run_id
        WHERE rt.run_id IS NULL;
        -- Expect 0.

        -- (b) At least one billing_usage row for served_answer_count:
        SELECT COUNT(*) AS billing_periods
        FROM billing_usage
        WHERE metric_name = 'served_answer_count';
        -- Expect >= 1.

        -- (c) Retention worker has run at least once successfully:
        SELECT MAX(created_at) AS last_retention_run
        FROM audit_entries
        WHERE action = 'worker.retention.completed'
          AND details->>'deleted_count' IS NOT NULL;
        -- Expect NOT NULL (at least one row).
    """
    raise NotImplementedError("pending Phase 1 → 2 dashboard work: criterion_8_operational_basics")


def criterion_9_real_safety_configs(db_url: str) -> tuple[str, str, str, bool]:
    """Exit criterion #9: config/sensitivity_keywords.yaml and
    config/pastoral_filters.yaml carry founder-approved rules; version != stub
    baseline '2026-05-01.1'; CI safety-suite-execution passes against real configs.

    SQL (when implemented):
        -- Read from audit_entries row written when founder approves configs:
        SELECT details->>'sensitivity_keywords_version' AS kw_version,
               details->>'pastoral_filters_version'     AS pf_version,
               details->>'greek_review_completed'       AS greek_reviewed
        FROM audit_entries
        WHERE action = 'founder_config_approval'
        ORDER BY created_at DESC
        LIMIT 1;
        -- Pass when kw_version != '2026-05-01.1' AND pf_version != '2026-05-01.1'
        -- AND greek_reviewed = 'true'.
    """
    raise NotImplementedError("pending Phase 1 → 2 dashboard work: criterion_9_real_safety_configs")


# ---------------------------------------------------------------------------
# Criterion registry
# ---------------------------------------------------------------------------

_CRITERIA = [
    ("1", "Safety suite stability (14 consecutive CI days)",         "14 consecutive days",  criterion_1_safety_suite_stability),
    ("2", "Internal traffic threshold (≥50 distinct queries)",        "≥ 50 queries",         criterion_2_internal_traffic_threshold),
    ("3", "RED rate ceiling (≤30% over 7 days)",                      "≤ 30%",                criterion_3_red_rate_ceiling),
    ("4", "Latency target (p95 < 8 s over 7 days)",                  "p95 < 8000 ms",        criterion_4_latency_target),
    ("5", "Tenant isolation invariant (zero cross-tenant leaks)",     "0 leaks",              criterion_5_tenant_isolation_invariant),
    ("6", "Founder review pass (audit_entries signoff)",              "≥1 valid signoff",     criterion_6_founder_review_pass),
    ("7", "Corpus health (≥100 approved chunks, ≥5 sources)",        "≥100 chunks, ≥5 srcs", criterion_7_corpus_health),
    ("8", "Operational basics (traces, billing, retention worker)",   "all 3 sub-checks pass",criterion_8_operational_basics),
    ("9", "Real safety configs (founder-approved, non-stub)",         "version != 2026-05-01.1", criterion_9_real_safety_configs),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 1 → 2 exit-criteria dashboard. "
            "Reads run_traces, audit_entries, chunks, sources, billing_usage "
            "and prints each criterion's current value vs. threshold."
        )
    )
    parser.add_argument(
        "--db-url",
        required=True,
        metavar="POSTGRES_URL",
        help="PostgreSQL connection URL (e.g. postgresql://user:pass@host/db)",
    )
    args = parser.parse_args()

    print()
    print("Phase 1 → 2 Exit Criteria Dashboard")
    print("=" * 72)
    print(f"{'#':<4} {'Criterion':<46} {'Value':<18} {'Threshold':<22} {'Pass?'}")
    print("-" * 72)

    all_passing = True
    for num, name, threshold, fn in _CRITERIA:
        try:
            crit_name, current_value, thr, passing = fn(args.db_url)
        except NotImplementedError as e:
            current_value = "not yet measurable"
            thr = threshold
            passing = False
            all_passing = False
        except Exception as e:
            current_value = f"ERROR: {e}"
            thr = threshold
            passing = False
            all_passing = False

        pass_mark = "PASS" if passing else "----"
        if not passing:
            all_passing = False
        print(f"{num:<4} {name:<46} {current_value:<18} {thr:<22} {pass_mark}")

    print("-" * 72)
    if all_passing:
        print("Result: ALL CRITERIA PASS — Phase 2 gate is open.")
    else:
        print("Result: One or more criteria not yet met — Phase 2 is BLOCKED.")
    print()

    return 0 if all_passing else 1


if __name__ == "__main__":
    sys.exit(main())
