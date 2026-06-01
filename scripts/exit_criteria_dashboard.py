"""Phase 1 → 2 exit-criteria dashboard.

Audit finding: F-22
Context citations:
  - docs/contracts/phase1-implementation-contract.md — "Phase 1 → Phase 2 Exit Criteria"
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

Each criterion coroutine returns:
  (criterion_name: str, current_value: str, threshold: str, passing: bool)

Criteria backed by run_traces / chunks / billing_usage compute live values. Criteria backed by
audit_entries rows that no code emits yet (#1 ci_safety_suite_passed, #5 ci_tenant_isolation_passed,
#6 founder_phase2_signoff) report "no row yet" with passing=False until those rows accrue — they are
operational gates, not crashes. The SQL each criterion runs is also quoted in its docstring.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

import asyncpg

# Each criterion returns (criterion_name, current_value, threshold, passing).
CriterionResult = tuple[str, str, str, bool]

# The stub baseline version that exit criterion #9 forbids in real configs.
_STUB_CONFIG_VERSION = "2026-05-01.1"
# The production tenant whose corpus health exit criterion #7 measures.
_ORTHODOX_ETHOS_TENANT = "tn_orthodoxethos"


def _normalize_db_url(db_url: str) -> str:
    """asyncpg wants a plain libpq URL, not SQLAlchemy's `postgresql+asyncpg://` dialect form."""
    return db_url.replace("postgresql+asyncpg://", "postgresql://", 1)


# ---------------------------------------------------------------------------
# Criterion functions (one per Phase 1 → 2 exit criterion)
# ---------------------------------------------------------------------------


async def criterion_1_safety_suite_stability(conn: asyncpg.Connection) -> CriterionResult:
    """Exit criterion #1: test_20_queries.py passes in CI for 14 consecutive
    calendar days with no override.

    Measured via CI run history recorded as audit_entries rows (action
    'ci_safety_suite_passed'); no code emits these yet, so this reports "no row yet" until a CI
    job writes them.

    SQL:
        SELECT COUNT(DISTINCT DATE(occurred_at)) AS passing_days
        FROM audit_entries
        WHERE action = 'ci_safety_suite_passed'
          AND resource_type = 'ci_check'
          AND occurred_at >= NOW() - INTERVAL '14 days'
          AND details->>'override' IS NULL;
        -- Pass when passing_days = 14 (no gap allowed).
    """
    passing_days = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT DATE(occurred_at)) AS passing_days
        FROM audit_entries
        WHERE action = 'ci_safety_suite_passed'
          AND resource_type = 'ci_check'
          AND occurred_at >= NOW() - INTERVAL '14 days'
          AND details->>'override' IS NULL
        """
    )
    passing_days = int(passing_days or 0)
    value = "no CI rows yet" if passing_days == 0 else f"{passing_days}/14 days"
    return (
        "Safety suite stability",
        value,
        "14 consecutive days",
        passing_days >= 14,
    )


async def criterion_2_internal_traffic_threshold(conn: asyncpg.Connection) -> CriterionResult:
    """Exit criterion #2: at least 50 distinct internal queries served end-to-end.

    Cache hits and misses both count. A run is "served end-to-end" when finished_at IS NOT NULL
    AND final_handling IS NOT NULL.

    SQL:
        SELECT COUNT(DISTINCT run_id) AS served_count
        FROM run_traces
        WHERE finished_at IS NOT NULL
          AND final_handling IS NOT NULL;
        -- Pass when served_count >= 50.
    """
    served = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT run_id) AS served_count
        FROM run_traces
        WHERE finished_at IS NOT NULL
          AND final_handling IS NOT NULL
        """
    )
    served = int(served or 0)
    return (
        "Internal traffic threshold",
        f"{served} served",
        "≥ 50 queries",
        served >= 50,
    )


