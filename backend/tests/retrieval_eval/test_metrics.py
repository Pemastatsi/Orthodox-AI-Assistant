"""Known-answer unit tests for the deterministic retrieval metrics.

Every expected value here is hand-computed from the definitions in
`docs/contracts/retrieval-eval-suite.md` §Metrics. These are the rigorous tests; the
end-to-end `test_eval_runs.py` only smoke-tests the plumbing.
"""

from __future__ import annotations

import math

import pytest

from tests.retrieval_eval.metrics import (
    CaseResult,
    aggregate_metrics,
    compare_to_baseline,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


class TestRecallAtK:
    def test_hit_in_top_k(self) -> None:
        assert recall_at_k(["a", "b", "c", "d"], ["c"], k=6) == 1.0

    def test_miss(self) -> None:
        assert recall_at_k(["a", "b", "c", "d"], ["z"], k=6) == 0.0

    def test_relevant_below_cutoff_is_a_miss(self) -> None:
        # "c" is at rank 3 but K=2 → not retrieved.
        assert recall_at_k(["a", "b", "c"], ["c"], k=2) == 0.0

    def test_relevant_at_cutoff_boundary(self) -> None:
        assert recall_at_k(["a", "b", "c"], ["b"], k=2) == 1.0

    def test_any_sufficient_chunk_counts(self) -> None:
        assert recall_at_k(["a", "b"], ["z", "b"], k=6) == 1.0


class TestPrecisionAtK:
    def test_half_relevant(self) -> None:
        assert precision_at_k(["a", "b", "c", "d"], ["a", "c"], k=4) == pytest.approx(0.5)

    def test_divides_by_k_not_by_retrieved_count(self) -> None:
        # Only 2 retrieved, 1 relevant, but K=6 → 1/6 (the contract divides by K).
        assert precision_at_k(["a", "b"], ["a", "c"], k=6) == pytest.approx(1 / 6)

    def test_k_zero(self) -> None:
        assert precision_at_k(["a"], ["a"], k=0) == 0.0

    def test_no_hits(self) -> None:
        assert precision_at_k(["x", "y"], ["a"], k=6) == 0.0


class TestMRR:
    def test_first_rank(self) -> None:
        assert mrr(["a", "b", "c"], ["a"]) == 1.0

    def test_second_rank(self) -> None:
        assert mrr(["a", "b", "c"], ["b"]) == pytest.approx(0.5)

    def test_no_match(self) -> None:
        assert mrr(["a", "b", "c"], ["z"]) == 0.0

    def test_earliest_of_several_sufficient(self) -> None:
        assert mrr(["x", "y", "a", "b"], ["a", "b"]) == pytest.approx(1 / 3)


class TestNDCGAtK:
    def test_single_relevant_at_top_is_perfect(self) -> None:
        assert ndcg_at_k(["a", "b", "c"], ["a"], k=6) == pytest.approx(1.0)

    def test_single_relevant_at_rank_2(self) -> None:
        # dcg = 1/log2(3); idcg = 1/log2(2) = 1.0
        expected = (1.0 / math.log2(3)) / 1.0
        assert ndcg_at_k(["b", "a", "c"], ["a"], k=6) == pytest.approx(expected)

    def test_all_relevant_in_order_is_perfect(self) -> None:
        assert ndcg_at_k(["a", "b"], ["a", "b"], k=6) == pytest.approx(1.0)

    def test_no_relevant_chunks_defined(self) -> None:
        assert ndcg_at_k(["a", "b"], [], k=6) == 0.0

    def test_relevant_below_cutoff(self) -> None:
        assert ndcg_at_k(["x", "y"], ["a"], k=6) == 0.0


class TestAggregate:
    def test_empty_cases(self) -> None:
        assert aggregate_metrics([]) == {}

    def test_means_across_two_cases(self) -> None:
        cases = [
            CaseResult("RE-1", ["a", "b"], ["a"], ["a"]),
            CaseResult("RE-2", ["x", "y"], ["z"], ["z"]),
        ]
        scores = aggregate_metrics(cases, ks=(6,))
        assert scores["recall_at_6"] == pytest.approx(0.5)  # 1 + 0 / 2
        assert scores["mrr"] == pytest.approx(0.5)  # 1.0 + 0.0 / 2
        assert scores["precision_at_6"] == pytest.approx((1 / 6 + 0) / 2)
        # case1 ndcg = 1.0 (a at top), case2 = 0.0 → mean 0.5
        assert scores["ndcg_at_6"] == pytest.approx(0.5)

    def test_emits_one_entry_per_k_plus_single_mrr(self) -> None:
        cases = [CaseResult("RE-1", ["a"], ["a"], ["a"])]
        scores = aggregate_metrics(cases, ks=(6, 12, 20))
        assert set(scores) == {
            "recall_at_6", "precision_at_6", "ndcg_at_6",
            "recall_at_12", "precision_at_12", "ndcg_at_12",
            "recall_at_20", "precision_at_20", "ndcg_at_20",
            "mrr",
        }


class TestBaselineComparison:
    def test_first_run_has_no_baseline(self) -> None:
        result = compare_to_baseline({"recall_at_6": 0.8}, baseline=None)
        assert result.passed is True
        assert result.is_first_run is True

    def test_pass_when_at_or_above_baseline(self) -> None:
        result = compare_to_baseline(
            {"recall_at_6": 0.83}, baseline={"recall_at_6": 0.80}
        )
        assert result.passed is True
        assert result.regressions == []

    def test_drop_within_epsilon_passes(self) -> None:
        # 0.78 >= 0.80 - 0.02 → exactly on the boundary, passes.
        result = compare_to_baseline(
            {"recall_at_6": 0.78}, baseline={"recall_at_6": 0.80}, epsilon=0.02
        )
        assert result.passed is True

    def test_drop_beyond_epsilon_fails(self) -> None:
        result = compare_to_baseline(
            {"recall_at_6": 0.77}, baseline={"recall_at_6": 0.80}, epsilon=0.02
        )
        assert result.passed is False
        assert len(result.regressions) == 1
        reg = result.regressions[0]
        assert reg.metric == "recall_at_6"
        assert reg.drop == pytest.approx(0.03)

    def test_metric_only_in_scores_is_not_gated(self) -> None:
        # A metric present in the new scores but absent from the baseline is ignored
        # (versions aren't commensurable); only baseline metrics are checked.
        result = compare_to_baseline(
            {"recall_at_6": 0.9, "ndcg_at_6": 0.1},
            baseline={"recall_at_6": 0.8},
        )
        assert result.passed is True
        assert result.regressions == []

    def test_missing_observed_metric_treated_as_zero(self) -> None:
        result = compare_to_baseline({}, baseline={"recall_at_6": 0.80})
        assert result.passed is False
        assert result.regressions[0].observed == 0.0
