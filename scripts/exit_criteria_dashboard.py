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

Each function runs a small read-only query (the SQL is inlined) and delegates
the threshold decision to a pure ``_eval_*`` helper so the pass/fail logic is
unit-testable without a database. Column names are verified against
``backend/app/alembic/versions/0001_initial.py``.
"""
from __future__ import annotations

import argparse
import sys

try:  # SQLAlchemy + a sync driver are only needed to actually run the queries.
    from sqlalchemy import create_engine, text
except ImportError:  # pragma: no cover - import guard so --help / tests work without the dep
    create_engine = None  # type: ignore[assignment]
    text = None  # type: ignore[assignment]


# Stub baseline that exit criterion #9 must move past (see safety_config.py).
STUB_CONFIG_VERSION = "2026-05-01.1"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

_ENGINES: dict = {}


def _normalize_db_url(db_url: str) -> str:
    """Pin the sync psycopg (v3) driver the backend already depends on, so a
    plain ``postgresql://`` URL does not fall back to an absent psycopg2."""
    for prefix in ("postgresql://", "postgres://"):
        if db_url.startswith(prefix):
            return "postgresql+psycopg://" + db_url[len(prefix):]
    return db_url


def _engine(db_url: str):
    if create_engine is None:  # pragma: no cover
        raise RuntimeError(
            "SQLAlchemy + psycopg are required to run the dashboard "
            "(pip install 'sqlalchemy>=2' 'psycopg[binary]')."
        )
    norm = _normalize_db_url(db_url)
    eng = _ENGINES.get(norm)
    if eng is None:
        eng = create_engine(norm, future=True, pool_pre_ping=True)
        _ENGINES[norm] = eng
    return eng


def _fetch_one(db_url: str, sql: str):
    """Run a single read-only statement and return the first row (or None)."""
    with _engine(db_url).connect() as conn:
        return conn.execute(text(sql)).first()


# ---------------------------------------------------------------------------
# Pure evaluators (no DB) — these hold the threshold logic and are unit-tested.
# ---------------------------------------------------------------------------


def _eval_consecutive_days(passing_days: int) -> tuple[str, bool]:
    return f"{passing_days}/14 days", passing_days >= 14


def _eval_min_count(value: int, minimum: int) -> tuple[str, bool]:
    return str(value), value >= minimum


def _eval_red_rate(red_count: int, total_count: int) -> tuple[str, bool]:
    if total_count <= 0:
        return "no served answers", False
    rate = red_count / total_count
    return f"{rate:.1%} ({red_count}/{total_count})", rate <= 0.30


def _eval_p95(p95_ms: float | None) -> tuple[str, bool]:
    if p95_ms is None:
        return "no data", False
    return f"{p95_ms:.0f} ms", p95_ms < 8000


def _eval_last_result(last_result: str | None) -> tuple[str, bool]:
    if last_result is None:
        return "no CI record", False
    return last_result, last_result == "pass"


def _eval_founder_signoff(
    actor_role: str | None, reviewed_count: int, sensitivity_count: int
) -> tuple[str, bool]:
    if actor_role is None:
        return "no signoff", False
    passing = actor_role == "owner" and reviewed_count >= 20 and sensitivity_count >= 3
    return f"{reviewed_count} runs / {sensitivity_count} cats", passing


def _eval_corpus(approved_chunks: int, distinct_sources: int) -> tuple[str, bool]:
    passing = approved_chunks >= 100 and distinct_sources >= 5
    return f"{approved_chunks} ch / {distinct_sources} src", passing


def _eval_operational(
    run_trace_rows: int, billing_periods: int, last_retention
) -> tuple[str, bool]:
    traces_ok = run_trace_rows >= 1
    billing_ok = billing_periods >= 1
    retention_ok = last_retention is not None
    passing = traces_ok and billing_ok and retention_ok
    value = "{}{}{}".format(
        "trace" + ("✓" if traces_ok else "✗") + " ",
        "bill" + ("✓" if billing_ok else "✗") + " ",
        "ret" + ("✓" if retention_ok else "✗"),
    )
    return value, passing


def _eval_safety_configs(
    kw_version: str | None, pf_version: str | None
) -> tuple[str, bool]:
    # Founder-only model (2026-05-20): the existence of the safety_config_approved
    # row is the founder's approval signal; there is no separate reviewer gate.
    # Greek-language coverage is enforced inside the configs, not by this check.
    if kw_version is None or pf_version is None:
        return "not approved", False
    non_stub = kw_version != STUB_CONFIG_VERSION and pf_version != STUB_CONFIG_VERSION
    return ("non-stub" if non_stub else "stub baseline"), non_stub


# ---------------------------------------------------------------------------
# Criterion functions (one per Phase 1 → 2 exit criterion)
# ---------------------------------------------------------------------------


