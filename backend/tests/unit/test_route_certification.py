"""Unit tests for the route-certification gate decision (DB-free; runs in CI).

These cover the security-critical rules in `app/domain/services/route_certification.py`:
which routes may be promoted to `certified` (ADR-0004 + retrieval-eval-suite.md). The DB wiring
(repository + endpoint) is exercised by the DB-gated integration test, which skips where no
Postgres is reachable — so the gate logic is deliberately isolated here.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.models.model_route import ModelRoute
from app.domain.services.route_certification import (
    RETRIEVAL_EVAL_PURPOSES,
    evaluate_certification,
    requires_retrieval_eval_gate,
)

NOW = datetime(2026, 5, 29, tzinfo=UTC)


def _route(**overrides) -> ModelRoute:
    base = dict(
        route_id="embedding_openai@2026-05-01.1",
        purpose="embedding",
        provider="openai",
        model="text-embedding-3-large",
        prompt_version="embedding_none@2026-05-01.1",
        schema_version="1.0",
        certification_status="experiment",
        created_at=NOW,
        safety_suite_run_id="ssr_1",
        retrieval_eval_run_id="reval_1",
    )
    base.update(overrides)
    return ModelRoute(**base)


class TestRetrievalEvalGate:
    def test_embedding_requires_gate(self) -> None:
        assert requires_retrieval_eval_gate(_route(purpose="embedding")) is True

    def test_rerank_is_a_gated_purpose(self) -> None:
        # 'rerank' is forward-looking: the gate (and retrieval-eval-suite.md) anticipate it, but
        # the RoutePurpose literal does not add it until the reranker phase (ADR-0012), so we
        # assert membership directly rather than build a (not-yet-valid) rerank ModelRoute.
        assert "rerank" in RETRIEVAL_EVAL_PURPOSES

    def test_compose_does_not(self) -> None:
        assert requires_retrieval_eval_gate(_route(purpose="compose")) is False


class TestEvaluateCertification:
    def test_allowed_when_both_gates_pass(self) -> None:
        decision = evaluate_certification(
            _route(), safety_passed=True, retrieval_eval_passed=True
        )
        assert decision.allowed is True
        assert decision.reason is None

    def test_already_certified_rejected(self) -> None:
        decision = evaluate_certification(
            _route(certification_status="certified"),
            safety_passed=True,
            retrieval_eval_passed=True,
        )
        assert decision.allowed is False
        assert "already certified" in decision.reason

    def test_deprecated_rejected(self) -> None:
        decision = evaluate_certification(
            _route(certification_status="deprecated"),
            safety_passed=True,
            retrieval_eval_passed=True,
        )
        assert decision.allowed is False
        assert "deprecated" in decision.reason

    def test_missing_safety_run_rejected(self) -> None:
        decision = evaluate_certification(
            _route(safety_suite_run_id=None),
            safety_passed=False,
            retrieval_eval_passed=True,
        )
        assert decision.allowed is False
        assert "safety" in decision.reason

    def test_failing_safety_run_rejected(self) -> None:
        decision = evaluate_certification(
            _route(), safety_passed=False, retrieval_eval_passed=True
        )
        assert decision.allowed is False
        assert "safety" in decision.reason

    def test_embedding_missing_retrieval_run_rejected(self) -> None:
        decision = evaluate_certification(
            _route(retrieval_eval_run_id=None),
            safety_passed=True,
            retrieval_eval_passed=False,
        )
        assert decision.allowed is False
        assert "retrieval-eval" in decision.reason

    def test_embedding_failing_retrieval_run_rejected(self) -> None:
        decision = evaluate_certification(
            _route(), safety_passed=True, retrieval_eval_passed=False
        )
        assert decision.allowed is False
        assert "retrieval-eval" in decision.reason

    def test_non_embedding_route_ignores_retrieval_gate(self) -> None:
        # A compose route needs only the safety gate; retrieval_eval_passed is None and irrelevant.
        decision = evaluate_certification(
            _route(
                purpose="compose",
                route_id="a5_compose_anthropic@2026-05-01.1",
                retrieval_eval_run_id=None,
            ),
            safety_passed=True,
            retrieval_eval_passed=None,
        )
        assert decision.allowed is True


def test_certify_endpoint_is_registered() -> None:
    # DB-free: importing the app constructs all routes. This also proves the Path(alias="routeId")
    # binding is valid (FastAPI raises at construction otherwise).
    from app.main import app

    matches = [
        route
        for route in app.routes
        if getattr(route, "path", "").endswith("/model-routes/{routeId}/certify")
    ]
    assert matches, "certify route not registered"
    assert "PATCH" in matches[0].methods
