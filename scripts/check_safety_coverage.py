#!/usr/bin/env python3
"""Safety-config coverage checker (T-007 launch-gate aid).

`docs/contracts/safety-config-format.md` §"Phase 2 Launch Gate" requires the real
`config/sensitivity_keywords.yaml` to cover **every** `sensitivityPrimary` enum value
(except `normal`) and **every** `riskFlags` value with at least one rule, with Greek
(`lang: el`) variants alongside the English ones.

This reports that coverage as a matrix and tells you exactly which Greek variants are
still missing (the config currently ships some `el` rules as a deliberate "(deferred)"
first pass). The canonical enum lists are read from `docs/schemas/classified-query.schema.json`
so this tracks the contract rather than a hand-copied list.

Not a duplicate of the loader tests (`test_safety_config.py`) or the case/paraphrase invariants
in `test_20_queries*.py` — it checks taxonomy *coverage*, which neither of those does.

Exit code 0 = English coverage complete (Greek gaps are reported but non-fatal by default);
1 = a required rule is missing (or, with --require-el, a Greek variant is missing);
2 = usage / parse / IO error.

Stdlib + PyYAML only (PyYAML is already a backend dep). Wire via `make check-safety-coverage`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - environment guard
    print("error: PyYAML is required (`pip install pyyaml`).", file=sys.stderr)
    raise SystemExit(2) from None

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA = _REPO_ROOT / "docs" / "schemas" / "classified-query.schema.json"
_CONFIG = _REPO_ROOT / "config" / "sensitivity_keywords.yaml"
_LANGS = ("en", "el")


def _load_expected(schema_path: Path) -> tuple[list[str], list[str]]:
    """Return (sensitivities-excluding-normal, risk_flags) from the classified-query schema."""
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    props = data["properties"]
    sensitivities = [s for s in props["sensitivityPrimary"]["enum"] if s != "normal"]
    risk_flags = list(props["riskFlags"]["items"]["enum"])
    return sensitivities, risk_flags


def _coverage(rules: list[dict[str, Any]]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Map each sensitivity / risk_flag to the set of languages that cover it."""
    sens_langs: dict[str, set[str]] = {}
    flag_langs: dict[str, set[str]] = {}
    for rule in rules:
        lang = str(rule.get("lang", ""))
        sensitivity = rule.get("sensitivity")
        if sensitivity:
            sens_langs.setdefault(str(sensitivity), set()).add(lang)
        for flag in rule.get("risk_flags", []) or []:
            flag_langs.setdefault(str(flag), set()).add(lang)
    return sens_langs, flag_langs


def _render(
    title: str, expected: list[str], covered: dict[str, set[str]]
) -> tuple[list[str], list[str]]:
    """Print one coverage table; return (en_missing, el_missing)."""
    en_missing: list[str] = []
    el_missing: list[str] = []
    print(f"\n{title}")
    print(f"  {'value':<26} {'en':<5} {'el':<5}")
    print(f"  {'-' * 26} {'-' * 5} {'-' * 5}")
    for value in expected:
        langs = covered.get(value, set())
        en = "yes" if "en" in langs else "MISSING"
        el = "yes" if "el" in langs else "gap"
        if "en" not in langs:
            en_missing.append(value)
        if "el" not in langs:
            el_missing.append(value)
        print(f"  {value:<26} {en:<5} {el:<5}")
    return en_missing, el_missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(_CONFIG), help="sensitivity_keywords.yaml path.")
    parser.add_argument("--schema", default=str(_SCHEMA), help="classified-query.schema.json path.")
    parser.add_argument(
        "--require-el",
        action="store_true",
        help="Treat a missing Greek (el) variant as a failure (full-parity mode).",
    )
    args = parser.parse_args()

    try:
        sensitivities, risk_flags = _load_expected(Path(args.schema))
        config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
        rules = config.get("rules", []) if isinstance(config, dict) else []
        sens_langs, flag_langs = _coverage(rules)
    except (OSError, KeyError, ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    version = config.get("version", "?") if isinstance(config, dict) else "?"
    print(f"Safety-config coverage — {Path(args.config).name} (version {version})")

    sens_en_missing, sens_el_missing = _render("sensitivityPrimary", sensitivities, sens_langs)
    flag_en_missing, flag_el_missing = _render("riskFlags", risk_flags, flag_langs)

    en_missing = sens_en_missing + flag_en_missing
    el_missing = sens_el_missing + flag_el_missing

    print()
    if en_missing:
        print(
            f"FAIL — required English rules missing for: {', '.join(en_missing)}",
            file=sys.stderr,
        )
    if el_missing:
        label = "FAIL" if args.require_el else "note"
        print(f"{label} — Greek (el) variants not yet present for: {', '.join(el_missing)}")
        if not args.require_el:
            print("      (deferred per the config matrix; use --require-el to enforce parity.)")

    if en_missing or (args.require_el and el_missing):
        return 1
    print("\nEnglish coverage complete." + ("" if not el_missing else " Greek gaps noted above."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
