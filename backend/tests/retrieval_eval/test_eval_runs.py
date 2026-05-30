"""End-to-end smoke for the retrieval-eval harness — offline, deterministic, zero API cost.

Rigorous metric correctness lives in `test_metrics.py`; this module validates the *plumbing*:
gold set -> A3 (the real `Retriever` over an offline lexical index of the fixture corpus) ->
deterministic metrics -> a well-formed `RetrievalEvalRun`. The paid LLM-judge path is asserted
to be skipped by default.

This is the pytest entry point the contract's CI job (`retrieval-eval-regression`) runs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

pytest.importorskip("app")

from app.domain.models.retrieval_eval_run import RetrievalEvalRun  # noqa: E402

from tests.retrieval_eval.harness import (  # noqa: E402
    build_offline_harness,
    load_gold_set,
)
from tests.retrieval_eval.judge import judge_metrics_enabled  # noqa: E402
from tests.retrieval_eval.metrics import (  # noqa: E402
    aggregate_metrics,
    compare_to_baseline,
)

_GOLD_SET = Path(__file__).parent / "gold_sets" / "tenant_smoke" / "2026-05-29.1.json"


@pytest.fixture
def gold_set():
    return load_gold_set(_GOLD_SET)


def test_smoke_gold_set_is_well_formed(gold_set) -> None:
    assert gold_set.tenant_id == "tenant_smoke"
    assert gold_set.reviewed_by  # contract: must be non-empty
    assert len(gold_set.cases) >= 1
    for case in gold_set.cases:
        assert case.expected_chunk_ids
        assert set(case.minimally_sufficient_chunk_ids) <= set(case.expected_chunk_ids)


async def test_smoke_gold_set_retrieves_expected_chunks(gold_set) -> None:
    harness = build_offline_harness(tenant_id=gold_set.tenant_id)
    results = await harness.run(gold_set, config="dense_only")
    scores = aggregate_metrics(results)
    # The smoke gold set is lexically distinct, so every target chunk lands in the top-6.
    assert scores["recall_at_6"] == 1.0
    assert scores["mrr"] == 1.0
    assert scores["ndcg_at_6"] == 1.0


@pytest.mark.parametrize("config", ["dense_only", "hybrid", "hybrid_rerank"])
async def test_every_config_runs(gold_set, config) -> None:
    harness = build_offline_harness(tenant_id=gold_set.tenant_id)
    results = await harness.run(gold_set, config=config)
    assert len(results) == len(gold_set.cases)
    assert all(r.retrieved_ids for r in results)


async def test_unapproved_chunk_never_retrieved(gold_set) -> None:
    # The fixture corpus carries a deliberately-unapproved chunk; A3's approved filter must drop it.
    harness = build_offline_harness(tenant_id=gold_set.tenant_id)
    results = await harness.run(gold_set, config="dense_only")
    retrieved = {cid for r in results for cid in r.retrieved_ids}
    assert "chunk-unapproved-001" not in retrieved


async def test_builds_well_formed_first_run(gold_set) -> None:
    harness = build_offline_harness(tenant_id=gold_set.tenant_id)
    started = datetime.now(UTC)
    results = await harness.run(gold_set, config="dense_only")
    scores = aggregate_metrics(results)
    comparison = compare_to_baseline(scores, baseline=None)
    run = RetrievalEvalRun(
        retrieval_eval_run_id="reval_smoke_01",
        route_id="retrieval_eval_offline@2026-05-29.1",
        purpose="embedding",
        config_label="dense_only",
        gold_set_tenant_id=gold_set.tenant_id,
        gold_set_version=gold_set.version,
        case_count=len(results),
        scores=scores,
        passed=comparison.passed,
        is_first_run=comparison.is_first_run,
        judge_applied=False,
        regressions=None,
        initiated_by="usr_ci",
        started_at=started,
        finished_at=datetime.now(UTC),
    )
    assert run.passed is True  # first run for the version: no baseline to regress against
    assert run.is_first_run is True
    assert run.case_count == len(gold_set.cases)
    assert run.model_dump(by_alias=True)["goldSetVersion"] == gold_set.version


async def test_regression_detected_against_inflated_baseline(gold_set) -> None:
    harness = build_offline_harness(tenant_id=gold_set.tenant_id)
    results = await harness.run(gold_set, config="dense_only")
    scores = aggregate_metrics(results)
    # Single-chunk cases cap precision@6 at 1/6; a baseline above that must flag a regression.
    comparison = compare_to_baseline(scores, baseline={"precision_at_6": 0.9})
    assert comparison.passed is False
    assert comparison.regressions[0].metric == "precision_at_6"


def test_judge_path_skipped_by_default() -> None:
    # Paid LLM-judge metrics stay off unless RETRIEVAL_EVAL_RUN_JUDGE=1 and deepeval is installed.
    assert judge_metrics_enabled() is False
