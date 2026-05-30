"""Pure certification-gate decision for model routes.

The certification rules (ADR-0004 + `docs/contracts/retrieval-eval-suite.md`) are kept here as a
**DB-free pure function** so they can be unit-tested in CI, where no Postgres runs. The endpoint and
repository (`app/api/v1/admin.py`, `model_route_repository.py`) supply the loaded route and the
gate-run pass flags; this module decides whether certification is allowed.

Gates:
  * Every route requires a linked, passing safety-suite run (ADR-0004).
  * Routes with `purpose IN ('embedding','rerank')` additionally require a linked, passing
    retrieval-eval run (retrieval-eval-suite.md — "the second of two binding gates").
  * A route that is already certified or deprecated cannot be (re-)certified here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.model_route import ModelRoute

# Purposes that additionally require the retrieval-eval gate.
RETRIEVAL_EVAL_PURPOSES = frozenset({"embedding", "rerank"})


@dataclass(frozen=True)
class CertificationDecision:
    """Outcome of the gate check. ``reason`` is set (for a 409 response) only when not allowed."""

    allowed: bool
    reason: str | None = None


def requires_retrieval_eval_gate(route: ModelRoute) -> bool:
    return route.purpose in RETRIEVAL_EVAL_PURPOSES


def evaluate_certification(
    route: ModelRoute,
    *,
    safety_passed: bool,
    retrieval_eval_passed: bool | None,
) -> CertificationDecision:
    """Decide whether ``route`` may be certified.

    ``retrieval_eval_passed`` may be ``None`` when the route's purpose has no retrieval-eval gate;
    it is only consulted for embedding/rerank routes.
    """
    if route.certification_status == "certified":
        return CertificationDecision(False, "route is already certified")
    if route.certification_status == "deprecated":
        return CertificationDecision(False, "a deprecated route cannot be certified")
    if route.safety_suite_run_id is None or not safety_passed:
        return CertificationDecision(
            False, "no passing safety-suite run is linked (ADR-0004 gate)"
        )
    if requires_retrieval_eval_gate(route) and (
        route.retrieval_eval_run_id is None or not retrieval_eval_passed
    ):
        return CertificationDecision(
            False,
            "no passing retrieval-eval run is linked "
            "(retrieval-eval-suite.md gate for embedding/rerank routes)",
        )
    return CertificationDecision(True)


__all__ = [
    "RETRIEVAL_EVAL_PURPOSES",
    "CertificationDecision",
    "evaluate_certification",
    "requires_retrieval_eval_gate",
]
