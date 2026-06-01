"""DB-backed tests for scripts/exit_criteria_dashboard.py.

Each criterion reads run_traces / chunks / sources / billing_usage / audit_entries and returns
(name, value, threshold, passing). These seed boundary cases and assert the computed value + the
passing flag, against the real Postgres the integration suite uses (REQUIRE_DB path). The dashboard
lives in repo-root scripts/, so we load it by path (mirroring tests/unit/test_validate_gold_set.py).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

pytest.importorskip("app")

pytestmark = pytest.mark.asyncio

# Load the repo-root script by path (not an installed package).
_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "exit_criteria_dashboard.py"
_spec = importlib.util.spec_from_file_location("exit_criteria_dashboard", _SCRIPT)
assert _spec and _spec.loader
dashboard = importlib.util.module_from_spec(_spec)
sys.modules["exit_criteria_dashboard"] = dashboard
_spec.loader.exec_module(dashboard)

# A plain libpq URL for asyncpg.connect (the app default; conftest guarantees it's reachable here).
_DB_URL = "postgresql://orthodox:orthodox@localhost:5432/orthodox"


async def _connect():
    import asyncpg

    return await asyncpg.connect(dashboard._normalize_db_url(_DB_URL))


async def _insert_run(
    conn,
    *,
    run_id: str,
    tenant_id: str,
    user_id: str,
    started_at: datetime,
    finished_at: datetime | None,
    final_handling: str | None,
    final_confidence_tier: str | None,
) -> None:
    await conn.execute(
        """
        INSERT INTO run_traces (
            run_id, tenant_id, user_id, started_at, finished_at,
            final_handling, final_confidence_tier
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        run_id,
        tenant_id,
        user_id,
        started_at,
        finished_at,
        final_handling,
        final_confidence_tier,
    )


@pytest_asyncio.fixture()
async def conn(seed_tenant: tuple[str, str]):
    """An asyncpg connection over the seeded test DB (seed_tenant -> clean_tables runs first)."""
    del seed_tenant
    c = await _connect()
    try:
        yield c
    finally:
        await c.close()


# ---------------------------------------------------------------------------
# Empty-DB safety: no criterion crashes, none pass.
# ---------------------------------------------------------------------------
async def test_all_criteria_handle_empty_db(conn) -> None:
    for _num, _name, fn in dashboard._CRITERIA:
        name, value, threshold, passing = await fn(conn)
        assert isinstance(value, str) and value  # non-empty display string
        assert isinstance(threshold, str) and threshold
        assert passing is False, f"{name} should not pass on an empty DB"


# ---------------------------------------------------------------------------
# Criterion 2 — internal traffic threshold (≥50 served).
# ---------------------------------------------------------------------------
async def test_criterion_2_below_and_at_threshold(conn) -> None:
    tenant_id, user_id = "tn_test", "usr_test"
    now = datetime.now(UTC)
    for i in range(49):
        await _insert_run(
            conn, run_id=f"run_c2_{i}", tenant_id=tenant_id, user_id=user_id,
            started_at=now, finished_at=now, final_handling="answer",
            final_confidence_tier="GREEN",
        )
    _name, value, _thr, passing = await dashboard.criterion_2_internal_traffic_threshold(conn)
    assert "49" in value
    assert passing is False

    await _insert_run(
        conn, run_id="run_c2_49", tenant_id=tenant_id, user_id=user_id,
        started_at=now, finished_at=now, final_handling="answer",
        final_confidence_tier="GREEN",
    )
    _name, value, _thr, passing = await dashboard.criterion_2_internal_traffic_threshold(conn)
    assert "50" in value
    assert passing is True


# ---------------------------------------------------------------------------
# Criterion 3 — RED rate ceiling (≤30%, block_with_redirect excluded).
# ---------------------------------------------------------------------------
async def test_criterion_3_red_rate_excludes_blocks_and_respects_ceiling(conn) -> None:
    tenant_id, user_id = "tn_test", "usr_test"
    now = datetime.now(UTC)
    # 10 answered: 3 RED, 7 GREEN -> 30% (passes, boundary is <=).
    for i in range(3):
        await _insert_run(
            conn, run_id=f"run_c3_red_{i}", tenant_id=tenant_id, user_id=user_id,
            started_at=now, finished_at=now, final_handling="answer",
            final_confidence_tier="RED",
        )
    for i in range(7):
        await _insert_run(
            conn, run_id=f"run_c3_green_{i}", tenant_id=tenant_id, user_id=user_id,
            started_at=now, finished_at=now, final_handling="answer",
            final_confidence_tier="GREEN",
        )
    # A hard-safety block that is ALSO RED must be excluded from both num and denom.
    await _insert_run(
        conn, run_id="run_c3_block", tenant_id=tenant_id, user_id=user_id,
        started_at=now, finished_at=now, final_handling="block_with_redirect",
        final_confidence_tier="RED",
    )
    _name, value, _thr, passing = await dashboard.criterion_3_red_rate_ceiling(conn)
    assert "30.0%" in value
    assert "10 ans" in value  # the block is excluded from the denominator
    assert passing is True

    # One more RED answer -> 4/11 ≈ 36.4% -> fails.
    await _insert_run(
        conn, run_id="run_c3_red_extra", tenant_id=tenant_id, user_id=user_id,
        started_at=now, finished_at=now, final_handling="answer",
        final_confidence_tier="RED",
    )
    _name, _value, _thr, passing = await dashboard.criterion_3_red_rate_ceiling(conn)
    assert passing is False


