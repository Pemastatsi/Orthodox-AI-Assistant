"""Unit tests for the Phase 1 → 2 exit-criteria dashboard (scripts/exit_criteria_dashboard.py).

These exercise the pure ``_eval_*`` threshold helpers and the URL normaliser —
no database or SQLAlchemy install is required. The DB query wiring is covered
separately (and is gated on a live Postgres); the threshold logic is where the
regressions live, so that is what we pin here.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

# Load the standalone script (it lives under scripts/, not an importable package).
# Typed as Any so the dynamic ``dash._eval_*`` lookups stay mypy-clean.
_MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "exit_criteria_dashboard.py"
_spec = importlib.util.spec_from_file_location("exit_criteria_dashboard", _MODULE_PATH)
assert _spec and _spec.loader
dash: Any = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dash)


# --- URL normalisation -----------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("postgresql://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+asyncpg://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
    ],
)
def test_normalize_db_url(raw: str, expected: str) -> None:
    assert dash._normalize_db_url(raw) == expected


# --- #1 safety-suite stability --------------------------------------------


@pytest.mark.parametrize("days,passing", [(14, True), (20, True), (13, False), (0, False)])
def test_eval_consecutive_days(days: int, passing: bool) -> None:
    value, ok = dash._eval_consecutive_days(days)
    assert ok is passing
    assert "14" in value


# --- #2 internal traffic ---------------------------------------------------


@pytest.mark.parametrize("count,passing", [(50, True), (51, True), (49, False), (0, False)])
def test_eval_min_count(count: int, passing: bool) -> None:
    assert dash._eval_min_count(count, 50) == (str(count), passing)


# --- #3 RED rate ceiling ---------------------------------------------------


def test_eval_red_rate_boundary_inclusive() -> None:
    value, ok = dash._eval_red_rate(3, 10)  # exactly 30%
    assert ok is True
    assert "30.0%" in value


@pytest.mark.parametrize(
    "red,total,passing",
    [(4, 10, False), (0, 10, True), (30, 100, True), (31, 100, False)],
)
def test_eval_red_rate(red: int, total: int, passing: bool) -> None:
    _value, ok = dash._eval_red_rate(red, total)
    assert ok is passing


def test_eval_red_rate_no_data() -> None:
    value, ok = dash._eval_red_rate(0, 0)
    assert ok is False
    assert value == "no served answers"


# --- #4 latency ------------------------------------------------------------


@pytest.mark.parametrize(
    "p95,passing", [(7999.0, True), (0.0, True), (8000.0, False), (9001.0, False)]
)
def test_eval_p95(p95: float, passing: bool) -> None:
    _value, ok = dash._eval_p95(p95)
    assert ok is passing


def test_eval_p95_no_data() -> None:
    assert dash._eval_p95(None) == ("no data", False)


# --- #5 tenant isolation ---------------------------------------------------


@pytest.mark.parametrize(
    "result,passing", [("pass", True), ("fail", False), ("error", False), (None, False)]
)
def test_eval_last_result(result, passing: bool) -> None:
    _value, ok = dash._eval_last_result(result)
    assert ok is passing


# --- #6 founder signoff ----------------------------------------------------


@pytest.mark.parametrize(
    "role,reviewed,cats,passing",
    [
        ("owner", 20, 3, True),
        ("owner", 25, 5, True),
        ("owner", 19, 3, False),  # too few reviewed runs
        ("owner", 20, 2, False),  # too few categories
        ("member", 20, 3, False),  # not an owner
        (None, 0, 0, False),  # no signoff row
    ],
)
def test_eval_founder_signoff(role, reviewed: int, cats: int, passing: bool) -> None:
    _value, ok = dash._eval_founder_signoff(role, reviewed, cats)
    assert ok is passing


# --- #7 corpus health ------------------------------------------------------


@pytest.mark.parametrize(
    "chunks,sources,passing",
    [(100, 5, True), (250, 9, True), (99, 5, False), (100, 4, False)],
)
def test_eval_corpus(chunks: int, sources: int, passing: bool) -> None:
    _value, ok = dash._eval_corpus(chunks, sources)
    assert ok is passing


# --- #8 operational basics -------------------------------------------------


@pytest.mark.parametrize(
    "traces,billing,retention,passing",
    [
        (1, 1, "2026-06-01T00:00:00Z", True),
        (0, 1, "2026-06-01T00:00:00Z", False),  # no run traces
        (1, 0, "2026-06-01T00:00:00Z", False),  # no billing period reported
        (1, 1, None, False),  # retention worker never ran
    ],
)
def test_eval_operational(traces: int, billing: int, retention, passing: bool) -> None:
    _value, ok = dash._eval_operational(traces, billing, retention)
    assert ok is passing


# --- #9 real safety configs (founder-only) ---------------------------------


@pytest.mark.parametrize(
    "kw,pf,passing",
    [
        ("2026-06-01.1", "2026-06-02.1", True),
        ("2026-05-01.1", "2026-06-02.1", False),  # keywords still stub
        ("2026-06-01.1", "2026-05-01.1", False),  # filters still stub
        (None, None, False),  # no approval row
    ],
)
def test_eval_safety_configs(kw, pf, passing: bool) -> None:
    _value, ok = dash._eval_safety_configs(kw, pf)
    assert ok is passing


# --- registry integrity ----------------------------------------------------


def test_registry_has_nine_criteria_mapped_to_callables() -> None:
    assert len(dash._CRITERIA) == 9
    assert [c[0] for c in dash._CRITERIA] == [str(i) for i in range(1, 10)]
    for _num, _name, _threshold, fn in dash._CRITERIA:
        assert callable(fn)
