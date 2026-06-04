#!/usr/bin/env python3
"""Documentation-index drift checker (REC-003, T-008 doc-hygiene workstream).

Diffs the filesystem against the tables in ``docs/DOCS_INDEX.md`` for the three
contract directories that the index is the source of truth for:

    docs/adr/        (*.md)
    docs/contracts/  (*.md)
    docs/schemas/    (*.json)

Fails (exit 1) when:
  * a file exists on disk under one of those dirs with no row in DOCS_INDEX.md, or
  * an index row points at a path under one of those dirs that is missing on disk.

Stdlib only — safe to run in the CI ``contracts`` job with no extra deps. Wire via
``make check-docs-index``.

Exit code 0 = in sync; 1 = drift; 2 = usage/IO error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_INDEX_PATH = _REPO_ROOT / "docs" / "DOCS_INDEX.md"

# Directory -> filename glob the index is authoritative for.
_TRACKED_DIRS: dict[str, str] = {
    "docs/adr": "*.md",
    "docs/contracts": "*.md",
    "docs/schemas": "*.json",
}

# Any `backtick-wrapped` token. We only keep those under a tracked dir.
_BACKTICK_RE = re.compile(r"`([^`]+)`")


def _indexed_paths(index_text: str, prefix: str, suffix: str) -> set[str]:
    """Repo-relative file paths referenced in the index directly under ``prefix``.

    Only concrete filenames are kept: prose tokens like a bare ``docs/adr/`` or a
    glob ``docs/schemas/*.json`` are ignored, so the diff is against real rows.
    """
    found: set[str] = set()
    for token in _BACKTICK_RE.findall(index_text):
        token = token.strip()
        if not token.startswith(prefix + "/"):
            continue
        name = token[len(prefix) + 1 :]
        # Direct child only, a real filename (no glob), with the dir's extension.
        if not name or "/" in name or "*" in name or not name.endswith(suffix):
            continue
        found.add(token)
    return found


def _disk_paths(prefix: str, glob: str) -> set[str]:
    directory = _REPO_ROOT / prefix
    if not directory.is_dir():
        return set()
    return {f"{prefix}/{p.name}" for p in directory.glob(glob) if p.is_file()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index",
        default=str(_INDEX_PATH),
        help="Path to DOCS_INDEX.md (default: docs/DOCS_INDEX.md).",
    )
    args = parser.parse_args()

    index_file = Path(args.index)
    try:
        index_text = index_file.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - usage error
        print(f"error: cannot read index {index_file}: {exc}", file=sys.stderr)
        return 2

    missing_from_index: list[str] = []
    missing_on_disk: list[str] = []

    for prefix, glob in _TRACKED_DIRS.items():
        suffix = glob.lstrip("*")  # "*.md" -> ".md", "*.json" -> ".json"
        indexed = _indexed_paths(index_text, prefix, suffix)
        on_disk = _disk_paths(prefix, glob)
        missing_from_index.extend(sorted(on_disk - indexed))
        missing_on_disk.extend(sorted(indexed - on_disk))

    if not missing_from_index and not missing_on_disk:
        tracked = ", ".join(_TRACKED_DIRS)
        print(f"DOCS_INDEX.md OK — {tracked} fully mirrored.")
        return 0

    if missing_from_index:
        print("Files on disk with no DOCS_INDEX.md row:")
        for path in missing_from_index:
            print(f"  + {path}")
    if missing_on_disk:
        print("DOCS_INDEX.md rows pointing at missing files:")
        for path in missing_on_disk:
            print(f"  - {path}")
    print(
        "\nFix: add a row in docs/DOCS_INDEX.md for each '+' file, or remove/correct "
        "the row for each '-' path.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
