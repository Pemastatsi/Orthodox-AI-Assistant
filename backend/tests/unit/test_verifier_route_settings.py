"""F-08: `ACTIVE_MODEL_ROUTE_VERIFIER` env-var slot wiring.

When the env var is empty, the verifier judge is cleanly disabled and the verifier provider
dependency returns None. Deterministic A6 checks still run.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.api.v1._deps import (
    _reset_query_caches,
    build_verifier,
    get_verifier_provider,
)
from app.core.config import Settings
from app.domain.services.safety_config import load_pastoral_filters

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PASTORAL_PATH = _REPO_ROOT / "config" / "pastoral_filters.yaml"


@pytest.fixture(autouse=True)
def _reset_caches():
    _reset_query_caches()
    yield
    _reset_query_caches()


def test_get_verifier_provider_returns_none_when_route_empty() -> None:
    """F-08: empty `ACTIVE_MODEL_ROUTE_VERIFIER` returns None — judge cleanly disabled."""
    settings = Settings(active_model_route_verifier="")
    assert get_verifier_provider(settings=settings) is None


def test_get_verifier_provider_returns_provider_when_route_set() -> None:
    """When a route is configured, the dependency returns an LLMProvider instance."""
    settings = Settings(
        active_model_route_verifier="verifier_judge_anthropic@2026-05-01.1",
        anthropic_api_key="REPLACE_ME",
    )
    provider = get_verifier_provider(settings=settings)
    assert provider is not None
    # Sanity: the protocol attributes we rely on are present.
    assert provider.name == "anthropic"


def test_build_verifier_with_empty_route_yields_no_judge() -> None:
    """Verifier instances built with judge_route_id='' must not call any provider."""
    pastoral = load_pastoral_filters(_PASTORAL_PATH)
    settings = Settings(active_model_route_verifier="")
    verifier = build_verifier(
        pastoral_config=pastoral, settings=settings, judge_provider=None
    )
    # Private attr inspection is fine for a focused unit test of wiring.
    assert verifier._judge is None  # type: ignore[attr-defined]


def test_build_verifier_with_route_uses_judge_provider() -> None:
    pastoral = load_pastoral_filters(_PASTORAL_PATH)
    settings = Settings(
        active_model_route_verifier="verifier_judge_anthropic@2026-05-01.1"
    )

    class SentinelJudge:
        name = "sentinel"

    verifier = build_verifier(
        pastoral_config=pastoral,
        settings=settings,
        judge_provider=SentinelJudge(),  # type: ignore[arg-type]
    )
    assert verifier._judge is not None  # type: ignore[attr-defined]
