"""Unit tests for the audit-event recorder (scripts/record_audit_event.py).

These exercise the pure helpers (hashing, version read, sign-off validation, CSV parsing) and the
CLI dry-run path — no database or SQLAlchemy install is required. The DB INSERT itself is exercised
by CI's Postgres-backed run; the row-shaping and validation logic is what we pin here.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import Any

import pytest

# Load the standalone script (it lives under scripts/, not an importable package).
_MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "record_audit_event.py"
_spec = importlib.util.spec_from_file_location("record_audit_event", _MODULE_PATH)
assert _spec and _spec.loader
rec: Any = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rec)


# --- URL normalisation (shared shape with the dashboard) -------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("postgresql://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ],
)
def test_normalize_db_url(raw: str, expected: str) -> None:
    assert rec._normalize_db_url(raw) == expected


# --- content hashing + version read (#9) -----------------------------------


def test_sha256_file(tmp_path: Path) -> None:
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello world")
    assert rec._sha256_file(p) == hashlib.sha256(b"hello world").hexdigest()


def test_safety_config_details(tmp_path: Path) -> None:
    kw = tmp_path / "kw.yaml"
    kw.write_text('version: "2026-06-01.1"\nrules: []\n', encoding="utf-8")
    pf = tmp_path / "pf.yaml"
    pf.write_text('version: "2026-06-02.1"\nrules: []\n', encoding="utf-8")

    details = rec._safety_config_details(kw, pf)

    assert details["sensitivity_keywords_version"] == "2026-06-01.1"
    assert details["pastoral_filters_version"] == "2026-06-02.1"
    assert details["sensitivity_keywords_sha256"] == hashlib.sha256(kw.read_bytes()).hexdigest()
    assert details["pastoral_filters_sha256"] == hashlib.sha256(pf.read_bytes()).hexdigest()
    assert set(details) == {
        "sensitivity_keywords_version",
        "pastoral_filters_version",
        "sensitivity_keywords_sha256",
        "pastoral_filters_sha256",
    }


def test_yaml_version_requires_version(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("rules: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        rec._yaml_version(bad)


# --- founder sign-off validation (#6) --------------------------------------


@pytest.mark.parametrize(
    "role,runs,cats,valid",
    [
        ("owner", 20, 3, True),
        ("owner", 25, 5, True),
        ("owner", 19, 3, False),  # too few reviewed runs
        ("owner", 20, 2, False),  # too few distinct categories
        ("member", 20, 3, False),  # not an owner
    ],
)
def test_validate_signoff(role: str, runs: int, cats: int, valid: bool) -> None:
    errors = rec._validate_signoff(
        role, [f"run_{i}" for i in range(runs)], [f"cat_{i}" for i in range(cats)]
    )
    assert (errors == []) is valid


def test_validate_signoff_counts_distinct_categories() -> None:
    # Five entries but only two distinct values -> still under the >=3 threshold.
    errors = rec._validate_signoff(
        "owner", [f"run_{i}" for i in range(20)], ["a", "a", "b", "b", "a"]
    )
    assert errors != []


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, []),
        ("", []),
        ("a", ["a"]),
        ("a, b ,c", ["a", "b", "c"]),
        (" , ,", []),
    ],
)
def test_split_csv(raw: str | None, expected: list[str]) -> None:
    assert rec._split_csv(raw) == expected


# --- CLI dry-run paths (no DB) ---------------------------------------------


def test_main_safety_suite_passed_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    rc = rec.main(
        ["safety-suite-passed", "--tenant", "tn_x", "--actor-user", "usr_x", "--dry-run"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert '"action": "ci_safety_suite_passed"' in out
    assert '"passed": true' in out
    assert "dry-run" in out


def test_main_tenant_isolation_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    rc = rec.main(
        [
            "tenant-isolation-passed",
            "--tenant",
            "tn_x",
            "--actor-user",
            "usr_x",
            "--dry-run",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert '"action": "ci_tenant_isolation_passed"' in out
    assert '"result": "pass"' in out


def test_main_founder_signoff_valid_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    runs = ",".join(f"run_{i}" for i in range(20))
    rc = rec.main(
        [
            "founder-signoff",
            "--tenant",
            "tn_x",
            "--actor-user",
            "usr_owner",
            "--reviewed-run-ids",
            runs,
            "--sensitivity-categories",
            "normal,pastoral_advice,doctrinal",
            "--dry-run",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert '"action": "founder_phase2_signoff"' in out


def test_main_founder_signoff_validation_blocks_write(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Only 2 reviewed runs (< 20) -> validation fails -> exit 2, even with --dry-run.
    rc = rec.main(
        [
            "founder-signoff",
            "--tenant",
            "tn_x",
            "--actor-user",
            "usr_owner",
            "--reviewed-run-ids",
            "run_1,run_2",
            "--sensitivity-categories",
            "a,b,c",
            "--dry-run",
        ]
    )
    err = capsys.readouterr().err
    assert rc == 2
    assert "reviewed run ids" in err


def test_main_requires_db_url_when_not_dry_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = rec.main(
        ["safety-suite-passed", "--tenant", "tn_x", "--actor-user", "usr_x"]
    )
    err = capsys.readouterr().err
    assert rc == 2
    assert "--db-url is required" in err
