"""Principal model — `docs/schemas/principal.schema.json`."""

from __future__ import annotations

from typing import Literal

from app.domain.models._base import WireModel

Role = Literal["member", "scholar", "content_manager", "admin", "owner"]
Scope = Literal[
    "query:read",
    "corpus:read",
    "corpus:write",
    "corpus:approve",
    "admin:queries:read",
    "admin:flagged:read",
    "admin:audit:read",
    "admin:raw_sensitive:read",
    "model_route:certify",
    "tenant:config:read",
    "tenant:config:write",
    "billing:read",
]
DataRegion = Literal["us", "eu"]


class Principal(WireModel):
    user_id: str
    clerk_user_id: str
    tenant_id: str
    clerk_org_id: str
    role: Role
    scopes: list[Scope]
    data_region: DataRegion = "us"
