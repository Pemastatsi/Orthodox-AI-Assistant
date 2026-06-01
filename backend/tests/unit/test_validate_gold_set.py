"""Unit tests for the offline layer of scripts/validate_gold_set.py — free, deterministic.

The validator's value is catching bad gold sets *before* they gate a certification, so these focus
on the failure modes: schema violations, the minimally-sufficient subset rule, duplicate/ malformed
case ids, an empty reviewedBy, and the hard-trigger sensitivity ban. The live-corpus layer is
DB-gated and exercised separately.
"""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("app")

# The validator lives in repo-root scripts/ (not an installed package); load it by path.
_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "validate_gold_set.py"
_spec = importlib.util.spec_from_file_location("validate_gold_set", _SCRIPT)
assert _spec and _spec.loader
validate_gold_set = importlib.util.module_from_spec(_spec)
sys.modules["validate_gold_set"] = validate_gold_set
_spec.loader.exec_module(validate_gold_set)

_GOOD: dict[str, Any] = {
    "tenantId": "tenant_smoke",
    "version": "2026-05-29.1",
    "createdBy": "founder",
    "reviewedBy": ["founder"],
    "corpusVersionAtCuration": "v1",
    "cases": [
        {
            "id": "RE-001",
            "query": "Why does the Eastern Church reject papal supremacy?",
            "language": "en",
            "expectedChunkIds": ["chunk-a", "chunk-b"],
            "minimallySufficientChunkIds": ["chunk-a"],
            "answerMode": "institutional_policy",
            "sensitivityPrimary": "normal",
            "notes": "ok",
        }
    ],
}


def test_good_gold_set_is_valid() -> None:
    report = validate_gold_set.validate_offline(copy.deepcopy(_GOOD))
    assert report.ok, report.errors
    assert report.case_count == 1


def test_minimally_sufficient_must_be_subset() -> None:
    bad = copy.deepcopy(_GOOD)
    bad["cases"][0]["minimallySufficientChunkIds"] = ["chunk-a", "chunk-not-in-expected"]
    report = validate_gold_set.validate_offline(bad)
    assert not report.ok
    assert any("⊄ expectedChunkIds" in e for e in report.errors)


def test_empty_reviewed_by_is_rejected() -> None:
    bad = copy.deepcopy(_GOOD)
    bad["reviewedBy"] = []
    report = validate_gold_set.validate_offline(bad)
    assert not report.ok
    assert any("reviewedBy" in e for e in report.errors)


def test_hard_trigger_sensitivity_is_forbidden() -> None:
    bad = copy.deepcopy(_GOOD)
    bad["cases"][0]["sensitivityPrimary"] = "self_harm"
    report = validate_gold_set.validate_offline(bad)
    assert not report.ok
    # Caught either by the enum (schema) or the explicit hard-trigger guard — both are failures.
    assert report.errors


def test_duplicate_case_id_is_rejected() -> None:
    bad = copy.deepcopy(_GOOD)
    bad["cases"].append(copy.deepcopy(bad["cases"][0]))
    report = validate_gold_set.validate_offline(bad)
    assert not report.ok
    assert any("duplicate case id" in e for e in report.errors)


def test_malformed_case_id_is_rejected() -> None:
    bad = copy.deepcopy(_GOOD)
    bad["cases"][0]["id"] = "Q-001"
    report = validate_gold_set.validate_offline(bad)
    assert not report.ok
    assert any("must match" in e for e in report.errors)


def test_bad_version_pattern_is_rejected() -> None:
    bad = copy.deepcopy(_GOOD)
    bad["version"] = "v1"
    report = validate_gold_set.validate_offline(bad)
    assert not report.ok


def test_committed_smoke_gold_set_validates() -> None:
    # Regression guard: the real committed smoke fixture must always pass the offline validator.
    path = (
        Path(__file__).resolve().parents[1]
        / "retrieval_eval"
        / "gold_sets"
        / "tenant_smoke"
        / "2026-05-29.1.json"
    )
    import json

    report = validate_gold_set.validate_offline(json.loads(path.read_text()))
    assert report.ok, report.errors
    assert report.case_count == 6


# --------------------------------------------------------------------------------------------
# Published-schema <-> pydantic-model drift guard (T-009 Phase-A readiness).
#
# `validate_offline` enforces the gold-set shape via the pydantic `GoldSet` model
# (tests/retrieval_eval/harness.py), and `load_gold_set` drops `$schema` and validates through that
# same model — so the *published* JSON schema (docs/schemas/retrieval-eval-gold-set.schema.json),
# which curators read and tooling advertises, is never actually checked against the model that
# bites. These stdlib-only tests (no `jsonschema` dependency — the repo's Contracts CI job is
# deliberately stdlib-only) fail if the two drift apart on the contract surface: required fields and
# the documented patterns/enums.
# --------------------------------------------------------------------------------------------
import json  # noqa: E402  (kept local to this guard block)


def _published_schema() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "schemas"
        / "retrieval-eval-gold-set.schema.json"
    )
    return json.loads(path.read_text())


def test_published_schema_required_fields_match_model() -> None:
    """Top-level + per-case required fields in the published schema match the pydantic model
    (compared by camelCase alias, since WireModel uses alias_generator=to_camel)."""
    from tests.retrieval_eval.harness import GoldCase, GoldSet

    schema = _published_schema()

    model_top = set(GoldSet.model_json_schema(by_alias=True)["required"])
    assert set(schema["required"]) == model_top, (
        "top-level required fields drifted between the published schema and GoldSet"
    )

    model_case = set(GoldCase.model_json_schema(by_alias=True)["required"])
    schema_case = set(schema["$defs"]["case"]["required"])
    assert schema_case == model_case, (
        "per-case required fields drifted between the published schema and GoldCase"
    )


def test_published_schema_patterns_and_enums_match_validator_and_model() -> None:
    """The version/case-id regexes and the language/sensitivity enums in the published schema match
    the validator's hand-coded rules and the pydantic model's Literals — so a curator validating
    against the published schema gets the same verdict the gate will."""
    from tests.retrieval_eval.harness import GoldCase

    schema = _published_schema()
    case_props = schema["$defs"]["case"]["properties"]

    # Patterns the validator enforces directly (validate_gold_set._VERSION_RE / _CASE_ID_RE).
    assert schema["properties"]["version"]["pattern"] == validate_gold_set._VERSION_RE
    assert case_props["id"]["pattern"] == validate_gold_set._CASE_ID_RE

    # Enums must match the pydantic Literals exactly (order-insensitive).
    import typing

    model_fields = GoldCase.model_fields
    enum_pairs = [("language", "language"), ("sensitivityPrimary", "sensitivity_primary")]
    for wire_name, py_name in enum_pairs:
        schema_enum = set(case_props[wire_name]["enum"])
        # Literal[...] args live on the field annotation.
        literal_args = set(typing.get_args(model_fields[py_name].annotation))
        assert schema_enum == literal_args, f"{wire_name} enum drifted from the model Literal"

    # The hard-trigger ban the validator layers on top must NOT be expressible via the enum (the
    # forbidden aliases are intentionally absent from sensitivityPrimary).
    assert not (
        validate_gold_set._FORBIDDEN_SENSITIVITY_ALIASES
        & set(case_props["sensitivityPrimary"]["enum"])
    )
