"""Unit tests for the retrieval-eval runner + baseline IO — offline, deterministic, zero cost.

Drives ``run_eval`` with the **offline** lexical harness over the synthetic smoke gold set (the same
path `test_eval_runs.py` exercises) and asserts the orchestration produces a well-formed
`RetrievalEvalRun`: a first-run pass with no baseline, and a flagged regression against an inflated
baseline. No network, no DB, no LLM judge.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("app")

from tests.retrieval_eval.baselines import (  # noqa: E402
    load_baseline,
    write_baseline,
)
from tests.retrieval_eval.harness import (  # noqa: E402
    build_offline_harness,
    load_gold_set,
)
from tests.retrieval_eval.runner import (  # noqa: E402
    resolve_gold_set_path,
    run_eval,
)

_GOLD_SPEC = "tenant_smoke/2026-05-29.1"


@pytest.fixture
def gold_set():
    return load_gold_set(resolve_gold_set_path(_GOLD_SPEC))


def test_resolve_gold_set_path_shape() -> None:
    path = resolve_gold_set_path(_GOLD_SPEC)
    assert path.name == "2026-05-29.1.json"
    assert path.parent.name == "tenant_smoke"
    assert path.exists()


def test_resolve_gold_set_path_rejects_bad_spec() -> None:
    with pytest.raises(ValueError, match="tenant_id.*version"):
        resolve_gold_set_path("no-slash-here")


async def test_run_eval_first_run_passes(gold_set, tmp_path: Path) -> None:
    harness = build_offline_harness(tenant_id=gold_set.tenant_id)
    run = await run_eval(
        route_id="embedding_openai_large@2026-05-29.1",
        purpose="embedding",
        config="dense_only",
        gold_set=gold_set,
        harness=harness,
        initiated_by="usr_ci",
        baselines_dir=tmp_path,  # empty -> no baseline -> first run
    )
    assert run.passed is True
    assert run.is_first_run is True
    assert run.regressions is None
    assert run.judge_applied is False
    assert run.case_count == len(gold_set.cases)
    assert run.route_id == "embedding_openai_large@2026-05-29.1"
    assert run.config_label == "dense_only"
    assert run.retrieval_eval_run_id.startswith("reval_")
    # The smoke gold set is lexically distinct: every target lands in the top-6.
    assert run.scores["recall_at_6"] == 1.0
    assert run.scores["mrr"] == 1.0
    # The wire shape stays camelCase (it is what the repository persists / reads back).
    assert run.model_dump(by_alias=True)["goldSetVersion"] == gold_set.version


async def test_run_eval_regression_flagged_against_inflated_baseline(
    gold_set, tmp_path: Path
) -> None:
    # Single-chunk cases cap precision@6 at 1/6; a baseline above that must flag a regression.
    write_baseline(
        gold_set.tenant_id,
        gold_set.version,
        {"precision_at_6": 0.9},
        established_by="usr_founder",
        baselines_dir=tmp_path,
    )
    harness = build_offline_harness(tenant_id=gold_set.tenant_id)
    run = await run_eval(
        route_id="embedding_openai_large@2026-05-29.1",
        purpose="embedding",
        config="dense_only",
        gold_set=gold_set,
        harness=harness,
        initiated_by="usr_ci",
        baselines_dir=tmp_path,
    )
    assert run.passed is False
    assert run.is_first_run is False
    assert run.regressions is not None
    assert run.regressions[0].metric == "precision_at_6"
    assert run.regressions[0].baseline == 0.9
    assert run.regressions[0].observed < 0.9


async def test_run_eval_judge_off_by_default(gold_set, tmp_path: Path) -> None:
    # Even when asked, the judge stays off unless its gate is open (env + deepeval) — never in CI.
    harness = build_offline_harness(tenant_id=gold_set.tenant_id)
    run = await run_eval(
        route_id="embedding_openai_large@2026-05-29.1",
        purpose="embedding",
        config="dense_only",
        gold_set=gold_set,
        harness=harness,
        initiated_by="usr_ci",
        judge_enabled=True,
        baselines_dir=tmp_path,
    )
    assert run.judge_applied is False
    assert "faithfulness" not in run.scores


def test_baseline_round_trips(tmp_path: Path) -> None:
    assert load_baseline("tenant_smoke", "2026-05-29.1", baselines_dir=tmp_path) is None
    write_baseline(
        "tenant_smoke",
        "2026-05-29.1",
        {"recall_at_6": 1.0, "mrr": 0.83},
        established_by="usr_founder",
        baselines_dir=tmp_path,
    )
    loaded = load_baseline("tenant_smoke", "2026-05-29.1", baselines_dir=tmp_path)
    assert loaded == {"recall_at_6": 1.0, "mrr": 0.83}
    # A different version on the same tenant file is independent (and absent here).
    assert load_baseline("tenant_smoke", "2099-01-01.1", baselines_dir=tmp_path) is None


def test_write_baseline_preserves_other_versions(tmp_path: Path) -> None:
    write_baseline(
        "tenant_smoke", "2026-05-29.1", {"recall_at_6": 1.0},
        established_by="usr_founder", baselines_dir=tmp_path,
    )
    write_baseline(
        "tenant_smoke", "2026-06-01.1", {"recall_at_6": 0.95},
        established_by="usr_founder", baselines_dir=tmp_path,
    )
    assert load_baseline("tenant_smoke", "2026-05-29.1", baselines_dir=tmp_path) == {
        "recall_at_6": 1.0
    }
    assert load_baseline("tenant_smoke", "2026-06-01.1", baselines_dir=tmp_path) == {
        "recall_at_6": 0.95
    }
