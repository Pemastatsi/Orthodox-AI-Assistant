"""ApiError model — `docs/schemas/api-error.schema.json`."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.domain.models._base import WireModel


class ApiError(WireModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    message: str
    trace_id: str
    details: dict[str, Any] | None = None
    retryable: bool = False
    retry_after_seconds: int | None = Field(default=None, ge=0)
