"""Safety config loader and matcher for A1.

Canonical owner of `config/sensitivity_keywords.yaml` per
`docs/contracts/safety-config-format.md`. Loaded at startup; validation failures
must prevent the service from booting. The hard-trigger regex match runs *before*
any LLM call (T-003 acceptance test).

`pastoral_filters.yaml` (A6, T-004) reuses the validation conventions documented
here but is implemented separately when T-004 lands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, get_args

import yaml

from app.domain.models.classified_query import RiskFlag, SensitivityPrimary

_SENSITIVITY_VALUES: Final[frozenset[str]] = frozenset(get_args(SensitivityPrimary))
_RISK_FLAG_VALUES: Final[frozenset[str]] = frozenset(get_args(RiskFlag))
_LANG_VALUES: Final[frozenset[str]] = frozenset({"en", "el"})

STUB_VERSION: Final[str] = "2026-05-01.1"


@dataclass(frozen=True)
class SafetyRule:
    rule_id: str
    pattern: re.Pattern[str]
    sensitivity: SensitivityPrimary
    risk_flags: tuple[RiskFlag, ...]
    hard_trigger: bool
    lang: Literal["en", "el"]
    notes: str | None


@dataclass(frozen=True)
class SafetyConfig:
    version: str
    rules: tuple[SafetyRule, ...]
    source_path: Path


@dataclass(frozen=True)
class SafetyMatch:
    rule_id: str
    sensitivity: SensitivityPrimary
    risk_flags: tuple[RiskFlag, ...]
    hard_trigger: bool
    lang: Literal["en", "el"]


class SafetyConfigError(ValueError):
    """Raised when the YAML cannot be parsed or violates the schema."""


def load_sensitivity_keywords(path: str | Path) -> SafetyConfig:
    """Parse and validate `config/sensitivity_keywords.yaml`. Raises `SafetyConfigError` on any
    schema, type, regex, or uniqueness violation. The returned config is immutable."""
    yaml_path = Path(path)
    if not yaml_path.is_file():
        raise SafetyConfigError(f"safety config not found: {yaml_path}")

    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SafetyConfigError(f"YAML parse error in {yaml_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise SafetyConfigError(f"{yaml_path}: top-level must be a mapping")

    version = raw.get("version")
    if not isinstance(version, str) or not version:
        raise SafetyConfigError(f"{yaml_path}: 'version' must be a non-empty string")

    if raw.get("regex_flavor") not in (None, "python_re"):
        raise SafetyConfigError(
            f"{yaml_path}: only regex_flavor: python_re is supported"
        )
    if raw.get("ordering") not in (None, "first_match_wins"):
        raise SafetyConfigError(
            f"{yaml_path}: only ordering: first_match_wins is supported"
        )

    rules_raw = raw.get("rules")
    if not isinstance(rules_raw, list) or not rules_raw:
        raise SafetyConfigError(f"{yaml_path}: 'rules' must be a non-empty list")

    rules: list[SafetyRule] = []
    seen_ids: set[str] = set()
    for idx, item in enumerate(rules_raw):
        rules.append(_parse_rule(item, yaml_path=yaml_path, index=idx, seen_ids=seen_ids))

    return SafetyConfig(version=version, rules=tuple(rules), source_path=yaml_path)


def _parse_rule(
    item: object,
    *,
    yaml_path: Path,
    index: int,
    seen_ids: set[str],
) -> SafetyRule:
    if not isinstance(item, dict):
        raise SafetyConfigError(f"{yaml_path}: rule {index} must be a mapping")

    rule_id = item.get("id")
    if not isinstance(rule_id, str) or not rule_id.strip():
        raise SafetyConfigError(f"{yaml_path}: rule {index} 'id' must be a non-empty string")
    if rule_id in seen_ids:
        raise SafetyConfigError(f"{yaml_path}: duplicate rule id {rule_id!r}")
    seen_ids.add(rule_id)

    pattern_raw = item.get("pattern")
    if not isinstance(pattern_raw, str) or not pattern_raw:
        raise SafetyConfigError(
            f"{yaml_path}: rule {rule_id!r} 'pattern' must be a non-empty string"
        )
    try:
        compiled = re.compile(pattern_raw, re.IGNORECASE | re.UNICODE)
    except re.error as exc:
        raise SafetyConfigError(
            f"{yaml_path}: rule {rule_id!r} regex does not compile: {exc}"
        ) from exc

    sensitivity = item.get("sensitivity")
    if sensitivity not in _SENSITIVITY_VALUES:
        raise SafetyConfigError(
            f"{yaml_path}: rule {rule_id!r} 'sensitivity' must be one of "
            f"{sorted(_SENSITIVITY_VALUES)}"
        )

    risk_flags_raw = item.get("risk_flags", [])
    if not isinstance(risk_flags_raw, list):
        raise SafetyConfigError(f"{yaml_path}: rule {rule_id!r} 'risk_flags' must be a list")
    for flag in risk_flags_raw:
        if flag not in _RISK_FLAG_VALUES:
            raise SafetyConfigError(
                f"{yaml_path}: rule {rule_id!r} risk_flag {flag!r} not in "
                f"{sorted(_RISK_FLAG_VALUES)}"
            )

    hard_trigger = item.get("hard_trigger", False)
    if not isinstance(hard_trigger, bool):
        raise SafetyConfigError(f"{yaml_path}: rule {rule_id!r} 'hard_trigger' must be a bool")
    if hard_trigger and not risk_flags_raw:
        raise SafetyConfigError(
            f"{yaml_path}: rule {rule_id!r} hard_trigger requires at least one risk_flag"
        )

    lang = item.get("lang")
    if lang not in _LANG_VALUES:
        raise SafetyConfigError(
            f"{yaml_path}: rule {rule_id!r} 'lang' must be 'en' or 'el'"
        )

    notes = item.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise SafetyConfigError(f"{yaml_path}: rule {rule_id!r} 'notes' must be a string")

    return SafetyRule(
        rule_id=rule_id,
        pattern=compiled,
        sensitivity=sensitivity,  # type: ignore[arg-type]
        risk_flags=tuple(risk_flags_raw),
        hard_trigger=hard_trigger,
        lang=lang,  # type: ignore[arg-type]
        notes=notes,
    )


def match_sensitivity(text: str, config: SafetyConfig) -> SafetyMatch | None:
    """Return the first rule whose pattern matches `text`, or None.

    First-match-wins per `safety-config-format.md`. Patterns were compiled with
    `IGNORECASE | UNICODE`, so callers do not need to normalize case.
    """
    for rule in config.rules:
        if rule.pattern.search(text):
            return SafetyMatch(
                rule_id=rule.rule_id,
                sensitivity=rule.sensitivity,
                risk_flags=rule.risk_flags,
                hard_trigger=rule.hard_trigger,
                lang=rule.lang,
            )
    return None


def assert_production_ready(config: SafetyConfig, *, app_env: str) -> None:
    """Phase 2 launch gate per safety-config-format.md.

    If running in production against a stub baseline (`version == STUB_VERSION`), refuse to boot
    so a stub config can never serve production traffic. Other environments pass through."""
    if app_env == "production" and config.version == STUB_VERSION:
        raise SafetyConfigError(
            f"refusing to boot: {config.source_path} still carries the stub version "
            f"{STUB_VERSION!r}. Real safety rules with founder sign-off are required before "
            "production deploy (see docs/contracts/safety-config-format.md §Phase 2 Launch Gate)."
        )


__all__ = [
    "STUB_VERSION",
    "SafetyConfig",
    "SafetyConfigError",
    "SafetyMatch",
    "SafetyRule",
    "assert_production_ready",
    "load_sensitivity_keywords",
    "match_sensitivity",
]
