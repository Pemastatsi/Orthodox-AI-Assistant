#!/usr/bin/env python3
"""Enum-parity gate for the hand-maintained schema <-> OpenAPI <-> Pydantic mirrors.

A few enums are deliberately duplicated across contract surfaces because OpenAPI 3.1
tooling cannot reliably ``$ref`` a cross-file JSON Schema enum (see the NOTE above
``AnswerMode`` in docs/api/openapi.yaml). This script is the CI guard those NOTE
comments promise: it fails the build when the duplicated lists drift apart.

Checks (each requires byte-for-byte identical, *ordered* value lists):

  AnswerMode  (3-way)
    - docs/schemas/answer-mode.schema.json     : enum
    - docs/api/openapi.yaml                    : components.schemas.AnswerMode.enum
    - backend/app/domain/models/answer_mode.py : the ``AnswerMode = Literal[...]``

  ProgressVariant.stage  (JSON Schema <-> OpenAPI)
    - docs/schemas/progress-event.schema.json  (ProgressVariant.properties.stage.enum)
    - docs/api/openapi.yaml                     (same path under components.schemas)

Requires PyYAML to parse the OpenAPI document (already installed in the CI
``contracts`` job; ``pip install pyyaml`` locally). Everything else is stdlib, and the
Pydantic Literal is read via ``ast`` so no application code is imported. Wire via
``make verify-enums``.

Exit code 0 = all mirrors aligned; 1 = drift; 2 = usage / parse / IO error.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - environment guard
    print(
        "error: PyYAML is required to parse docs/api/openapi.yaml (`pip install pyyaml`).",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OPENAPI = _REPO_ROOT / "docs" / "api" / "openapi.yaml"
_ANSWER_MODE_PY = _REPO_ROOT / "backend" / "app" / "domain" / "models" / "answer_mode.py"

# Raised by the extraction helpers below; surfaced as exit code 2 (parse/IO error).
_PARSE_ERRORS = (OSError, ValueError, KeyError, LookupError, json.JSONDecodeError, yaml.YAMLError)


def _dig(obj: Any, *path: Any, source: str) -> Any:
    """Walk nested dict/list keys, raising a precise error on a missing node."""
    cur = obj
    for key in path:
        try:
            cur = cur[key]
        except (KeyError, IndexError, TypeError) as exc:
            joined = " -> ".join(str(p) for p in path)
            raise KeyError(f"{source}: cannot resolve {joined} (failed at {key!r}): {exc}") from exc
    return cur


def _json_enum(rel_path: str, *path: Any) -> list[str]:
    data = json.loads((_REPO_ROOT / rel_path).read_text(encoding="utf-8"))
    return list(_dig(data, *path, source=rel_path))


def _openapi_enum(*path: Any) -> list[str]:
    data = yaml.safe_load(_OPENAPI.read_text(encoding="utf-8"))
    return list(_dig(data, *path, source="docs/api/openapi.yaml"))


def _pydantic_literal(alias: str) -> list[str]:
    """Extract the string members of ``<alias> = Literal[...]`` without importing the app."""
    name = _ANSWER_MODE_PY.name
    tree = ast.parse(_ANSWER_MODE_PY.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if not any(isinstance(t, ast.Name) and t.id == alias for t in targets):
            continue
        if not (
            isinstance(value, ast.Subscript)
            and isinstance(value.value, ast.Name)
            and value.value.id == "Literal"
        ):
            raise ValueError(f"{name}: `{alias}` is not assigned a typing.Literal[...]")
        sl = value.slice
        elts = sl.elts if isinstance(sl, ast.Tuple) else [sl]
        out: list[str] = []
        for elt in elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                out.append(elt.value)
            else:
                raise ValueError(f"{name}: `{alias}` Literal has a non-string member")
        return out
    raise LookupError(f"{name}: `{alias} = Literal[...]` not found")


def _check(name: str, sources: dict[str, list[str]]) -> list[str]:
    """Return failure lines (empty == every source has identical, identically ordered values)."""
    (ref_label, ref), *rest = sources.items()
    failures: list[str] = []
    for label, values in rest:
        if values != ref:
            failures.append(
                f"  [{name}] DRIFT between {ref_label} and {label}:\n"
                f"      {ref_label}: {ref}\n"
                f"      {label}: {values}"
            )
    return failures


def main() -> int:
    try:
        checks: dict[str, dict[str, list[str]]] = {
            "AnswerMode": {
                "docs/schemas/answer-mode.schema.json": _json_enum(
                    "docs/schemas/answer-mode.schema.json", "enum"
                ),
                "docs/api/openapi.yaml": _openapi_enum(
                    "components", "schemas", "AnswerMode", "enum"
                ),
                "backend/app/domain/models/answer_mode.py": _pydantic_literal("AnswerMode"),
            },
            "ProgressVariant.stage": {
                "docs/schemas/progress-event.schema.json": _json_enum(
                    "docs/schemas/progress-event.schema.json",
                    "$defs", "ProgressVariant", "properties", "stage", "enum",
                ),
                "docs/api/openapi.yaml": _openapi_enum(
                    "components", "schemas", "ProgressVariant", "properties", "stage", "enum"
                ),
            },
        }
    except _PARSE_ERRORS as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    failures: list[str] = []
    for name, sources in checks.items():
        failures.extend(_check(name, sources))

    if failures:
        print("Enum parity FAILED — duplicated enum lists have drifted:\n")
        print("\n\n".join(failures))
        print(
            "\nFix: make the listed surfaces byte-for-byte identical (same values, same "
            "order). See the NOTE comments in docs/api/openapi.yaml.",
            file=sys.stderr,
        )
        return 1

    summary = ", ".join(
        f"{name} ({len(next(iter(srcs.values())))} values)" for name, srcs in checks.items()
    )
    print(f"Enum parity OK — {summary}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
