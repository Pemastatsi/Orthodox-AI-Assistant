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

# Builder modules whose _SYSTEM_PROMPT must be loaded from the registry, not inlined.
BUILDERS = [
    "backend/app/domain/prompts/query_analyzer_a1_a2.py",
    "backend/app/domain/prompts/composer_a5.py",
]


def _system_prompt_value(py_path: Path) -> ast.expr | None:
    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_SYSTEM_PROMPT" for t in node.targets
        ):
            return node.value
    return None


@pytest.mark.parametrize("rel", BUILDERS)
def test_system_prompt_is_loaded_not_embedded(rel: str) -> None:
    value = _system_prompt_value(REPO_ROOT / rel)
    assert value is not None, f"{rel}: no _SYSTEM_PROMPT assignment found"
    assert not isinstance(value, (ast.Constant, ast.JoinedStr)), (
        f"{rel}: _SYSTEM_PROMPT is an inline literal — answer-path prompts MUST be loaded "
        f"from /prompts via load_prompt() (GS-3 no-embedded-prompts rule)."
    )
    assert (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "load_prompt"
    ), f"{rel}: _SYSTEM_PROMPT must be assigned from load_prompt(...)"


def test_registry_layout_is_well_formed() -> None:
    assert (PROMPTS_DIR / "README.md").is_file(), "top-level /prompts/README.md is required"
    jinja_files = sorted(PROMPTS_DIR.rglob("*.j2"))
    assert jinja_files, "no prompt .j2 files found under /prompts/"
    for jf in jinja_files:
        rel = jf.relative_to(PROMPTS_DIR)
        assert len(rel.parts) == 3, f"{rel} must be <stage>/<language>/<version>.j2"
        assert jf.stat().st_size > 0, f"{jf} is empty"
        assert (jf.parent.parent / "README.md").is_file(), f"stage '{rel.parts[0]}' missing README.md"
