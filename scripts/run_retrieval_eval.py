#!/usr/bin/env python3
"""Operator CLI for the retrieval-eval suite (T-009 Phase-A, operationalization).

Closes the loop for the founder: *run* a candidate embedding route's retrieval-eval ->
*persist* the result -> *attach* a passing run to the route -> *certify* (the existing
`PATCH /api/v1/admin/model-routes/{routeId}/certify` endpoint). Mirrors the founder-operated
`scripts/exit_criteria_dashboard.py` precedent (a CLI, not an endpoint/arq task). The orchestration
itself lives in the reusable `tests/retrieval_eval/runner.py`, so an endpoint can wrap it later.

Run it from `backend/` so the project venv + imports resolve:

    uv run python ../scripts/run_retrieval_eval.py \
        --offline \
        --gold-set tenant_smoke/2026-05-29.1 \
        --route-id embedding_openai_large@2026-05-29.1

Cost/safety posture:
  * Default + `--offline`: free, deterministic, no network, no DB — prints a metrics report.
  * `--persist`: writes one `retrieval_eval_runs` row (needs Postgres).
  * `--attach`: owner action — links the passing run to the route's second cert gate (implies
    `--persist`; needs Postgres). `--safety-run-id` additionally links the safety gate.
  * `--establish-baseline`: owner action — records the passing scores as the version's baseline.
  * `--judge`: the paid Ragas-style LLM-judge path; stays gated behind RETRIEVAL_EVAL_RUN_JUDGE +
    an installed `deepeval` (off by default), so this flag is a no-op until the founder enables it.
  * Live run (omit `--offline`): a real embedding route over a backfilled Qdrant collection — paid
    embedding calls + real Qdrant; founder-/infra-gated. The bge candidate errors until its dep
    lands.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Run from backend/ via `uv run python ../scripts/...`; the script lives at repo-root scripts/, so
# put backend/ on the path to import both `app.*` and the `tests.retrieval_eval.*` orchestration.
_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.domain.models.retrieval_eval_run import RetrievalEvalRun  # noqa: E402
from app.domain.repositories._base import (  # noqa: E402
    dispose_engine,
    init_engine,
    session_scope,
)
from app.domain.repositories.model_route_repository import (  # noqa: E402
    ModelRouteRepository,
)
from app.domain.repositories.retrieval_eval_run_repository import (  # noqa: E402
    RetrievalEvalRunRepository,
)

from tests.retrieval_eval.baselines import (  # noqa: E402
    load_baseline,
    write_baseline,
)
from tests.retrieval_eval.harness import (  # noqa: E402
    build_offline_harness,
    load_gold_set,
)
from tests.retrieval_eval.metrics import DEFAULT_EPSILON  # noqa: E402
from tests.retrieval_eval.runner import (  # noqa: E402
    build_live_harness,
    resolve_gold_set_path,
    run_eval,
)


def _infer_purpose(route_id: str) -> str:
    """rerank routes carry 'rerank' in their id; everything else here is an embedding route."""
    return "rerank" if "rerank" in route_id else "embedding"


def _print_report(run: RetrievalEvalRun, baseline: dict[str, float] | None) -> None:
    print()
    print(f"Retrieval-Eval Run — {run.route_id}")
    print("=" * 72)
    print(
        f"gold set : {run.gold_set_tenant_id}/{run.gold_set_version}"
        f"   config={run.config_label}   cases={run.case_count}"
    )
    print(
        "baseline : "
        + ("none — first run for this version" if run.is_first_run else "pinned")
        + ("   (judge metrics included)" if run.judge_applied else "")
    )
    print("-" * 72)
    print(f"{'metric':<22}{'observed':>10}{'baseline':>10}{'delta':>10}  {'gate'}")
    print("-" * 72)
    for metric in sorted(run.scores):
        observed = run.scores[metric]
        base = baseline.get(metric) if baseline else None
        if base is None:
            base_str, delta_str, gate = "—", "—", "first-run"
        else:
            base_str = f"{base:.4f}"
            delta_str = f"{observed - base:+.4f}"
            gate = "PASS" if observed >= base - DEFAULT_EPSILON else "FAIL"
        print(f"{metric:<22}{observed:>10.4f}{base_str:>10}{delta_str:>10}  {gate}")
    print("-" * 72)
    if run.passed:
        verdict = "PASS (first run)" if run.is_first_run else "PASS"
    else:
        flagged = ", ".join(r.metric for r in (run.regressions or []))
        verdict = f"FAIL — regressions: {flagged}"
    print(f"Result: {verdict}")
    print(f"run id : {run.retrieval_eval_run_id}")
    print()


async def _build_harness(args: argparse.Namespace, tenant_id: str):
    if args.offline:
        return build_offline_harness(tenant_id=tenant_id)
    # Live run: load the candidate route from the DB and target its backfilled collection.
    settings = get_settings()
    init_engine(settings)
    async with session_scope() as session:
        route = await ModelRouteRepository(session).get(args.route_id)
    if route is None:
        raise SystemExit(
            f"error: route {args.route_id} not found — a live run needs a seeded route "
            f"(or pass --offline)."
        )
    collection = args.collection or f"{settings.qdrant_collection_prefix}_candidate"
    return build_live_harness(
        route=route, settings=settings, collection=collection, tenant_id=tenant_id
    )


async def _amain(args: argparse.Namespace) -> int:
    gold_set = load_gold_set(resolve_gold_set_path(args.gold_set))
    baselines_dir = Path(args.baselines_dir) if args.baselines_dir else None

    harness = await _build_harness(args, gold_set.tenant_id)
    run = await run_eval(
        route_id=args.route_id,
        purpose=_infer_purpose(args.route_id),  # type: ignore[arg-type]
        config=args.config,
        gold_set=gold_set,
        harness=harness,
        judge_enabled=args.judge,
        initiated_by=args.initiated_by,
        baselines_dir=baselines_dir,
    )

    baseline = load_baseline(
        gold_set.tenant_id, gold_set.version, baselines_dir=baselines_dir
    )
    _print_report(run, baseline)

    # --attach implies --persist (the gate pointer is an FK to a persisted run row).
    should_persist = args.persist or args.attach
    needs_db = should_persist or args.attach
    if needs_db:
        init_engine(get_settings())  # idempotent; ensures an engine for the DB writes below
    try:
        if should_persist:
            async with session_scope() as session:
                run_id = await RetrievalEvalRunRepository(session).insert(run)
            print(f"persisted retrieval_eval_runs row: {run_id}")

        if args.attach:
            if not run.passed:
                print("refusing to --attach a failing run (gate would never certify).")
                return 1
            async with session_scope() as session:
                repo = ModelRouteRepository(session)
                await repo.attach_retrieval_eval_run(
                    route_id=args.route_id, run_id=run.retrieval_eval_run_id
                )
                if args.safety_run_id:
                    await repo.attach_safety_suite_run(
                        route_id=args.route_id, run_id=args.safety_run_id
                    )
            print(
                f"attached retrieval-eval run {run.retrieval_eval_run_id} -> "
                f"{args.route_id}"
                + (f" (+ safety run {args.safety_run_id})" if args.safety_run_id else "")
            )
            print(
                "Next (owner): PATCH /api/v1/admin/model-routes/"
                f"{args.route_id}/certify"
            )

        if args.establish_baseline:
            if not run.passed:
                print("refusing to establish a baseline from a failing run.")
                return 1
            path = write_baseline(
                gold_set.tenant_id,
                gold_set.version,
                run.scores,
                established_by=args.initiated_by,
                baselines_dir=baselines_dir,
            )
            print(f"baseline established (owner action): {path}")
    finally:
        if needs_db:
            await dispose_engine()

    return 0 if run.passed else 1


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a candidate route's retrieval-eval; print a metrics report vs. baseline, and "
            "optionally persist / attach (owner) / establish a baseline (owner)."
        )
    )
    parser.add_argument("--route-id", required=True, help="ModelRoute.routeId under test.")
    parser.add_argument(
        "--gold-set",
        required=True,
        metavar="TENANT/VERSION",
        help="Gold-set spec, e.g. tenant_smoke/2026-05-29.1",
    )
    parser.add_argument(
        "--config",
        default="dense_only",
        choices=["dense_only", "hybrid", "hybrid_rerank"],
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use the offline lexical harness (free; default when no live infra).",
    )
    parser.add_argument(
        "--persist", action="store_true", help="Write the run to retrieval_eval_runs (needs DB)."
    )
    parser.add_argument(
        "--attach",
        action="store_true",
        help="Owner: link the passing run to the route's retrieval-eval gate (implies --persist).",
    )
    parser.add_argument(
        "--safety-run-id",
        default=None,
        help="With --attach, also link this passing safety-suite run (owner).",
    )
    parser.add_argument(
        "--establish-baseline",
        action="store_true",
        help="Owner: record this passing run's scores as the version's baseline.",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Enable the paid LLM-judge path (still gated by RETRIEVAL_EVAL_RUN_JUDGE + deepeval).",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Live run only: the backfilled Qdrant collection to target.",
    )
    parser.add_argument(
        "--initiated-by",
        default="usr_founder",
        help="users.user_id recorded as the run initiator / baseline establisher.",
    )
    parser.add_argument(
        "--baselines-dir",
        default=None,
        help="Override the baselines directory (defaults to the package baselines/).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(_parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