def criterion_1_safety_suite_stability(db_url: str) -> tuple[str, str, str, bool]:
    """#1: test_20_queries.py passes in CI for 14 consecutive days, no override."""
    row = _fetch_one(
        db_url,
        """
        SELECT COUNT(DISTINCT DATE(occurred_at)) AS passing_days
        FROM audit_entries
        WHERE action = 'ci_safety_suite_passed'
          AND resource_type = 'ci_check'
          AND occurred_at >= NOW() - INTERVAL '14 days'
          AND details->>'override' IS NULL
        """,
    )
    value, passing = _eval_consecutive_days(int(row.passing_days) if row else 0)
    return "Safety suite stability", value, "14 consecutive days", passing


def criterion_2_internal_traffic_threshold(db_url: str) -> tuple[str, str, str, bool]:
    """#2: at least 50 distinct internal queries served end-to-end."""
    row = _fetch_one(
        db_url,
        """
        SELECT COUNT(DISTINCT run_id) AS served_count
        FROM run_traces
        WHERE finished_at IS NOT NULL
          AND final_handling IS NOT NULL
        """,
    )
    value, passing = _eval_min_count(int(row.served_count) if row else 0, 50)
    return "Internal traffic threshold", value, "≥ 50 queries", passing


def criterion_3_red_rate_ceiling(db_url: str) -> tuple[str, str, str, bool]:
    """#3: 7-day rolling RED rate <= 30% of served answers (hard blocks excluded)."""
    row = _fetch_one(
        db_url,
        """
        SELECT
            COALESCE(SUM(CASE WHEN final_confidence_tier = 'RED' THEN 1 ELSE 0 END), 0) AS red_count,
            COUNT(*) AS total_count
        FROM run_traces
        WHERE finished_at IS NOT NULL
          AND final_handling IS NOT NULL
          AND final_handling != 'block_with_redirect'
          AND finished_at >= NOW() - INTERVAL '7 days'
        """,
    )
    red = int(row.red_count) if row else 0
    total = int(row.total_count) if row else 0
    value, passing = _eval_red_rate(red, total)
    return "RED rate ceiling", value, "≤ 30%", passing


def criterion_4_latency_target(db_url: str) -> tuple[str, str, str, bool]:
    """#4: p95 query latency < 8000 ms at /api/v1/query boundary, last 7 days."""
    row = _fetch_one(
        db_url,
        """
        SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (
                   ORDER BY EXTRACT(EPOCH FROM (finished_at - started_at)) * 1000
               ) AS p95_latency_ms
        FROM run_traces
        WHERE finished_at IS NOT NULL
          AND final_handling IS NOT NULL
          AND finished_at >= NOW() - INTERVAL '7 days'
        """,
    )
    p95 = float(row.p95_latency_ms) if row and row.p95_latency_ms is not None else None
    value, passing = _eval_p95(p95)
    return "Latency target", value, "p95 < 8000 ms", passing


def criterion_5_tenant_isolation_invariant(db_url: str) -> tuple[str, str, str, bool]:
    """#5: zero cross-tenant leaks — last CI result for the isolation suite."""
    row = _fetch_one(
        db_url,
        """
        SELECT details->>'result' AS last_result
        FROM audit_entries
        WHERE action = 'ci_tenant_isolation_passed'
          AND resource_type = 'ci_check'
        ORDER BY occurred_at DESC
        LIMIT 1
        """,
    )
    value, passing = _eval_last_result(row.last_result if row else None)
    return "Tenant isolation invariant", value, "result = pass", passing


def criterion_6_founder_review_pass(db_url: str) -> tuple[str, str, str, bool]:
    """#6: a founder_phase2_signoff by an owner, >=20 reviewed runs, >=3 categories."""
    row = _fetch_one(
        db_url,
        """
        SELECT
            actor_role,
            jsonb_array_length(COALESCE(details->'reviewedRunIds', '[]'::jsonb)) AS reviewed_count,
            jsonb_array_length(COALESCE(details->'sensitivityCategoriesCovered', '[]'::jsonb)) AS sensitivity_count
        FROM audit_entries
        WHERE action = 'founder_phase2_signoff'
          AND resource_type = 'tenant'
        ORDER BY occurred_at DESC
        LIMIT 1
        """,
    )
    if row is None:
        value, passing = _eval_founder_signoff(None, 0, 0)
    else:
        value, passing = _eval_founder_signoff(
            row.actor_role, int(row.reviewed_count), int(row.sensitivity_count)
        )
    return "Founder review pass", value, "≥1 valid signoff", passing


