"""Deterministic retrieval metrics for the retrieval-eval suite.

These implement the §Metrics → "Retrieval Metrics (deterministic, no LLM judge)" table of
`docs/contracts/retrieval-eval-suite.md` exactly. They are pure functions over chunk-ID lists:
no network, no LLM, no API cost. They run offline in CI and are the **primary gate** for
`purpose IN ('embedding', 'rerank')` route certification.

Definitions (verbatim from the contract):

* ``recall_at_k`` — per case, ``1`` if *any* chunk in ``minimallySufficientChunkIds`` appears in
  the top-K retrieved IDs, else ``0``; averaged across cases.
* ``precision_at_k`` — per case, ``|retrieved_top_k ∩ expectedChunkIds| / k``; averaged.
* ``mrr`` — reciprocal rank of the first chunk in ``minimallySufficientChunkIds`` to appear in
  the ranking; ``0`` if none appears; averaged.
* ``ndcg_at_k`` — standard nDCG with binary relevance drawn from ``expectedChunkIds``; averaged.

All metrics are reported in ``[0.0, 1.0]`` (the contract forbids the Sialtsis 1–5 scale).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

# K values per the contract: 6 is the production retrieval ceiling and the primary gate; 12 and
# 20 diagnose whether the right candidates merely sit deeper in the ranking.
DEFAULT_KS: tuple[int, ...] = (6, 12, 20)
PRIMARY_K: int = 6

# Default regression tolerance (two percentage points) from the contract's pass/fail rule.
DEFAULT_EPSILON: float = 0.02


@dataclass(frozen=True)
class CaseResult:
    """One gold-set case after retrieval has run.

    ``retrieved_ids`` is the ranked list of chunk IDs A3 returned (best first). The two gold
    fields are copied from the gold-set case.
    """

    case_id: str
    retrieved_ids: list[str]
    expected_ids: list[str]
    minimally_sufficient_ids: list[str]


def recall_at_k(
    retrieved_ids: Sequence[str], minimally_sufficient_ids: Iterable[str], k: int
) -> float:
    """1.0 if any minimally-sufficient chunk is in the top-K, else 0.0 (per-case, binary)."""
    top_k = set(retrieved_ids[:k])
    return 1.0 if any(cid in top_k for cid in minimally_sufficient_ids) else 0.0


def precision_at_k(
    retrieved_ids: Sequence[str], expected_ids: Iterable[str], k: int
) -> float:
    """``|retrieved_top_k ∩ expectedChunkIds| / k`` — divides by K, per the contract."""
    if k <= 0:
        return 0.0
    expected = set(expected_ids)
    hits = sum(1 for cid in retrieved_ids[:k] if cid in expected)
    return hits / k


def mrr(retrieved_ids: Sequence[str], minimally_sufficient_ids: Iterable[str]) -> float:
    """Reciprocal rank of the first minimally-sufficient chunk; 0.0 if none appears."""
    sufficient = set(minimally_sufficient_ids)
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in sufficient:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(
    retrieved_ids: Sequence[str], expected_ids: Iterable[str], k: int
) -> float:
    """Standard nDCG@K with binary relevance from ``expectedChunkIds``.

    DCG = Σ rel_i / log2(i + 1) over ranks i = 1..K; IDCG is the DCG of the ideal ordering
    (all relevant chunks first). Returns 0.0 when no relevant chunk exists.
    """
    expected = set(expected_ids)
    if not expected or k <= 0:
        return 0.0
    dcg = 0.0
    for i, cid in enumerate(retrieved_ids[:k], start=1):
        if cid in expected:
            dcg += 1.0 / math.log2(i + 1)
    ideal_hits = min(len(expected), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate_metrics(
    cases: Sequence[CaseResult], ks: Sequence[int] = DEFAULT_KS
) -> dict[str, float]:
    """Mean of each metric across cases, keyed ``<metric>_at_<k>`` (plus a K-independent ``mrr``).

    Returns an empty dict for an empty case list. Keys are stable so they can be compared to a
    pinned ``baselines/<tenant_id>.json`` row and stored in ``retrieval_eval_runs``.
    """
    scores: dict[str, float] = {}
    if not cases:
        return scores
    for k in ks:
        scores[f"recall_at_{k}"] = _mean(
            [recall_at_k(c.retrieved_ids, c.minimally_sufficient_ids, k) for c in cases]
        )
        scores[f"precision_at_{k}"] = _mean(
            [precision_at_k(c.retrieved_ids, c.expected_ids, k) for c in cases]
        )
        scores[f"ndcg_at_{k}"] = _mean(
            [ndcg_at_k(c.retrieved_ids, c.expected_ids, k) for c in cases]
        )
    scores["mrr"] = _mean(
        [mrr(c.retrieved_ids, c.minimally_sufficient_ids) for c in cases]
    )
    return scores


@dataclass(frozen=True)
class Regression:
    metric: str
    baseline: float
    observed: float

    @property
    def drop(self) -> float:
        return self.baseline - self.observed


@dataclass(frozen=True)
class BaselineComparison:
    """Result of the contract's pass/fail rule against a pinned baseline."""

    passed: bool
    regressions: list[Regression] = field(default_factory=list)
    is_first_run: bool = False


def compare_to_baseline(
    scores: dict[str, float],
    baseline: dict[str, float] | None,
    epsilon: float = DEFAULT_EPSILON,
) -> BaselineComparison:
    """Apply the contract's pass/fail rule.

    * No baseline (first run for a gold-set version) → pass; the caller establishes the baseline
      only if the safety suite also passes (owner-gated, done outside this pure function).
    * Otherwise: for every metric **present in the baseline**, the new score must be
      ``>= baseline - epsilon``. Any larger drop flips the run to fail. Metrics absent from the
      baseline are not gated (versions are not comparable; see the contract's Forbidden Patterns).
    """
    if not baseline:
        return BaselineComparison(passed=True, is_first_run=True)
    regressions = [
        Regression(metric=metric, baseline=base, observed=scores.get(metric, 0.0))
        for metric, base in baseline.items()
        if scores.get(metric, 0.0) < base - epsilon
    ]
    return BaselineComparison(passed=not regressions, regressions=regressions)


__all__ = [
    "DEFAULT_EPSILON",
    "DEFAULT_KS",
    "PRIMARY_K",
    "BaselineComparison",
    "CaseResult",
    "Regression",
    "aggregate_metrics",
    "compare_to_baseline",
    "mrr",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
]