async def criterion_3_red_rate_ceiling(conn: asyncpg.Connection) -> CriterionResult:
    """Exit criterion #3: 7-day rolling RED rate <= 30% of served answers.

    Formula (phase1-implementation-contract.md "RED Rate Ceiling — Definition"):
        red_rate = count(finalConfidenceTier='RED' AND finalHandling != 'block_with_redirect')
                 / count(finalHandling != 'block_with_redirect')
        over last 7 days. Hard-safety blocks excluded from both numerator and denominator.

    SQL:
        WITH base AS (
            SELECT
                SUM(CASE WHEN final_confidence_tier = 'RED' THEN 1 ELSE 0 END) AS red_count,
                COUNT(*) AS total_count
            FROM run_traces
            WHERE finished_at IS NOT NULL
              AND final_handling IS NOT NULL
              AND final_handling != 'block_with_redirect'
              AND finished_at >= NOW() - INTERVAL '7 days'
        )
        SELECT red_count, total_count,
               ROUND(red_count::numeric / NULLIF(total_count, 0), 4) AS red_rate
        FROM base;
        -- Pass when red_rate <= 0.30 (and total_count > 0).
    """
    row = await conn.fetchrow(
        """
        WITH base AS (
            SELECT
                SUM(CASE WHEN final_confidence_tier = 'RED' THEN 1 ELSE 0 END) AS red_count,
                COUNT(*) AS total_count
            FROM run_traces
            WHERE finished_at IS NOT NULL
              AND final_handling IS NOT NULL
              AND final_handling != 'block_with_redirect'
              AND finished_at >= NOW() - INTERVAL '7 days'
        )
        SELECT red_count, total_count,
               ROUND(red_count::numeric / NULLIF(total_count, 0), 4) AS red_rate
        FROM base
        """
    )
    total = int(row["total_count"] or 0)
    if total == 0:
        # No served answers in the window → the ceiling cannot be demonstrated met.
        return ("RED rate ceiling", "no answers in 7d", "≤ 30%", False)
    red_rate = float(row["red_rate"] or 0.0)
    return (
        "RED rate ceiling",
        f"{red_rate * 100:.1f}% ({total} ans)",
        "≤ 30%",
        red_rate <= 0.30,
    )


async def criterion_4_latency_target(conn: asyncpg.Connection) -> CriterionResult:
    """Exit criterion #4: p95 query latency < 8000 ms over the last 7 days.

    Latency is computed from started_at/finished_at. run_traces only holds query-pipeline runs.

    SQL:
        SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (
                   ORDER BY EXTRACT(EPOCH FROM (finished_at - started_at)) * 1000
               ) AS p95_latency_ms
        FROM run_traces
        WHERE finished_at IS NOT NULL
          AND final_handling IS NOT NULL
          AND finished_at >= NOW() - INTERVAL '7 days';
        -- Pass when p95_latency_ms < 8000.
    """
    p95 = await conn.fetchval(
        """
        SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (
                   ORDER BY EXTRACT(EPOCH FROM (finished_at - started_at)) * 1000
               ) AS p95_latency_ms
        FROM run_traces
        WHERE finished_at IS NOT NULL
          AND final_handling IS NOT NULL
          AND finished_at >= NOW() - INTERVAL '7 days'
        """
    )
    if p95 is None:
        # No completed runs in the window → cannot demonstrate the latency target.
        return ("Latency target (p95)", "no runs in 7d", "p95 < 8000 ms", False)
    p95 = float(p95)
    return (
        "Latency target (p95)",
        f"{p95:.0f} ms",
        "p95 < 8000 ms",
        p95 < 8000.0,
    )


async def criterion_5_tenant_isolation_invariant(conn: asyncpg.Connection) -> CriterionResult:
    """Exit criterion #5: zero cross-tenant leaks across deployment history.

    Measured via the CI tenant-isolation test result recorded as an audit_entries row
    (action 'ci_tenant_isolation_passed'); no code emits this yet → "no row yet".

    SQL:
        SELECT details->>'result' AS last_result
        FROM audit_entries
        WHERE action = 'ci_tenant_isolation_passed'
          AND resource_type = 'ci_check'
        ORDER BY occurred_at DESC
        LIMIT 1;
        -- Pass when last_result = 'pass'.
    """
    last_result = await conn.fetchval(
        """
        SELECT details->>'result' AS last_result
        FROM audit_entries
        WHERE action = 'ci_tenant_isolation_passed'
          AND resource_type = 'ci_check'
        ORDER BY occurred_at DESC
        LIMIT 1
        """
    )
    if last_result is None:
        return ("Tenant isolation invariant", "no CI row yet", "last result = pass", False)
    return (
        "Tenant isolation invariant",
        str(last_result),
        "last result = pass",
        last_result == "pass",
    )


