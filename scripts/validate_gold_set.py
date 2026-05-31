#!/usr/bin/env python3
"""Gold-set curation validator (T-009 Phase-A — gated item #1 prep).

Curating the real, founder/content-manager-owned gold set is a **Confidential**, domain-expert
action this tool does not perform. What it *does* is make that curation safe: it validates a
candidate gold-set file against (a) the JSON schema, (b) the contract's structural curation rules,
and — when a corpus DB is reachable — (c) the *live corpus*, so a curated case can never silently
gate on a chunk that doesn't exist, isn't approved, or belongs to another tenant.

Two layers, so the cheap one runs anywhere:

  * **Offline (always):** schema shape, id/version patterns, `RE-NNN` uniqueness,
    `minimallySufficientChunkIds ⊆ expectedChunkIds`, the forbidden-content rules
    (`reviewedBy` non-empty; hard-trigger sensitivities live in the safety suite, not here).
  * **Live corpus (`--check-corpus`, needs Postgres):** every referenced `chunk_id` exists for
    `tenantId`, is `approved = true`, and (warn) was curated against the current `corpusVersion`.
    This is the §Curation Rules "only against approved chunks" invariant, enforced mechanically.

Run from `backend/` so `app.*` imports resolve (same convention as run_retrieval_eval.py):

    uv run python ../scripts/validate_gold_set.py \
        ../backend/tests/retrieval_eval/gold_sets/tenant_smoke/2026-05-29.1.json
    uv run python ../scripts/validate_gold_set.py --check-corpus <file>   # + live corpus (DB)

Exit code 0 = valid; 1 = validation errors; 2 = usage error. Designed to be wired into CI for
real tenant gold sets later, and to be the pre-flight a curator runs before a certification PR.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Hard-trigger sensitivities are forbidden in a retrieval-eval gold set — they belong to the safety
# suite (retrieval-eval-suite.md §Curation Rules / §Forbidden Patterns). sensitivityPrimary never
# encodes a hard trigger directly, but a curator could mislabel; we reject the obvious aliases.
_FORBIDDEN_SENSITIVITY_ALIASES = {"self_harm", "medical_emergency"}
_VERSION_RE = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}\.[0-9]+$"
_CASE_ID_RE = r"^RE-[0-9]+$"


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    corpus_checked: bool = False
    case_count: int = 0

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_offline(data: dict) -> ValidationReport:
    """Schema + structural curation rules. Pure; no DB. Mirrors retrieval-eval-suite.md exactly."""
    report = ValidationReport()

    # The pydantic GoldSet model already enforces the field shape; reuse it for the heavy lifting,
    # then layer the cross-field curation rules the model doesn't express.
    from tests.retrieval_eval.harness import GoldSet  # noqa: PLC0415

    payload = {k: v for k, v in data.items() if k != "$schema"}
    try:
        gold_set = GoldSet.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - surface the pydantic message as a validation error
        report.error(f"schema: {exc}")
        return report

    report.case_count = len(gold_set.cases)

    if not re.match(_VERSION_RE, gold_set.version):
        report.error(f"version {gold_set.version!r} must match {_VERSION_RE}")
    if not gold_set.reviewed_by:
        report.error("reviewedBy must be non-empty (contract §Curation Rules)")

    seen_ids: set[str] = set()
    for case in gold_set.cases:
        if not re.match(_CASE_ID_RE, case.id):
            report.error(f"case id {case.id!r} must match {_CASE_ID_RE}")
        if case.id in seen_ids:
            report.error(f"duplicate case id {case.id!r} (ids are never reused)")
        seen_ids.add(case.id)

        expected = set(case.expected_chunk_ids)
        minimal = set(case.minimally_sufficient_chunk_ids)
        if not minimal <= expected:
            report.error(
                f"{case.id}: minimallySufficientChunkIds ⊄ expectedChunkIds "
                f"(extra: {sorted(minimal - expected)})"
            )
        if case.sensitivity_primary in _FORBIDDEN_SENSITIVITY_ALIASES:
            report.error(
                f"{case.id}: sensitivityPrimary {case.sensitivity_primary!r} is a hard trigger — "
                "those live in the safety suite, not the retrieval-eval gold set"
            )
        if len(expected) != len(case.expected_chunk_ids):
            report.warn(f"{case.id}: expectedChunkIds has duplicates")

    return report


async def check_corpus(data: dict, report: ValidationReport) -> None:
    """Verify every referenced chunk_id exists + is approved for the tenant (needs Postgres).

    Appends errors/warnings to `report`. Skips with a warning if no DB is reachable so the tool
    degrades gracefully when run outside an environment with the corpus.
    """
    from app.domain.repositories._base import (  # noqa: PLC0415
        dispose_engine,
        init_engine,
        session_scope,
    )
    from sqlalchemy import text

    tenant_id = data["tenantId"]
    curated_corpus_version = data.get("corpusVersionAtCuration")
    referenced: set[str] = set()
    for case in data["cases"]:
        referenced.update(case["expectedChunkIds"])
        referenced.update(case["minimallySufficientChunkIds"])
    if not referenced:
        return

    init_engine()
    try:
        async with session_scope() as session:
            result = await session.execute(
                text(
                    """
                    SELECT chunk_id, approved, corpus_version
                    FROM chunks
                    WHERE tenant_id = :tenant_id AND chunk_id = ANY(:ids)
                    """
                ),
                {"tenant_id": tenant_id, "ids": list(referenced)},
            )
            rows = {r["chunk_id"]: r for r in result.mappings().all()}
    finally:
        await dispose_engine()

    report.corpus_checked = True
    missing = sorted(referenced - rows.keys())
    for chunk_id in missing:
        report.error(f"corpus: chunk {chunk_id!r} not found for tenant {tenant_id!r}")
    for chunk_id, row in rows.items():
        if not row["approved"]:
            report.error(
                f"corpus: chunk {chunk_id!r} is NOT approved — gold sets may only reference "
                "approved chunks (contract §Curation Rules)"
            )
        if (
            curated_corpus_version
            and row["corpus_version"]
            and row["corpus_version"] != curated_corpus_version
        ):
            report.warn(
                f"corpus: chunk {chunk_id!r} is at corpusVersion {row['corpus_version']!r}, "
                f"but the gold set was curated against {curated_corpus_version!r}"
            )


def _print_report(path: Path, report: ValidationReport) -> None:
    print()
    print(f"Gold-set validation — {path.name}")
    print("=" * 72)
    print(
        f"cases: {report.case_count}   "
        f"corpus check: {'ran' if report.corpus_checked else 'skipped (offline)'}"
    )
    print("-" * 72)
    for warning in report.warnings:
        print(f"  WARN  {warning}")
    for err in report.errors:
        print(f"  FAIL  {err}")
    print("-" * 72)
    print("Result: VALID" if report.ok else f"Result: INVALID ({len(report.errors)} error(s))")
    print()


async def _amain(args: argparse.Namespace) -> int:
    path = Path(args.gold_set_file)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2
    data = json.loads(path.read_text(encoding="utf-8"))

    report = validate_offline(data)
    # Only reach for the corpus if the offline shape is sound (otherwise data["cases"] etc. may
    # not even be well-formed).
    if args.check_corpus and report.ok:
        try:
            await check_corpus(data, report)
        except Exception as exc:  # noqa: BLE001 - a DB outage shouldn't crash the validator
            report.warn(f"corpus check skipped: {exc}")

    _print_report(path, report)
    return 0 if report.ok else 1


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a retrieval-eval gold-set file against the schema, the contract's curation "
            "rules, and (optionally) the live corpus."
        )
    )
    parser.add_argument("gold_set_file", help="Path to the gold-set JSON file.")
    parser.add_argument(
        "--check-corpus",
        action="store_true",
        help="Also verify every chunk_id exists + is approved for the tenant (needs Postgres).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(_parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
