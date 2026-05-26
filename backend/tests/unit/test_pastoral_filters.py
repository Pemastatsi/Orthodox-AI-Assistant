"""Tests for the pastoral-filter loader and matcher (A6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.domain.services.safety_config import (
    SafetyConfigError,
    iter_pastoral_matches,
    load_pastoral_filters,
    match_pastoral_filter,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_PATH = _REPO_ROOT / "config" / "pastoral_filters.yaml"


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "pastoral.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_shipped_stub_succeeds() -> None:
    config = load_pastoral_filters(_CONFIG_PATH)
    assert len(config.rules) >= 3
    rule_ids = [r.rule_id for r in config.rules]
    assert "pf_electoral_guidance_en_001" in rule_ids


def test_match_pastoral_filter_returns_first_reject() -> None:
    config = load_pastoral_filters(_CONFIG_PATH)
    match = match_pastoral_filter("The Fathers say vote for the candidate of virtue.", config)
    assert match is not None
    assert match.rule_id == "pf_electoral_guidance_en_001"
    assert match.action == "reject_answer"
    assert match.reason_code == "safety_blocked"


def test_match_pastoral_filter_returns_none_on_safe_answer() -> None:
    config = load_pastoral_filters(_CONFIG_PATH)
    assert match_pastoral_filter("Saint Basil teaches us about prayer.", config) is None


def test_iter_pastoral_matches_returns_warns_too() -> None:
    config = load_pastoral_filters(_CONFIG_PATH)
    # The stub has a `warn` rule for invented quote attribution.
    matches = iter_pastoral_matches(
        'In one place Saint Basil said: "Pray always for the soul."', config
    )
    actions = {m.action for m in matches}
    assert "warn" in actions


def test_loader_rejects_unknown_reason_code(tmp_path: Path) -> None:
    body = """
version: "2026-05-01.1"
schema: "1"
regex_flavor: python_re
ordering: first_match_wins
languages: [en]
rules:
  - id: bad
    pattern: "vote"
    action: reject_answer
    reason_code: nonexistent_code_xyz
    lang: en
"""
    with pytest.raises(SafetyConfigError, match="reason_code"):
        load_pastoral_filters(_write(tmp_path, body))


def test_loader_rejects_unknown_action(tmp_path: Path) -> None:
    body = """
version: "2026-05-01.1"
schema: "1"
regex_flavor: python_re
ordering: first_match_wins
languages: [en]
rules:
  - id: bad
    pattern: "vote"
    action: i_made_this_up
    reason_code: safety_blocked
    lang: en
"""
    with pytest.raises(SafetyConfigError, match="action"):
        load_pastoral_filters(_write(tmp_path, body))


def test_loader_rejects_invalid_regex(tmp_path: Path) -> None:
    body = """
version: "2026-05-01.1"
schema: "1"
regex_flavor: python_re
ordering: first_match_wins
languages: [en]
rules:
  - id: bad
    pattern: "(unclosed"
    action: reject_answer
    reason_code: safety_blocked
    lang: en
"""
    with pytest.raises(SafetyConfigError, match="regex does not compile"):
        load_pastoral_filters(_write(tmp_path, body))


def test_loader_rejects_duplicate_id(tmp_path: Path) -> None:
    body = """
version: "2026-05-01.1"
schema: "1"
regex_flavor: python_re
ordering: first_match_wins
languages: [en]
rules:
  - id: dupe
    pattern: "a"
    action: reject_answer
    reason_code: safety_blocked
    lang: en
  - id: dupe
    pattern: "b"
    action: warn
    reason_code: verifier_failed
    lang: en
"""
    with pytest.raises(SafetyConfigError, match="duplicate rule id"):
        load_pastoral_filters(_write(tmp_path, body))


def test_loader_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SafetyConfigError, match="not found"):
        load_pastoral_filters(tmp_path / "missing.yaml")
