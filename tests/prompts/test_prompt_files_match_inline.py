"""GS-3 prompt-registry drift guard (dep-free; runs in the `prompts-gate` CI job).

Phase-1 bootstrap: the canonical prompt text lives under
`/prompts/<stage>/<language>/<version>.j2`, but the A1/A2 and A5 agents still load
their prompt from the inline ``_SYSTEM_PROMPT`` literal in
``backend/app/domain/prompts/*.py`` (the runtime template-loader is the GS-3
follow-up). Until the loader lands the ``.j2`` file is a *copy*, so this test pins
it to the inline source: each ``.j2`` must equal, byte-for-byte, the
``_SYSTEM_PROMPT`` value parsed out of the corresponding module with :mod:`ast`.

Parsing via :mod:`ast` (not import) keeps this test free of backend dependencies,
so it runs with ``pytest`` alone — mirroring the ``safety-suite-fixtures`` job.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = REPO_ROOT / "prompts"

# canonical .j2 (relative to /prompts)  ->  inline source module + module-level
# constant it must stay byte-identical to. Add always-on answer-path prompts here
# when they are introduced.
REGISTRY: list[tuple[str, str, str]] = [
    (
        "a1_classifier/en/2026-05-01.1.j2",
        "backend/app/domain/prompts/query_analyzer_a1_a2.py",
        "_SYSTEM_PROMPT",
    ),
    (
        "a5_composer/en/2026-05-01.1.j2",
        "backend/app/domain/prompts/composer_a5.py",
        "_SYSTEM_PROMPT",
    ),
]


def _module_level_str(py_path: Path, var: str) -> str:
    """Return the value of a module-level ``var = "..."`` assignment, without importing."""
    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == var for t in node.targets
        ):
            value = ast.literal_eval(node.value)
            assert isinstance(value, str), f"{var} in {py_path} is not a string literal"
            return value
    raise AssertionError(f"{var} not found as a module-level string in {py_path}")


@pytest.mark.parametrize("jinja_rel, source_rel, var", REGISTRY)
def test_prompt_file_matches_inline_source(jinja_rel: str, source_rel: str, var: str) -> None:
    jinja_path = PROMPTS_DIR / jinja_rel
    source_path = REPO_ROOT / source_rel
    assert jinja_path.is_file(), f"missing canonical prompt file: {jinja_path}"
    assert source_path.is_file(), f"missing inline source: {source_path}"

    inline_value = _module_level_str(source_path, var)
    assert jinja_path.read_text(encoding="utf-8") == inline_value, (
        f"{jinja_rel} has drifted from {source_rel}:{var}. The .j2 file is the canonical "
        f"copy; until the GS-3 runtime loader lands the two MUST stay byte-identical. "
        f"Update both together and add a new version per /prompts/README.md."
    )


def test_mapped_files_exist() -> None:
    # Guards against a REGISTRY entry whose .j2 was renamed/deleted without updating it.
    for jinja_rel, _source_rel, _var in REGISTRY:
        assert (PROMPTS_DIR / jinja_rel).is_file(), f"REGISTRY points at missing {jinja_rel}"


def test_registry_layout_is_well_formed() -> None:
    assert (PROMPTS_DIR / "README.md").is_file(), "top-level /prompts/README.md is required"
    jinja_files = sorted(PROMPTS_DIR.rglob("*.j2"))
    assert jinja_files, "no prompt .j2 files found under /prompts/"
    for jf in jinja_files:
        rel = jf.relative_to(PROMPTS_DIR)
        # layout: <stage>/<language>/<version>.j2
        assert len(rel.parts) == 3, f"{rel} must be <stage>/<language>/<version>.j2"
        assert jf.stat().st_size > 0, f"{jf} is empty"
        stage_readme = jf.parent.parent / "README.md"
        assert stage_readme.is_file(), f"stage '{rel.parts[0]}' is missing README.md"
