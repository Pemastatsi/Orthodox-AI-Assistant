"""Baseline file IO for the retrieval-eval suite (`docs/contracts/retrieval-eval-suite.md`).

A baseline records the *last passing scores per gold-set version* for a tenant, at
``baselines/<tenant_id>.json``. ``compare_to_baseline`` (metrics.py) gates a new run against it:
a metric may not drop more than ε below its baseline. The first passing run for a version
establishes the baseline — a **deliberate owner-only action** (it mirrors `ModelRoute`
certification authority), so ``write_baseline`` is only ever called from the owner-gated CLI path,
never automatically from ``run_eval``.

File shape (camelCase wire style, like the rest of the repo):

    {
      "tenantId": "tenant_smoke",
      "versions": {
        "2026-05-29.1": {
          "scores": {"recall_at_6": 1.0, "mrr": 1.0, ...},
          "establishedBy": "usr_founder",
          "establishedAt": "2026-05-29T12:00:00+00:00"
        }
      }
    }

Versions are not commensurable (the contract's Forbidden Patterns): each gold-set version keeps its
own baseline, and a run is only ever compared against the baseline for its *own* version.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

# No tenant_smoke baseline is committed here on purpose: the offline smoke run is therefore always a
# first run (it passes with no baseline to regress against), which keeps the free CI path green.
PACKAGE_BASELINES_DIR = Path(__file__).parent / "baselines"


def baseline_file(tenant_id: str, *, baselines_dir: Path | None = None) -> Path:
    return (baselines_dir or PACKAGE_BASELINES_DIR) / f"{tenant_id}.json"


def load_baseline(
    tenant_id: str, version: str, *, baselines_dir: Path | None = None
) -> dict[str, float] | None:
    """Return the pinned baseline scores for ``(tenant_id, version)``, or ``None`` if none exists.

    ``None`` means "no baseline yet" — ``compare_to_baseline`` treats that as a first-run pass.
    """
    path = baseline_file(tenant_id, baselines_dir=baselines_dir)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    entry = data.get("versions", {}).get(version)
    if not entry or not entry.get("scores"):
        return None
    return {metric: float(value) for metric, value in entry["scores"].items()}


def write_baseline(
    tenant_id: str,
    version: str,
    scores: dict[str, float],
    *,
    established_by: str,
    baselines_dir: Path | None = None,
) -> Path:
    """Establish/replace the baseline for ``(tenant_id, version)``. Owner-only at the call site.

    Merges into any existing ``baselines/<tenant_id>.json`` so other versions are preserved.
    Returns the file path written.
    """
    path = baseline_file(tenant_id, baselines_dir=baselines_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = (
        json.loads(path.read_text(encoding="utf-8"))
        if path.exists()
        else {"tenantId": tenant_id, "versions": {}}
    )
    data.setdefault("tenantId", tenant_id)
    data.setdefault("versions", {})[version] = {
        "scores": {metric: float(value) for metric, value in scores.items()},
        "establishedBy": established_by,
        "establishedAt": datetime.now(UTC).isoformat(),
    }
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


__all__ = [
    "PACKAGE_BASELINES_DIR",
    "baseline_file",
    "load_baseline",
    "write_baseline",
]
