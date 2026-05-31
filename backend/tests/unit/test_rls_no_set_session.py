"""ADR-0016 Rule 6 guard: the tenant GUC must only ever be set with SET LOCAL, never SET SESSION.

`SET SESSION app.current_tenant_id` would persist the GUC on the pooled connection after the
transaction ends, so the next request to check out that connection could read a previous tenant's
id before its own `SET LOCAL` runs — a cross-tenant leak window. This test greps the application
source for `SET SESSION app` and fails if any appears. It is a cheap, offline invariant (no DB).
"""

from __future__ import annotations

import re
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parents[2] / "app"
# Case-insensitive: catch `SET SESSION app`, `set session  app`, etc. Whitespace-flexible.
_FORBIDDEN = re.compile(r"set\s+session\s+app\b", re.IGNORECASE)


def test_no_set_session_app_in_app_source() -> None:
    offenders: list[str] = []
    for path in _APP_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in _FORBIDDEN.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{path.relative_to(_APP_DIR.parent)}:{line}")
    assert not offenders, (
        "ADR-0016 Rule 6 violation — use SET LOCAL, never SET SESSION, for the tenant GUC: "
        + ", ".join(offenders)
    )


def test_guard_regex_actually_matches() -> None:
    # Sanity: the pattern catches the form it's meant to forbid (so a green test means something).
    assert _FORBIDDEN.search("SET SESSION app.current_tenant_id = 'x'")
    assert _FORBIDDEN.search("set  session   app.current_tenant_id")
    # And does not flag the permitted SET LOCAL form.
    assert not _FORBIDDEN.search("SET LOCAL app.current_tenant_id = 'x'")