# ---------------------------------------------------------------------------
# Criterion 4 — p95 latency < 8000 ms.
# ---------------------------------------------------------------------------
async def test_criterion_4_latency_pass_then_fail(conn) -> None:
    tenant_id, user_id = "tn_test", "usr_test"
    now = datetime.now(UTC)
    # 20 fast runs (~1s) -> p95 well under 8s.
    for i in range(20):
        await _insert_run(
            conn, run_id=f"run_c4_fast_{i}", tenant_id=tenant_id, user_id=user_id,
            started_at=now - timedelta(seconds=1), finished_at=now,
            final_handling="answer", final_confidence_tier="GREEN",
        )
    _name, _value, _thr, passing = await dashboard.criterion_4_latency_target(conn)
    assert passing is True

    # Add slow runs (~20s) so the p95 crosses 8000 ms.
    for i in range(5):
        await _insert_run(
            conn, run_id=f"run_c4_slow_{i}", tenant_id=tenant_id, user_id=user_id,
            started_at=now - timedelta(seconds=20), finished_at=now,
            final_handling="answer", final_confidence_tier="GREEN",
        )
    _name, value, _thr, passing = await dashboard.criterion_4_latency_target(conn)
    assert "ms" in value
    assert passing is False


# ---------------------------------------------------------------------------
# Criterion 7 — corpus health (≥100 approved chunks, ≥5 sources) for tn_orthodoxethos.
# ---------------------------------------------------------------------------
def _sha(seed: str) -> str:
    """A unique, schema-valid `sha256:<64 hex>` hash per seed (the CHECK + unique constraints
    on sources/chunks require distinct, well-formed hashes)."""
    import hashlib

    return "sha256:" + hashlib.sha256(seed.encode()).hexdigest()


async def _seed_orthodox_ethos_corpus(conn, *, n_sources: int, chunks_per_source: int) -> None:
    await conn.execute(
        """
        INSERT INTO tenants (tenant_id, name, clerk_org_id, status, data_region)
        VALUES ('tn_orthodoxethos', 'Orthodox Ethos', 'clerk_org_oe', 'active', 'us')
        ON CONFLICT (tenant_id) DO NOTHING
        """
    )
    for s in range(n_sources):
        await conn.execute(
            """
            INSERT INTO sources (
                source_id, tenant_id, title, language, source_type, source_hash,
                extraction_method, approved, corpus_version, created_at
            ) VALUES ($1, 'tn_orthodoxethos', $2, 'en', 'pdf', $3, 'plain', TRUE,
                      '2026-05-01.1', now())
            """,
            f"src_oe_{s}",
            f"Source {s}",
            _sha(f"src_oe_{s}"),
        )
        for c in range(chunks_per_source):
            await conn.execute(
                """
                INSERT INTO chunks (
                    chunk_id, source_id, tenant_id, text, chunk_hash, approved, visibility,
                    embedding_model, embedding_dimension, corpus_version
                ) VALUES ($1, $2, 'tn_orthodoxethos', 'body', $3, TRUE, 'member',
                          'text-embedding-3-small', 1536, '2026-05-01.1')
                """,
                f"chk_oe_{s}_{c}",
                f"src_oe_{s}",
                _sha(f"chk_oe_{s}_{c}"),
            )


