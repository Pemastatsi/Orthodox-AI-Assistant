"""User model — `docs/schemas/user.schema.json`."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import EmailStr

from app.domain.models._base import WireModel
from app.domain.models.principal import Role

UserStatus = Literal["active", "invited", "disabled"]


class User(WireModel):
    user_id: str
    clerk_user_id: str
    tenant_id: str
    role: Role
    status: UserStatus
    created_at: datetime
    email: EmailStr | None = None
    display_name: str | None = None
    last_seen_at: datetime | None = None
