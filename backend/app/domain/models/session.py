"""Session model — `docs/schemas/session.schema.json`."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.models._base import WireModel


class Session(WireModel):
    session_id: str
    tenant_id: str
    user_id: str
    session_hash: str
    turn_count: int = Field(ge=0)
    created_at: datetime
    last_query_at: datetime | None = None
    expires_at: datetime | None = None
