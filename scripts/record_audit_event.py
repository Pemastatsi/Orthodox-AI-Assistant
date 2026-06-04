"""Record a Phase 1 -> 2 exit-criteria audit attestation into `audit_entries`.

Sibling to `scripts/exit_criteria_dashboard.py` (which READS these rows). Four of the nine
Phase-1->2 exit criteria are satisfied by founder/ops-written `audit_entries` rows; this CLI is
the supported writer for them. By design there are no CI->DB credentials: an operator runs this
after observing the relevant CI/check result, and the founder runs the Phase-2 sign-off.

Subcommands (criterion -> action):
  safety-config-approved    #9  action=safety_config_approved     resource_type=safety_config
  safety-suite-passed       #1  action=ci_safety_suite_passed     resource_type=ci_check
  tenant-isolation-passed   #5  action=ci_tenant_isolation_passed resource_type=ci_check
  founder-signoff           #6  action=founder_phase2_signoff     resource_type=tenant

Each writes one append-only row. `audit_entries.tenant_id` and `actor_user_id` are FK-constrained,
so --tenant and --actor-user must reference existing rows. Use --dry-run to print the row JSON
without writing (and without needing a database).

Usage:
  python scripts/record_audit_event.py safety-config-approved \\
      --db-url postgresql://user:pass@host/db --tenant tn_orthodoxethos --actor-user usr_founder
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:  # SQLAlchemy + a sync driver are only needed to actually write the row.
    from sqlalchemy import create_engine, text
except ImportError:  # pragma: no cover - import guard so --help / unit tests work without the dep
    create_engine = None  # type: ignore[assignment]
    text = None  # type: ignore[assignment]

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_KEYWORDS = _REPO_ROOT / "config" / "sensitivity_keywords.yaml"
_DEFAULT_FILTERS = _REPO_ROOT / "config" / "pastoral_filters.yaml"

# Mirrors the Founder Review Protocol thresholds in phase1-implementation-contract.md (#6).
_SIGNOFF_MIN_RUNS = 20
_SIGNOFF_MIN_CATEGORIES = 3
_DEFAULT_CHECKLIST_VERSION = "phase2-signoff-2026-05-02.1"


# ---------------------------------------------------------------------------
# Pure helpers (no DB) — unit-tested.
# ---------------------------------------------------------------------------


def _normalize_db_url(db_url: str) -> str:
    """Pin the sync psycopg (v3) driver, matching exit_criteria_dashboard.py."""
    for prefix in ("postgresql://", "postgres://"):
        if db_url.startswith(prefix):
            return "postgresql+psycopg://" + db_url[len(prefix) :]
    return db_url


def _sha256_file(path: str | Path) -> str:
    """Hex SHA-256 of the file's raw bytes (pins approved config content, not just version)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _yaml_version(path: str | Path) -> str:
    import yaml

    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("version"), str):
        raise ValueError(f"{path}: missing string 'version'")
    return raw["version"]


def _safety_config_details(
    keywords_path: str | Path, filters_path: str | Path
) -> dict[str, str]:
    """`details` payload for #9: approved config versions + content hashes."""
    return {
        "sensitivity_keywords_version": _yaml_version(keywords_path),
        "pastoral_filters_version": _yaml_version(filters_path),
        "sensitivity_keywords_sha256": _sha256_file(keywords_path),
        "pastoral_filters_sha256": _sha256_file(filters_path),
    }


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _validate_signoff(
    actor_role: str, reviewed_run_ids: list[str], sensitivity_categories: list[str]
) -> list[str]:
    """Return validation errors (empty == valid), per the #6 Founder Review Protocol."""
    errors: list[str] = []
    if actor_role != "owner":
        errors.append(f"--actor-role must be 'owner' for a founder sign-off (got {actor_role!r})")
    if len(reviewed_run_ids) < _SIGNOFF_MIN_RUNS:
        errors.append(
            f"need >={_SIGNOFF_MIN_RUNS} reviewed run ids (got {len(reviewed_run_ids)})"
        )
    distinct = len(set(sensitivity_categories))
    if distinct < _SIGNOFF_MIN_CATEGORIES:
        errors.append(
            f"need >={_SIGNOFF_MIN_CATEGORIES} distinct sensitivity categories (got {distinct})"
        )
    return errors


# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------


