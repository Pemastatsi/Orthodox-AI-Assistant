"""AuditEntry model — `docs/schemas/audit-entry.schema.json`."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.domain.models._base import WireModel


class AuditEntry(WireModel):
    audit_id: str
    tenant_id: str
    actor_user_id: str
    actor_role: str
    action: str
    resource_type: str
    resource_id: str
    occurred_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = None
