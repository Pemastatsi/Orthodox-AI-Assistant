"""Reusable retrieval-eval orchestration: harness -> metrics -> baseline -> `RetrievalEvalRun`.

This is the missing bridge between the offline harness (`harness.py`) and the operational loop
(persist -> attach -> certify). It lives beside the harness so it can ``import app.*`` cleanly
(``app`` must never import ``tests``), and it is intentionally **DB-free**: ``run_eval`` builds and
returns a `RetrievalEvalRun` but does **not** write it — persistence is the caller's job
(`RetrievalEvalRunRepository.insert`, invoked from the owner-gated CLI). That keeps the whole
orchestration unit-testable offline with the lexical-hashing harness, at zero API/DB cost.

The same ``run_eval`` runs against either harness:
  * the **offline** harness (`build_offline_harness`) — free + deterministic; used by CI + tests;
  * a **live** harness (`build_live_harness`) — a real embedding route over a backfilled Qdrant
    collection, used only by the founder-gated certification run.

Only the deterministic retrieval metrics run by default. The paid Ragas-style LLM judge stays gated
behind ``judge_enabled`` **and** `judge.judge_metrics_enabled()` (the `RETRIEVAL_EVAL_RUN_JUDGE` env
flag + an installed `deepeval`); it never runs in CI.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import ulid
from app.adapters.providers.openai_provider import OpenAIProvider
from app.adapters.sparse.bm25_embedder import Bm25SparseEmbedder
from app.adapters.vector_store.qdrant_store import QdrantStore
from app.core.auth import make_dev_principal
from app.core.config import Settings
from app.domain.models.model_route import ModelRoute
from app.domain.models.retrieval_eval_run import (
    RetrievalEvalPurpose,
    RetrievalEvalRegression,
    RetrievalEvalRun,
)
from app.domain.services.retriever import Retriever

from tests.retrieval_eval.baselines import load_baseline
from tests.retrieval_eval.harness import (
    ConfigLabel,
    GoldSet,
    RetrievalHarness,
)
from tests.retrieval_eval.judge import (
    JudgeCase,
    judge_metrics_enabled,
    run_judge_metrics,
)
from tests.retrieval_eval.metrics import aggregate_metrics, compare_to_baseline

GOLD_SETS_DIR = Path(__file__).parent / "gold_sets"


def resolve_gold_set_path(spec: str, *, gold_sets_dir: Path | None = None) -> Path:
    """Resolve a ``<tenant_id>/<version>`` spec to its gold-set JSON path.

    e.g. ``tenant_smoke/2026-05-29.1`` -> ``gold_sets/tenant_smoke/2026-05-29.1.json``.
    """
    if "/" not in spec:
        raise ValueError(
            f"gold-set spec must be '<tenant_id>/<version>', got {spec!r}"
        )
    tenant_id, version = spec.split("/", 1)
    return (gold_sets_dir or GOLD_SETS_DIR) / tenant_id / f"{version}.json"


async def run_eval(
    *,
    route_id: str,
    purpose: RetrievalEvalPurpose,
    config: ConfigLabel,
    gold_set: GoldSet,
    harness: RetrievalHarness,
    initiated_by: str,
    judge_enabled: bool = False,
    judge_cases: Sequence[JudgeCase] | None = None,
    judge_model: object | None = None,
    baselines_dir: Path | None = None,
) -> RetrievalEvalRun:
    """Run the injected harness, score it, compare to the pinned baseline, and build a run model.

    Returns a `RetrievalEvalRun` with no side effects (no DB write, no baseline write). The caller
    persists it (`--persist`) and, on a passing first run, establishes the baseline (`--attach` /
    owner action). ``judge_cases``/``judge_model`` are the deferred founder-gated judge inputs
    (composed A5 answers + a certified `retrieval_eval_judge` route); they are consulted only when
    ``judge_enabled`` and the judge gate is open, so CI never touches them.
    """
    started = datetime.now(UTC)
    results = await harness.run(gold_set, config=config)
    scores = aggregate_metrics(results)

    judge_applied = False
    if judge_enabled and judge_metrics_enabled():
        if judge_cases is None or judge_model is None:
            raise RuntimeError(
                "LLM-judge metrics are enabled but no judge_cases/judge_model were supplied. "
                "The judge path needs A5-composed answers and a certified retrieval_eval_judge "
                "route (retrieval-eval-suite.md §Answer Quality Metrics) — a founder-/budget-gated "
                "step, off by default."
            )
        scores = {**scores, **run_judge_metrics(judge_cases, judge_model=judge_model)}
        judge_applied = True

    baseline = load_baseline(
        gold_set.tenant_id, gold_set.version, baselines_dir=baselines_dir
    )
    comparison = compare_to_baseline(scores, baseline)
    regressions = [
        RetrievalEvalRegression(
            metric=r.metric, baseline=r.baseline, observed=r.observed
        )
        for r in comparison.regressions
    ] or None

    return RetrievalEvalRun(
        retrieval_eval_run_id=f"reval_{ulid.new()!s}",
        route_id=route_id,
        purpose=purpose,
        config_label=config,
        gold_set_tenant_id=gold_set.tenant_id,
        gold_set_version=gold_set.version,
        case_count=len(results),
        scores=scores,
        passed=comparison.passed,
        is_first_run=comparison.is_first_run,
        judge_applied=judge_applied,
        regressions=regressions,
        initiated_by=initiated_by,
        started_at=started,
        finished_at=datetime.now(UTC),
    )


def build_live_harness(
    *,
    route: ModelRoute,
    settings: Settings,
    collection: str,
    tenant_id: str,
    role: str = "scholar",
) -> RetrievalHarness:
    """Assemble a real A3 harness for a candidate embedding route over a backfilled Qdrant
    collection — the only path that issues paid embedding calls + real Qdrant I/O, used by the
    founder-gated certification run (never by CI).

    The **openai** candidate (`text-embedding-3-large`) is runnable today. The **bge** candidate
    (BGE-M3) raises until its heavy runtime dependency is approved (a deferred, founder-gated
    decision). Construction makes **no** network call — I/O only happens when `.run()` is later
    awaited, which CI never does. ``collection`` targets the candidate's dual-index backfill
    collection (via the new `QdrantStore(collection=…)` option); ``tenant_id`` scopes the
    retrieval principal to the tenant whose corpus was backfilled.
    """
    if route.provider == "bge":
        raise NotImplementedError(
            "The bge candidate (BGE-M3) is not runnable yet: its runtime dependency "
            "(FlagEmbedding / sentence-transformers, ~2.3GB, or a hosted route) is a deferred, "
            "founder-/budget-gated decision. Run the openai candidate, or land the bge dep first."
        )
    if route.provider != "openai":
        raise ValueError(
            f"build_live_harness supports the openai/bge embedding candidates; "
            f"got provider={route.provider!r} for {route.route_id}"
        )

    provider = OpenAIProvider(settings=settings, model=route.model)
    store = QdrantStore(
        embedding_dimension=provider.embedding_dimension,
        settings=settings,
        collection=collection,
    )
    retriever = Retriever(
        embedding_provider=provider,
        vector_store=store,
        sparse_embedder=Bm25SparseEmbedder(),
        embedding_route_id=route.route_id,
    )
    principal = make_dev_principal(tenant_id=tenant_id, role=role, user_id="usr_founder")
    return RetrievalHarness(retriever=retriever, principal=principal)


__all__ = [
    "GOLD_SETS_DIR",
    "build_live_harness",
    "resolve_gold_set_path",
    "run_eval",
]