def _insert_audit(
    db_url: str,
    *,
    tenant_id: str,
    actor_user_id: str,
    actor_role: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, object],
) -> str:
    """Append one `audit_entries` row (column list mirrors AuditRepository.insert)."""
    if create_engine is None:  # pragma: no cover - guarded import
        raise RuntimeError(
            "SQLAlchemy + psycopg are required to write "
            "(pip install 'sqlalchemy>=2' 'psycopg[binary]')."
        )
    import ulid

    audit_id = f"aud_{ulid.new()!s}"
    engine = create_engine(_normalize_db_url(db_url), future=True, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO audit_entries (
                    audit_id, tenant_id, actor_user_id, actor_role, action, resource_type,
                    resource_id, details, ip_address, occurred_at
                ) VALUES (
                    :audit_id, :tenant_id, :actor_user_id, :actor_role, :action,
                    :resource_type, :resource_id, CAST(:details AS jsonb), NULL, now()
                )
                """
            ),
            {
                "audit_id": audit_id,
                "tenant_id": tenant_id,
                "actor_user_id": actor_user_id,
                "actor_role": actor_role,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "details": json.dumps(details, ensure_ascii=False, default=str),
            },
        )
    return audit_id


def _emit(
    *,
    tenant_id: str,
    actor_user_id: str,
    actor_role: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, object],
    dry_run: bool,
    db_url: str | None,
) -> int:
    """Print the row JSON, then write it unless --dry-run."""
    row = {
        "tenant_id": tenant_id,
        "actor_user_id": actor_user_id,
        "actor_role": actor_role,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details,
    }
    print(json.dumps(row, ensure_ascii=False, indent=2, default=str))
    if dry_run:
        print("\n[dry-run] not written.")
        return 0
    if not db_url:
        print("\nERROR: --db-url is required unless --dry-run.", file=sys.stderr)
        return 2
    audit_id = _insert_audit(
        db_url,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )
    print(f"\nWrote audit_entries row {audit_id}.")
    return 0


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def _cmd_safety_config_approved(args: argparse.Namespace) -> int:
    details: dict[str, object] = dict(
        _safety_config_details(args.sensitivity_keywords, args.pastoral_filters)
    )
    return _emit(
        tenant_id=args.tenant,
        actor_user_id=args.actor_user,
        actor_role=args.actor_role,
        action="safety_config_approved",
        resource_type="safety_config",
        resource_id=args.resource_id,
        details=details,
        dry_run=args.dry_run,
        db_url=args.db_url,
    )


def _cmd_safety_suite_passed(args: argparse.Namespace) -> int:
    details: dict[str, object] = {"passed": args.passed}
    if args.commit:
        details["commit"] = args.commit
    if args.note:
        details["note"] = args.note
    return _emit(
        tenant_id=args.tenant,
        actor_user_id=args.actor_user,
        actor_role=args.actor_role,
        action="ci_safety_suite_passed",
        resource_type="ci_check",
        resource_id=args.resource_id,
        details=details,
        dry_run=args.dry_run,
        db_url=args.db_url,
    )


def _cmd_tenant_isolation_passed(args: argparse.Namespace) -> int:
    details: dict[str, object] = {"result": args.result}
    if args.commit:
        details["commit"] = args.commit
    return _emit(
        tenant_id=args.tenant,
        actor_user_id=args.actor_user,
        actor_role=args.actor_role,
        action="ci_tenant_isolation_passed",
        resource_type="ci_check",
        resource_id=args.resource_id,
        details=details,
        dry_run=args.dry_run,
        db_url=args.db_url,
    )


def _cmd_founder_signoff(args: argparse.Namespace) -> int:
    reviewed = _split_csv(args.reviewed_run_ids)
    categories = _split_csv(args.sensitivity_categories)
    errors = _validate_signoff(args.actor_role, reviewed, categories)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 2
    details: dict[str, object] = {
        "reviewedRunIds": reviewed,
        "answerModesCovered": _split_csv(args.answer_modes),
        "sensitivityCategoriesCovered": categories,
        "concerns": args.concerns or "",
        "checklistVersion": args.checklist_version,
    }
    return _emit(
        tenant_id=args.tenant,
        actor_user_id=args.actor_user,
        actor_role=args.actor_role,
        action="founder_phase2_signoff",
        resource_type="tenant",
        resource_id=args.resource_id or args.tenant,
        details=details,
        dry_run=args.dry_run,
        db_url=args.db_url,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--db-url", metavar="POSTGRES_URL", help="PostgreSQL URL (required unless --dry-run)"
    )
    common.add_argument("--tenant", required=True, help="tenant_id (FK to tenants)")
    common.add_argument("--actor-user", required=True, help="actor_user_id (FK to users)")
    common.add_argument("--actor-role", default="owner", help="actor role (default: owner)")
    common.add_argument(
        "--dry-run", action="store_true", help="print the row JSON without writing"
    )

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p9 = sub.add_parser(
        "safety-config-approved", parents=[common], help="#9 safety_config_approved"
    )
    p9.add_argument("--sensitivity-keywords", default=str(_DEFAULT_KEYWORDS))
    p9.add_argument("--pastoral-filters", default=str(_DEFAULT_FILTERS))
    p9.add_argument("--resource-id", default="safety_config")
    p9.set_defaults(func=_cmd_safety_config_approved)

    p1 = sub.add_parser(
        "safety-suite-passed", parents=[common], help="#1 ci_safety_suite_passed"
    )
    grp = p1.add_mutually_exclusive_group()
    grp.add_argument("--passed", dest="passed", action="store_true", default=True)
    grp.add_argument("--failed", dest="passed", action="store_false")
    p1.add_argument("--commit", default=None, help="git SHA the attestation covers")
    p1.add_argument("--note", default=None)
    p1.add_argument("--resource-id", default="safety-suite")
    p1.set_defaults(func=_cmd_safety_suite_passed)

    p5 = sub.add_parser(
        "tenant-isolation-passed", parents=[common], help="#5 ci_tenant_isolation_passed"
    )
    p5.add_argument("--result", choices=["pass", "fail"], default="pass")
    p5.add_argument("--commit", default=None, help="git SHA the attestation covers")
    p5.add_argument("--resource-id", default="tenant-isolation")
    p5.set_defaults(func=_cmd_tenant_isolation_passed)

    p6 = sub.add_parser(
        "founder-signoff", parents=[common], help="#6 founder_phase2_signoff"
    )
    p6.add_argument("--reviewed-run-ids", required=True, help="comma-separated run ids (>=20)")
    p6.add_argument(
        "--sensitivity-categories", required=True, help="comma-separated (>=3 distinct)"
    )
    p6.add_argument("--answer-modes", default=None, help="comma-separated answer modes seen")
    p6.add_argument("--concerns", default=None)
    p6.add_argument("--checklist-version", default=_DEFAULT_CHECKLIST_VERSION)
    p6.add_argument("--resource-id", default=None, help="reviewed tenant (defaults to --tenant)")
    p6.set_defaults(func=_cmd_founder_signoff)

    args = parser.parse_args(argv)
    func = args.func  # set via set_defaults on each subparser
    return int(func(args))


if __name__ == "__main__":
    sys.exit(main())