async def test_criterion_7_corpus_health_boundary(conn) -> None:
    # 4 sources × 25 chunks = 100 chunks but only 4 sources -> fails on the source count.
    await _seed_orthodox_ethos_corpus(conn, n_sources=4, chunks_per_source=25)
    _name, value, _thr, passing = await dashboard.criterion_7_corpus_health(conn)
    assert "100 chunks, 4 srcs" in value
    assert passing is False

    # Add a 5th source with 1 chunk -> 101 chunks, 5 sources -> passes.
    await conn.execute(
        """
        INSERT INTO sources (
            source_id, tenant_id, title, language, source_type, source_hash,
            extraction_method, approved, corpus_version, created_at
        ) VALUES ('src_oe_4', 'tn_orthodoxethos', 'Source 4', 'en', 'pdf', $1, 'plain', TRUE,
                  '2026-05-01.1', now())
        """,
        _sha("src_oe_4"),
    )
    await conn.execute(
        """
        INSERT INTO chunks (
            chunk_id, source_id, tenant_id, text, chunk_hash, approved, visibility,
            embedding_model, embedding_dimension, corpus_version
        ) VALUES ('chk_oe_4_0', 'src_oe_4', 'tn_orthodoxethos', 'body', $1, TRUE, 'member',
                  'text-embedding-3-small', 1536, '2026-05-01.1')
        """,
        _sha("chk_oe_4_0"),
    )
    _name, value, _thr, passing = await dashboard.criterion_7_corpus_health(conn)
    assert "101 chunks, 5 srcs" in value
    assert passing is True


async def test_criterion_7_unapproved_chunks_do_not_count(conn) -> None:
    await _seed_orthodox_ethos_corpus(conn, n_sources=5, chunks_per_source=20)
    # Flip every chunk to unapproved -> 0 approved chunks despite 5 sources.
    await conn.execute("UPDATE chunks SET approved = FALSE WHERE tenant_id = 'tn_orthodoxethos'")
    _name, value, _thr, passing = await dashboard.criterion_7_corpus_health(conn)
    assert "0 chunks" in value
    assert passing is False


# ---------------------------------------------------------------------------
# Criterion 8 — operational basics (run traces + billing period + retention audit row).
# ---------------------------------------------------------------------------
async def test_criterion_8_three_subchecks(conn) -> None:
    tenant_id, user_id = "tn_test", "usr_test"
    now = datetime.now(UTC)

    # (a) only a run_trace so far -> trace=Y, bill=N, ret=N -> fails.
    await _insert_run(
        conn, run_id="run_c8", tenant_id=tenant_id, user_id=user_id,
        started_at=now, finished_at=now, final_handling="answer",
        final_confidence_tier="GREEN",
    )
    _name, value, _thr, passing = await dashboard.criterion_8_operational_basics(conn)
    assert value == "trace=Y bill=N ret=N"
    assert passing is False

    # (b) a reported billing period with served answers.
    await conn.execute(
        """
        INSERT INTO billing_usage (
            tenant_id, period_start, period_end, served_answer_count, stripe_usage_record_id
        ) VALUES ($1, $2, $3, 5, 'mbur_test')
        """,
        tenant_id,
        now - timedelta(days=30),
        now,
    )

    # (c) the retention_purged audit row (needs the sentinel, which clean_tables restores).
    await conn.execute(
        """
        INSERT INTO audit_entries (
            audit_id, tenant_id, actor_user_id, actor_role, action, resource_type,
            resource_id, details
        ) VALUES ('aud_c8', 'tn_platform', 'usr_system', 'system', 'retention_purged',
                  'raw_sensitive_logs', 'retention_sweep', '{"deleted_count": 0}'::jsonb)
        """
    )

    _name, value, _thr, passing = await dashboard.criterion_8_operational_basics(conn)
    assert value == "trace=Y bill=Y ret=Y"
    assert passing is True


# ---------------------------------------------------------------------------
# Criterion 6 — founder signoff (audit-row-gated; validates the jsonb cardinality guard).
# ---------------------------------------------------------------------------
async def test_criterion_6_requires_valid_owner_signoff(conn) -> None:
    # No row yet -> not passing, no crash.
    _name, value, _thr, passing = await dashboard.criterion_6_founder_review_pass(conn)
    assert passing is False

    # An owner with a fully-formed signoff (>=20 runs, >=3 categories) -> passes.
    await conn.execute(
        """
        INSERT INTO users (user_id, clerk_user_id, tenant_id, role, status)
        VALUES ('usr_owner', 'clerk_owner', 'tn_test', 'owner', 'active')
        ON CONFLICT (user_id) DO NOTHING
        """
    )
    reviewed = "[" + ",".join(f'"run_{i}"' for i in range(20)) + "]"
    cats = '["pastoral_advice","canonical_dispute","political"]'
    await conn.execute(
        f"""
        INSERT INTO audit_entries (
            audit_id, tenant_id, actor_user_id, actor_role, action, resource_type,
            resource_id, details
        ) VALUES ('aud_signoff', 'tn_test', 'usr_owner', 'owner', 'founder_phase2_signoff',
                  'tenant', 'tn_test',
                  '{{"reviewedRunIds": {reviewed}, "sensitivityCategoriesCovered": {cats}}}'::jsonb)
        """
    )
    _name, _value, _thr, passing = await dashboard.criterion_6_founder_review_pass(conn)
    assert passing is True
