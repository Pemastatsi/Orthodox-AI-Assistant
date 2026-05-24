"""Tests for `app.domain.services.safety_config`."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from app.domain.services.safety_config import (
    STUB_VERSION,
    SafetyConfigError,
    assert_production_ready,
    load_sensitivity_keywords,
    match_sensitivity,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_PATH = _REPO_ROOT / "config" / "sensitivity_keywords.yaml"


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "rules.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_shipped_stub_succeeds() -> None:
    config = load_sensitivity_keywords(_CONFIG_PATH)
    assert config.version == STUB_VERSION
    assert len(config.rules) >= 5
    ids = [r.rule_id for r in config.rules]
    assert len(set(ids)) == len(ids)
    # Self-harm rule is the canonical hard trigger.
    self_harm = next(r for r in config.rules if r.rule_id == "sk_self_harm_en_001")
    assert self_harm.hard_trigger is True
    assert "self_harm" in self_harm.risk_flags


def test_hard_trigger_matches_self_harm_phrasing() -> None:
    config = load_sensitivity_keywords(_CONFIG_PATH)
    match = match_sensitivity("I want to kill myself tonight", config)
    assert match is not None
    assert match.hard_trigger is True
    assert match.sensitivity == "pastoral_advice"
    assert "self_harm" in match.risk_flags


def test_soft_trigger_does_not_force_block() -> None:
    config = load_sensitivity_keywords(_CONFIG_PATH)
    match = match_sensitivity("should I divorce my wife", config)
    assert match is not None
    assert match.hard_trigger is False
    assert match.sensitivity == "pastoral_advice"


def test_no_match_returns_none() -> None:
    config = load_sensitivity_keywords(_CONFIG_PATH)
    assert match_sensitivity("what do the Fathers teach about prayer?", config) is None


def test_case_insensitive_matching() -> None:
    config = load_sensitivity_keywords(_CONFIG_PATH)
    upper = match_sensitivity("WHO SHOULD I VOTE for in November", config)
    mixed = match_sensitivity("Who Should I Vote for in November", config)
    assert upper is not None and mixed is not None
    assert upper.rule_id == mixed.rule_id == "sk_political_voting_en_001"


def test_first_match_wins(tmp_path: Path) -> None:
    body = """
version: "2026-05-01.1"
schema: "1"
regex_flavor: python_re
ordering: first_match_wins
languages: [en]
rules:
  - id: r_first
    pattern: "\\\\bprayer\\\\b"
    sensitivity: pastoral_advice
    risk_flags: []
    hard_trigger: false
    lang: en
  - id: r_second
    pattern: "\\\\bprayer\\\\b"
    sensitivity: political
    risk_flags: []
    hard_trigger: false
    lang: en
"""
    config = load_sensitivity_keywords(_write(tmp_path, body))
    match = match_sensitivity("a question about prayer", config)
    assert match is not None
    assert match.rule_id == "r_first"


def test_duplicate_id_rejected(tmp_path: Path) -> None:
    body = """
version: "2026-05-01.1"
schema: "1"
regex_flavor: python_re
ordering: first_match_wins
languages: [en]
rules:
  - id: dupe
    pattern: "a"
    sensitivity: pastoral_advice
    risk_flags: []
    hard_trigger: false
    lang: en
  - id: dupe
    pattern: "b"
    sensitivity: political
    risk_flags: []
    hard_trigger: false
    lang: en
"""
    with pytest.raises(SafetyConfigError, match="duplicate rule id"):
        load_sensitivity_keywords(_write(tmp_path, body))


def test_invalid_regex_rejected(tmp_path: Path) -> None:
    body = """
version: "2026-05-01.1"
schema: "1"
regex_flavor: python_re
ordering: first_match_wins
languages: [en]
rules:
  - id: r1
    pattern: "(unclosed"
    sensitivity: pastoral_advice
    risk_flags: []
    hard_trigger: false
    lang: en
"""
    with pytest.raises(SafetyConfigError, match="regex does not compile"):
        load_sensitivity_keywords(_write(tmp_path, body))


def test_hard_trigger_without_risk_flag_rejected(tmp_path: Path) -> None:
    body = """
version: "2026-05-01.1"
schema: "1"
regex_flavor: python_re
ordering: first_match_wins
languages: [en]
rules:
  - id: r1
    pattern: "danger"
    sensitivity: medical
    risk_flags: []
    hard_trigger: true
    lang: en
"""
    with pytest.raises(SafetyConfigError, match="hard_trigger requires"):
        load_sensitivity_keywords(_write(tmp_path, body))


def test_unknown_sensitivity_rejected(tmp_path: Path) -> None:
    body = """
version: "2026-05-01.1"
schema: "1"
regex_flavor: python_re
ordering: first_match_wins
languages: [en]
rules:
  - id: r1
    pattern: "x"
    sensitivity: not_a_real_value
    risk_flags: []
    hard_trigger: false
    lang: en
"""
    with pytest.raises(SafetyConfigError, match="'sensitivity'"):
        load_sensitivity_keywords(_write(tmp_path, body))


def test_unknown_risk_flag_rejected(tmp_path: Path) -> None:
    body = """
version: "2026-05-01.1"
schema: "1"
regex_flavor: python_re
ordering: first_match_wins
languages: [en]
rules:
  - id: r1
    pattern: "x"
    sensitivity: medical
    risk_flags: [not_a_flag]
    hard_trigger: false
    lang: en
"""
    with pytest.raises(SafetyConfigError, match="risk_flag"):
        load_sensitivity_keywords(_write(tmp_path, body))


def test_unicode_pattern_compiles(tmp_path: Path) -> None:
    body = """
version: "2026-05-01.1"
schema: "1"
regex_flavor: python_re
ordering: first_match_wins
languages: [el]
rules:
  - id: el_rule
    pattern: "προσευχ\\u03ae"
    sensitivity: pastoral_advice
    risk_flags: []
    hard_trigger: false
    lang: el
"""
    config = load_sensitivity_keywords(_write(tmp_path, body))
    assert config.rules[0].pattern.flags & re.UNICODE
    match = match_sensitivity("Πες μου για την προσευχή", config)
    assert match is not None and match.rule_id == "el_rule"


def test_assert_production_ready_blocks_stub_in_production() -> None:
    config = load_sensitivity_keywords(_CONFIG_PATH)
    with pytest.raises(SafetyConfigError, match="stub version"):
        assert_production_ready(config, app_env="production")


def test_assert_production_ready_allows_stub_in_development() -> None:
    config = load_sensitivity_keywords(_CONFIG_PATH)
    assert_production_ready(config, app_env="development")  # does not raise


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(SafetyConfigError, match="not found"):
        load_sensitivity_keywords(tmp_path / "does-not-exist.yaml")
