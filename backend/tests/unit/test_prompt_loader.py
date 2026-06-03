"""GS-3 runtime prompt loader + builder-wiring tests (needs the backend env).

Confirms the A1/A2 and A5 builders serve the exact text in the `/prompts` registry that
their active route advertises — the semantic counterpart to the dep-free no-embedded-prompts
gate in ``tests/prompts/test_prompt_registry.py``.
"""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.domain.agents import verifier
from app.domain.prompts import composer_a5, query_analyzer_a1_a2
from app.domain.services.prompt_loader import (
    PromptNotFoundError,
    load_prompt,
    registry_version,
)


def _file_version(prompt_version: str) -> str:
    return registry_version(prompt_version)


def test_load_prompt_returns_registry_text() -> None:
    text = load_prompt("a1_classifier", "en", "2026-05-01.1")
    assert text.startswith("You are the Orthodox AI Assistant's query analyzer")
    assert text.endswith("\n")


def test_load_prompt_missing_raises() -> None:
    with pytest.raises(PromptNotFoundError):
        load_prompt("a1_classifier", "en", "0000-00-00.0")


def test_a1_builder_loads_active_registry_prompt() -> None:
    settings = get_settings()
    expected = load_prompt(
        "a1_classifier", "en", _file_version(settings.active_prompt_version_a1a2)
    )
    assert expected, "active A1 prompt is empty"
    assert query_analyzer_a1_a2._SYSTEM_PROMPT == expected


def test_a5_builder_loads_active_registry_prompt() -> None:
    settings = get_settings()
    expected = load_prompt(
        "a5_composer", "en", _file_version(settings.active_prompt_version_a5)
    )
    assert expected, "active A5 prompt is empty"
    assert composer_a5._SYSTEM_PROMPT == expected


def test_a6_judge_loads_active_registry_prompt() -> None:
    settings = get_settings()
    expected = load_prompt("a6_judge", "en", _file_version(settings.active_verifier_version))
    assert expected.startswith("You are a closed-corpus consistency judge")
    assert verifier._JUDGE_SYSTEM_PROMPT == expected


def test_active_prompt_versions_resolve_to_files() -> None:
    settings = get_settings()
    # Startup self-check: every active prompt version maps to an on-disk registry file.
    assert load_prompt("a1_classifier", "en", registry_version(settings.active_prompt_version_a1a2))
    assert load_prompt("a5_composer", "en", registry_version(settings.active_prompt_version_a5))
    assert load_prompt("a6_judge", "en", registry_version(settings.active_verifier_version))