def criterion_7_corpus_health(db_url: str) -> tuple[str, str, str, bool]:
    """#7: Orthodox Ethos tenant has >=100 approved chunks across >=5 sources."""
    row = _fetch_one(
        db_url,
        """
        SELECT
            COUNT(c.chunk_id) AS approved_chunk_count,
            COUNT(DISTINCT c.source_id) AS distinct_source_count
        FROM chunks c
        JOIN sources s ON s.source_id = c.source_id
        WHERE c.tenant_id = 'tn_orthodoxethos'
          AND c.approved = TRUE
          AND s.approved = TRUE
        """,
    )
    chunks = int(row.approved_chunk_count) if row else 0
    sources = int(row.distinct_source_count) if row else 0
    value, passing = _eval_corpus(chunks, sources)
    return "Corpus health", value, "≥100 ch, ≥5 src", passing


def criterion_8_operational_basics(db_url: str) -> tuple[str, str, str, bool]:
    """#8: run traces persist, a billing period reported, retention worker ran."""
    traces = _fetch_one(db_url, "SELECT COUNT(*) AS n FROM run_traces")
    billing = _fetch_one(
        db_url,
        """
        SELECT COUNT(*) AS n
        FROM billing_usage
        WHERE served_answer_count > 0
          AND stripe_usage_record_id IS NOT NULL
        """,
    )
    retention = _fetch_one(
        db_url,
        """
        SELECT MAX(occurred_at) AS last_retention
        FROM audit_entries
        WHERE action = 'retention_purged'
          AND details->>'deleted_count' IS NOT NULL
        """,
    )
    value, passing = _eval_operational(
        int(traces.n) if traces else 0,
        int(billing.n) if billing else 0,
        retention.last_retention if retention else None,
    )
    return "Operational basics", value, "all 3 sub-checks", passing


def criterion_9_real_safety_configs(db_url: str) -> tuple[str, str, str, bool]:
    """#9: founder-approved, non-stub safety configs (founder-only ownership)."""
    row = _fetch_one(
        db_url,
        """
        SELECT details->>'sensitivity_keywords_version' AS kw_version,
               details->>'pastoral_filters_version'     AS pf_version
        FROM audit_entries
        WHERE action = 'safety_config_approved'
          AND resource_type = 'safety_config'
        ORDER BY occurred_at DESC
        LIMIT 1
        """,
    )
    value, passing = _eval_safety_configs(
        row.kw_version if row else None, row.pf_version if row else None
    )
    return "Real safety configs", value, "version != stub", passing


# ---------------------------------------------------------------------------
# Criterion registry
# ---------------------------------------------------------------------------

_CRITERIA = [
    ("1", "Safety suite stability (14 consecutive CI days)",          "14 consecutive days",  criterion_1_safety_suite_stability),
    ("2", "Internal traffic threshold (≥50 distinct queries)",   "≥ 50 queries",    criterion_2_internal_traffic_threshold),
    ("3", "RED rate ceiling (≤30% over 7 days)",                 "≤ 30%",           criterion_3_red_rate_ceiling),
    ("4", "Latency target (p95 < 8 s over 7 days)",                   "p95 < 8000 ms",        criterion_4_latency_target),
    ("5", "Tenant isolation invariant (zero cross-tenant leaks)",      "0 leaks",              criterion_5_tenant_isolation_invariant),
    ("6", "Founder review pass (audit_entries signoff)",               "≥1 valid signoff",criterion_6_founder_review_pass),
    ("7", "Corpus health (≥100 approved chunks, ≥5 sources)","≥100 ch, ≥5 src", criterion_7_corpus_health),
    ("8", "Operational basics (traces, billing, retention worker)",    "all 3 sub-checks pass", criterion_8_operational_basics),
    ("9", "Real safety configs (founder-approved, non-stub)",          "version != 2026-05-01.1", criterion_9_real_safety_configs),
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

    # Fail fast with a single clear message rather than 9 identical errors.
    try:
        with _engine(args.db_url).connect():
            pass
    except Exception as e:  # noqa: BLE001 - operator-facing diagnostic
        print(f"\nCould not connect to the database: {e}\n", file=sys.stderr)
        return 2

    print()
    print("Phase 1 → 2 Exit Criteria Dashboard")
    print("=" * 72)
    print(f"{'#':<4} {'Criterion':<46} {'Value':<18} {'Threshold':<22} {'Pass?'}")
    print("-" * 72)

    all_passing = True
    for num, name, threshold, fn in _CRITERIA:
        try:
            _crit_name, current_value, thr, passing = fn(args.db_url)
        except Exception as e:  # noqa: BLE001 - one criterion erroring must not abort the rest
            current_value = f"ERROR: {e}"
            thr = threshold
            passing = False

        if not passing:
            all_passing = False
        pass_mark = "PASS" if passing else "----"
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