async def criterion_6_founder_review_pass(conn: asyncpg.Connection) -> CriterionResult:
    """Exit criterion #6: at least one audit_entries row with action='founder_phase2_signoff',
    >= 20 reviewedRunIds, >= 3 distinct sensitivityCategoriesCovered, actor is owner.

    SQL:
        SELECT ae.audit_id
        FROM audit_entries ae
        JOIN users u ON u.user_id = ae.actor_user_id
        WHERE ae.action = 'founder_phase2_signoff'
          AND ae.resource_type = 'tenant'
          AND u.role = 'owner'
          AND jsonb_typeof(ae.details->'reviewedRunIds') = 'array'
          AND jsonb_typeof(ae.details->'sensitivityCategoriesCovered') = 'array'
          AND jsonb_array_length(ae.details->'reviewedRunIds') >= 20
          AND jsonb_array_length(ae.details->'sensitivityCategoriesCovered') >= 3
        ORDER BY ae.occurred_at DESC
        LIMIT 1;
        -- Pass when at least one row returned.
    """
    # jsonb_typeof guards jsonb_array_length against a scalar/null value (which would raise 22023).
    audit_id = await conn.fetchval(
        """
        SELECT ae.audit_id
        FROM audit_entries ae
        JOIN users u ON u.user_id = ae.actor_user_id
        WHERE ae.action = 'founder_phase2_signoff'
          AND ae.resource_type = 'tenant'
          AND u.role = 'owner'
          AND jsonb_typeof(ae.details->'reviewedRunIds') = 'array'
          AND jsonb_typeof(ae.details->'sensitivityCategoriesCovered') = 'array'
          AND jsonb_array_length(ae.details->'reviewedRunIds') >= 20
          AND jsonb_array_length(ae.details->'sensitivityCategoriesCovered') >= 3
        ORDER BY ae.occurred_at DESC
        LIMIT 1
        """
    )
    if audit_id is None:
        return ("Founder review pass", "no signoff yet", "≥1 valid signoff", False)
    return ("Founder review pass", "signed off", "≥1 valid signoff", True)


async def criterion_7_corpus_health(conn: asyncpg.Connection) -> CriterionResult:
    """Exit criterion #7: Orthodox Ethos tenant has >= 100 approved chunks spanning >= 5 sources.

    SQL:
        SELECT COUNT(c.chunk_id) AS approved_chunk_count,
               COUNT(DISTINCT c.source_id) AS distinct_source_count
        FROM chunks c
        JOIN sources s ON s.source_id = c.source_id
        WHERE c.tenant_id = 'tn_orthodoxethos'
          AND c.approved = TRUE
          AND s.approved = TRUE;
        -- Pass when approved_chunk_count >= 100 AND distinct_source_count >= 5.
    """
    row = await conn.fetchrow(
        """
        SELECT COUNT(c.chunk_id) AS approved_chunk_count,
               COUNT(DISTINCT c.source_id) AS distinct_source_count
        FROM chunks c
        JOIN sources s ON s.source_id = c.source_id
        WHERE c.tenant_id = $1
          AND c.approved = TRUE
          AND s.approved = TRUE
        """,
        _ORTHODOX_ETHOS_TENANT,
    )
    chunks = int(row["approved_chunk_count"] or 0)
    sources = int(row["distinct_source_count"] or 0)
    return (
        "Corpus health",
        f"{chunks} chunks, {sources} srcs",
        "≥100 chunks, ≥5 srcs",
        chunks >= 100 and sources >= 5,
    )


async def criterion_8_operational_basics(conn: asyncpg.Connection) -> CriterionResult:
    """Exit criterion #8: (a) runs produce a RunTrace, (b) served_answer_count Stripe meter has
    reported at least one billing period, (c) retention worker has emitted at least one successful
    purge recorded as an audit_entries row (action='retention_purged').

    SQL:
        SELECT COUNT(*) FROM run_traces;                                 -- (a) expect >= 1
        SELECT COUNT(*) FROM billing_usage
          WHERE served_answer_count > 0 AND stripe_usage_record_id IS NOT NULL;  -- (b) expect >= 1
        SELECT MAX(occurred_at) FROM audit_entries
          WHERE action = 'retention_purged'
            AND details->>'deleted_count' IS NOT NULL;                   -- (c) expect NOT NULL
    """
    run_trace_rows = int(await conn.fetchval("SELECT COUNT(*) FROM run_traces") or 0)
    billing_periods = int(
        await conn.fetchval(
            """
            SELECT COUNT(*) FROM billing_usage
            WHERE served_answer_count > 0 AND stripe_usage_record_id IS NOT NULL
            """
        )
        or 0
    )
    last_retention = await conn.fetchval(
        """
        SELECT MAX(occurred_at) FROM audit_entries
        WHERE action = 'retention_purged'
          AND details->>'deleted_count' IS NOT NULL
        """
    )
    a_ok = run_trace_rows >= 1
    b_ok = billing_periods >= 1
    c_ok = last_retention is not None
    value = f"trace={'Y' if a_ok else 'N'} bill={'Y' if b_ok else 'N'} ret={'Y' if c_ok else 'N'}"
    return ("Operational basics", value, "all 3 sub-checks", a_ok and b_ok and c_ok)


