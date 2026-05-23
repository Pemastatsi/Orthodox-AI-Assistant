"""ProgressEvent model — `docs/schemas/progress-event.schema.json` (SSE wire payloads)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from app.domain.models._base import WireModel
from app.domain.models.api_error import ApiError
from app.domain.models.verified_response import VerifiedResponse

ProgressStage = Literal[
    "a1_a2_query_analyzer",
    "a3_retrieval",
    "a4_evidence_packager",
    "a5_composer",
    "a6_verifier",
]


class ProgressVariant(WireModel):
    type: Literal["progress"] = "progress"
    stage: ProgressStage
    elapsed_ms: int = Field(ge=0)
    model_route_id: str | None = None


class DoneVariant(WireModel):
    type: Literal["done"] = "done"
    response: VerifiedResponse


class ErrorVariant(WireModel):
    type: Literal["error"] = "error"
    error: ApiError


ProgressEvent = Annotated[
    ProgressVariant | DoneVariant | ErrorVariant,
    Field(discriminator="type"),
]
