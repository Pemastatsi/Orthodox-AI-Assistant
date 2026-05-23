"""Tenant model — `docs/schemas/tenant.schema.json`."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.models._base import WireModel
from app.domain.models.calendar_profile import CalendarProfile

TenantStatus = Literal["active", "suspended", "trial", "closed"]
TenantDataRegion = Literal["us", "eu"]


class TenantConfig(WireModel):
    tone: str | None = None
    default_answer_length: str | None = None
    citation_style: str | None = None
    calendar_profile: CalendarProfile | None = None
    starter_corpus_enabled: bool | None = None
    sensitive_handling_strictness: str | None = None
    disclaimer_template_id: str | None = None
    ecclesiastical_jurisdiction: str | None = None
    ecclesiastical_jurisdiction_other: str | None = None
    config_version: str | None = None
    corpus_version: str | None = None


class Tenant(WireModel):
    tenant_id: str
    name: str = Field(min_length=1)
    clerk_org_id: str
    status: TenantStatus
    data_region: TenantDataRegion
    created_at: datetime
    stripe_customer_id: str | None = None
    starter_corpus_enabled: bool = False
    config: TenantConfig | None = None
    updated_at: datetime | None = None
