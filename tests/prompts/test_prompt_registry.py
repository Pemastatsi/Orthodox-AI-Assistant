"""GS-3 prompt-registry gate (dep-free; runs in the `prompts-gate` CI job).

Validates the `/prompts` registry layout and enforces the **no-embedded-prompts** rule: the
answer-path builders must load their system prompt from `/prompts` via `load_prompt()` and
never inline a literal. Source is parsed with :mod:`ast` (no backend imports), so this runs
with ``pytest`` alone — mirroring the ``safety-suite-fixtures`` job. The semantic check that
the loaded text matches the active route lives in ``backend/tests/unit/test_prompt_loader.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = REPO_ROOT / "prompts"

# Module-level prompt constants that MUST be loaded from the registry, never inlined:
# (source file relative to repo root, constant name).
LOADED_PROMPTS = [
    ("backend/app/domain/prompts/query_analyzer_a1_a2.py", "_SYSTEM_PROMPT"),
    ("backend/app/domain/prompts/composer_a5.py", "_SYSTEM_PROMPT"),
    ("backend/app/domain/agents/verifier.py", "_JUDGE_SYSTEM_PROMPT"),
]


def _assigned_value(py_path: Path, name: str) -> ast.expr | None:
    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node.value
    return None


@pytest.mark.parametrize("rel, name", LOADED_PROMPTS)
def test_prompt_constant_is_loaded_not_embedded(rel: str, name: str) -> None:
    value = _assigned_value(REPO_ROOT / rel, name)
    assert value is not None, f"{rel}: no {name} assignment found"
    assert not isinstance(value, (ast.Constant, ast.JoinedStr)), (
        f"{rel}: {name} is an inline literal — prompts MUST be loaded from /prompts via "
        f"load_prompt() (GS-3 no-embedded-prompts rule)."
    )
    assert (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "load_prompt"
    ), f"{rel}: {name} must be assigned from load_prompt(...)"


def test_registry_layout_is_well_formed() -> None:
    assert (PROMPTS_DIR / "README.md").is_file(), "top-level /prompts/README.md is required"
    jinja_files = sorted(PROMPTS_DIR.rglob("*.j2"))
    assert jinja_files, "no prompt .j2 files found under /prompts/"
    for jf in jinja_files:
        rel = jf.relative_to(PROMPTS_DIR)
        assert len(rel.parts) == 3, f"{rel} must be <stage>/<language>/<version>.j2"
        assert jf.stat().st_size > 0, f"{jf} is empty"
        assert (jf.parent.parent / "README.md").is_file(), f"stage '{rel.parts[0]}' missing README.md"


def _bare_string_constant_ids(tree: ast.AST) -> set[int]:
    """ids of string Constants used as bare expressions (docstrings / standalone strings),
    excluded from the embedded-prompt scan."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            ids.add(id(node.value))
    return ids


def test_no_embedded_prompt_literals_in_app_source() -> None:
    """Defense-in-depth heuristic (docs/contracts/prompt-management.md §Forbidden patterns):
    no string literal >200 chars containing 'You are'/'Your task is' may live in backend/app
    source — prompts belong in /prompts, loaded via load_prompt()."""
    app_dir = REPO_ROOT / "backend" / "app"
    offenders: list[str] = []
    for py in sorted(app_dir.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        bare = _bare_string_constant_ids(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in bare
                and len(node.value) > 200
                and ("You are" in node.value or "Your task is" in node.value)
            ):
                offenders.append(f"{py.relative_to(REPO_ROOT)}:{node.lineno}")
    assert not offenders, (
        f"Embedded prompt-like literal(s) found; move into /prompts and load via load_prompt(): "
        f"{offenders}"
    )
