"""ModelRoute model — `docs/schemas/model-route.schema.json`."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.domain.models._base import WireModel

RoutePurpose = Literal[
    "query_analyzer", "compose", "verifier_judge", "embedding", "retrieval_eval_judge"
]
RouteProvider = Literal["anthropic", "openai", "bge"]
CertificationStatus = Literal["draft", "experiment", "certified", "deprecated"]


class ModelRoute(WireModel):
    route_id: str = Field(pattern=r"^[a-z][a-z0-9_]+@[0-9]{4}-[0-9]{2}-[0-9]{2}\.[0-9]+$")
    purpose: RoutePurpose
    provider: RouteProvider
    model: str
    prompt_version: str
    schema_version: str
    certification_status: CertificationStatus
    created_at: datetime
    supports_prompt_cache: bool = False
    supports_batch: bool = False
    supports_json_mode: bool = False
    safety_suite_run_id: str | None = None
    retrieval_eval_run_id: str | None = None
    certified_by: str | None = None
    certified_at: datetime | None = None
    deprecated_at: datetime | None = None
