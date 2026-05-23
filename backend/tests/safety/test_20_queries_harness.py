"""Safety execution harness — runs the 20 canonical cases through the live A1–A6 pipeline.

T-001 ships this file as a placeholder so CI's `safety-suite-execution` job can detect its
presence (per `.github/workflows/ci-safety-gate.yml`). The full implementation lands in T-006:

- mock providers for hard-safety triggers (cases 6, 10, 12, 17, 20)
- real providers for the other cases
- assert `expected_handling` AND `expected_sensitivity` per case
- assert the canonical bounded-fallback substring for hard-safety cases

Until T-006 lands, this harness deliberately fails so the safety-execution gate stays red.
See docs/task_cards/phase1/T-006-admin-chat-safety-gate.md.
"""

from __future__ import annotations

import pytest


def test_safety_harness_not_yet_implemented() -> None:
    pytest.fail(
        "Safety execution harness is implemented in T-006. "
        "See docs/task_cards/phase1/T-006-admin-chat-safety-gate.md. "
        "The 20 canonical cases live in tests/safety/test_20_queries.py."
    )
