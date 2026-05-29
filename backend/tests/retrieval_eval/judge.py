"""Ragas-style LLM-judge answer-quality metrics (PAID, GATED).

Implements §Metrics → "Answer Quality Metrics (Ragas-style LLM judge)" of
`docs/contracts/retrieval-eval-suite.md` via DeepEval (REC-019), routed through our internal
``retrieval_eval_judge`` `ModelRoute` rather than DeepEval's default OpenAI endpoint.

This path is **deferred** (the `deepeval` dependency is not installed yet). To keep the suite
importable and the default CI path free + offline, `deepeval` is imported **lazily** inside the
gated functions, and the whole path is skipped unless BOTH:

* the opt-in env var ``RETRIEVAL_EVAL_RUN_JUDGE`` is truthy, AND
* ``deepeval`` is importable.

When activated, DeepEval cloud telemetry/login stays disabled — we never run ``deepeval login`` and
never set ``CONFIDENT_API_KEY`` (gold sets and chunk text must not leave the private remote). Judge
calls submit through the Anthropic Batch API on the certified judge route (REC-020); Batch mode is
NEVER used on the user-facing answer path.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass

JUDGE_OPT_IN_ENV = "RETRIEVAL_EVAL_RUN_JUDGE"

# Judge metric names, aligned with the contract's table and stored in retrieval_eval_runs.scores.
JUDGE_METRICS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)


@dataclass(frozen=True)
class JudgeCase:
    """One case for the LLM judge. Only built for cases where retrieval succeeded (Recall@6 = 1)."""

    case_id: str
    query: str
    answer: str
    retrieved_contexts: list[str]
    expected_contexts: list[str]


def judge_metrics_enabled() -> bool:
    """True only when the opt-in env var is set AND `deepeval` is importable. False by default."""
    if os.environ.get(JUDGE_OPT_IN_ENV, "").strip().lower() not in {"1", "true", "yes"}:
        return False
    try:
        import deepeval  # noqa: F401  (lazy availability probe)
    except ImportError:
        return False
    return True


def _disable_deepeval_telemetry() -> None:
    # Defensive: opt out of DeepEval's cloud telemetry before importing it.
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
    os.environ.setdefault("ERROR_REPORTING", "NO")


def build_internal_judge_model(
    *, route_id: str, generate_text: Callable[[str], str]
) -> object:
    """Build a DeepEval ``DeepEvalBaseLLM`` that routes generation through our internal judge route.

    ``generate_text`` is the caller's bound LLM-provider call (already pinned to the certified
    ``retrieval_eval_judge`` route). Lazily imports DeepEval; raises if unavailable.
    """
    if not judge_metrics_enabled():
        raise RuntimeError(
            "Judge path disabled: set RETRIEVAL_EVAL_RUN_JUDGE=1 and install `deepeval`."
        )
    _disable_deepeval_telemetry()
    from deepeval.models import DeepEvalBaseLLM  # noqa: PLC0415 (lazy, gated)

    class InternalJudgeModel(DeepEvalBaseLLM):  # type: ignore[misc]
        def load_model(self) -> object:
            return self

        def generate(self, prompt: str) -> str:
            return generate_text(prompt)

        async def a_generate(self, prompt: str) -> str:
            return generate_text(prompt)

        def get_model_name(self) -> str:
            return f"internal:{route_id}"

    return InternalJudgeModel()


def run_judge_metrics(
    cases: Sequence[JudgeCase], *, judge_model: object
) -> dict[str, float]:
    """Mean of the four DeepEval RAGAS metrics across cases (gated; lazily imports DeepEval).

    Returns an empty dict for no cases. Raises ``RuntimeError`` if the judge path is disabled.
    """
    if not judge_metrics_enabled():
        raise RuntimeError(
            "Judge path disabled: set RETRIEVAL_EVAL_RUN_JUDGE=1 and install `deepeval`."
        )
    if not cases:
        return {}
    _disable_deepeval_telemetry()
    from deepeval.metrics import (  # noqa: PLC0415 (lazy, gated)
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
    )
    from deepeval.test_case import LLMTestCase  # noqa: PLC0415

    metric_factories = {
        "faithfulness": lambda: FaithfulnessMetric(model=judge_model),
        "answer_relevancy": lambda: AnswerRelevancyMetric(model=judge_model),
        "context_precision": lambda: ContextualPrecisionMetric(model=judge_model),
        "context_recall": lambda: ContextualRecallMetric(model=judge_model),
    }
    totals: dict[str, float] = {name: 0.0 for name in metric_factories}
    for case in cases:
        tc = LLMTestCase(
            input=case.query,
            actual_output=case.answer,
            retrieval_context=case.retrieved_contexts,
            expected_output=" ".join(case.expected_contexts),
        )
        for name, factory in metric_factories.items():
            metric = factory()
            metric.measure(tc)
            totals[name] += float(metric.score or 0.0)
    return {name: total / len(cases) for name, total in totals.items()}


__all__ = [
    "JUDGE_METRICS",
    "JUDGE_OPT_IN_ENV",
    "JudgeCase",
    "build_internal_judge_model",
    "judge_metrics_enabled",
    "run_judge_metrics",
]
