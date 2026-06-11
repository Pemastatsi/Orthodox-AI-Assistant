"""Usage metering — resolve the usage-record id stamped on `billing_usage`.

ADR-0005 §1 meters served answers to billing. `BILLING_MODE` (see `core/config.py`) selects the
backend:

- ``local`` (default): a deterministic, clearly-labeled non-Stripe id. The metering path is fully
  functional — `billing_usage.served_answer_count` accrues and the row carries a usage-record id —
  without any Stripe account or real charge. This is what the private beta runs on and what makes
  the Phase-1 operational-basics exit criterion satisfiable.
- ``stripe``: usage is reported out-of-band by the periodic billing reporter so the request hot
  path makes no paid API call; the inline resolver returns ``None`` in this mode. Flipping it on
  (live keys + ``tenants.stripe_customer_id`` + the reporter) is the monetization step and needs
  no further request-path code.
"""

from __future__ import annotations

from datetime import datetime


def local_usage_record_id(tenant_id: str, period_start: datetime) -> str:
    """Deterministic non-Stripe usage-record id, one per (tenant, billing month)."""
    return f"unmetered_{period_start:%Y%m}_{tenant_id}"


def resolve_inline_usage_record_id(
    billing_mode: str, *, tenant_id: str, period_start: datetime
) -> str | None:
    """Usage-record id to stamp on `billing_usage` at serve time, or ``None`` to defer.

    ``local`` returns the synthetic id (see module docstring); ``stripe`` (and any unknown mode)
    returns ``None`` so the periodic reporter owns the real metering call off the hot path.
    """
    if billing_mode == "local":
        return local_usage_record_id(tenant_id, period_start)
    return None


__all__ = ["local_usage_record_id", "resolve_inline_usage_record_id"]