async def criterion_9_real_safety_configs(conn: asyncpg.Connection) -> CriterionResult:
    """Exit criterion #9: founder-approved safety configs whose versions != the stub baseline
    '2026-05-01.1', recorded as an audit_entries row (action='safety_config_approved').

    SQL:
        SELECT details->>'sensitivity_keywords_version' AS kw_version,
               details->>'pastoral_filters_version'     AS pf_version,
               details->>'greek_review_completed'       AS greek_reviewed
        FROM audit_entries
        WHERE action = 'safety_config_approved'
          AND resource_type = 'safety_config'
        ORDER BY occurred_at DESC
        LIMIT 1;
        -- Pass when kw_version != '2026-05-01.1' AND pf_version != '2026-05-01.1'
        --   AND greek_reviewed = 'true'.
    """
    row = await conn.fetchrow(
        """
        SELECT details->>'sensitivity_keywords_version' AS kw_version,
               details->>'pastoral_filters_version'     AS pf_version,
               details->>'greek_review_completed'       AS greek_reviewed
        FROM audit_entries
        WHERE action = 'safety_config_approved'
          AND resource_type = 'safety_config'
        ORDER BY occurred_at DESC
        LIMIT 1
        """
    )
    if row is None:
        return ("Real safety configs", "no approval row", "approved, non-stub", False)
    kw_version = row["kw_version"]
    pf_version = row["pf_version"]
    greek_reviewed = row["greek_reviewed"]
    passing = (
        kw_version not in (None, _STUB_CONFIG_VERSION)
        and pf_version not in (None, _STUB_CONFIG_VERSION)
        and greek_reviewed == "true"
    )
    value = f"kw={kw_version} pf={pf_version}"
    return ("Real safety configs", value, "approved, non-stub", passing)


# ---------------------------------------------------------------------------
# Criterion registry
# ---------------------------------------------------------------------------

_CRITERIA = [
    ("1", "Safety suite stability (14 consecutive CI days)", criterion_1_safety_suite_stability),
    ("2", "Internal traffic threshold (≥50 distinct queries)", criterion_2_internal_traffic_threshold),  # noqa: E501
    ("3", "RED rate ceiling (≤30% over 7 days)", criterion_3_red_rate_ceiling),
    ("4", "Latency target (p95 < 8 s over 7 days)", criterion_4_latency_target),
    ("5", "Tenant isolation invariant (zero cross-tenant leaks)", criterion_5_tenant_isolation_invariant),  # noqa: E501
    ("6", "Founder review pass (audit_entries signoff)", criterion_6_founder_review_pass),
    ("7", "Corpus health (≥100 approved chunks, ≥5 sources)", criterion_7_corpus_health),
    ("8", "Operational basics (traces, billing, retention worker)", criterion_8_operational_basics),  # noqa: E501
    ("9", "Real safety configs (founder-approved, non-stub)", criterion_9_real_safety_configs),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def _evaluate(db_url: str) -> list[tuple[str, str, str, str, bool]]:
    """Open one connection and evaluate every criterion. Returns
    (num, registry_name, value, threshold, passing) per criterion; a per-criterion error is
    captured as a non-passing row rather than aborting the whole dashboard."""
    conn = await asyncpg.connect(_normalize_db_url(db_url))
    rows: list[tuple[str, str, str, str, bool]] = []
    try:
        for num, name, fn in _CRITERIA:
            try:
                _crit_name, value, threshold, passing = await fn(conn)
            except Exception as exc:  # noqa: BLE001 - one bad criterion shouldn't hide the rest
                value, threshold, passing = f"ERROR: {exc}", "—", False
            rows.append((num, name, value, threshold, passing))
    finally:
        await conn.close()
    return rows


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

    try:
        results = asyncio.run(_evaluate(args.db_url))
    except (OSError, asyncpg.PostgresError) as exc:
        print(f"error: could not evaluate exit criteria: {exc}", file=sys.stderr)
        return 2

    print()
    print("Phase 1 → 2 Exit Criteria Dashboard")
    print("=" * 72)
    print(f"{'#':<4} {'Criterion':<46} {'Value':<18} {'Threshold':<22} {'Pass?'}")
    print("-" * 72)

    all_passing = True
    for num, name, value, threshold, passing in results:
        if not passing:
            all_passing = False
        pass_mark = "PASS" if passing else "----"
        print(f"{num:<4} {name:<46} {value:<18} {threshold:<22} {pass_mark}")

    print("-" * 72)
    if all_passing:
        print("Result: ALL CRITERIA PASS — Phase 2 gate is open.")
    else:
        print("Result: One or more criteria not yet met — Phase 2 is BLOCKED.")
    print()

    return 0 if all_passing else 1


if __name__ == "__main__":
    sys.exit(main())
