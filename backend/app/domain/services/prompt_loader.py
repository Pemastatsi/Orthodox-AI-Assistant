"""Runtime prompt loader for the `/prompts` registry (GS-3).

`prompts/<stage>/<language>/<version>.j2` is the single source of truth for the
answer-pipeline system prompts. This loader returns a prompt file's text **verbatim** —
there is no templating step: the current prompts carry no variables (dynamic context is
composed in Python around the system prompt), so a `.j2` with no Jinja tags renders to its
own bytes anyway. A real rendering layer can be added the day a prompt needs variables.

The registry root is `Settings.prompts_dir` (defaults to `<repo>/prompts`), mirroring how
`safety_config` locates its YAML. Files are read once and cached; a missing file raises
`PromptNotFoundError` so a misconfigured route fails fast at startup rather than silently
serving an empty system prompt. See `/prompts/README.md`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


class PromptNotFoundError(RuntimeError):
    """A requested prompt file is absent from the `/prompts` registry."""


def registry_version(prompt_version: str) -> str:
    """Map a route ``promptVersion`` ("{name}@{YYYY-MM-DD.N}") to its registry file stem
    ("{YYYY-MM-DD.N}"). The on-disk template is ``{stage}/{language}/{stem}.j2``; the
    ``{name}@`` prefix is the route/cache identifier, stripped here to locate the file."""
    return prompt_version.split("@", 1)[-1]


@lru_cache(maxsize=None)
def load_prompt(stage: str, language: str, version: str) -> str:
    """Return the verbatim text of `prompts/<stage>/<language>/<version>.j2`.

    `version` is the on-disk version stem (e.g. ``2026-05-01.1``) — i.e. the
    ``<YYYY-MM-DD.NN>`` portion of a route's ``promptVersion``.
    """
    path = Path(get_settings().prompts_dir) / stage / language / f"{version}.j2"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PromptNotFoundError(
            f"prompt not found in registry: {stage}/{language}/{version}.j2"
        ) from exc


__all__ = ["PromptNotFoundError", "load_prompt", "registry_version"]
