"""IngestJob model — `docs/schemas/ingest-job.schema.json`."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.models._base import WireModel

IngestJobStatus = Literal[
    "queued",
    "extracting",
    "chunking",
    "embedding",
    "awaiting_review",
    "completed",
    "failed",
    "cancelled",
]


class IngestJobProgress(WireModel):
    stage: str
    completed: int = Field(ge=0)
    total: int = Field(ge=0)


class IngestJob(WireModel):
    job_id: str
    tenant_id: str
    user_id: str
    source_id: str
    status: IngestJobStatus
    created_at: datetime
    progress: IngestJobProgress | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
