"""Pydantic domain models mirroring `docs/schemas/`.

Each schema in `docs/schemas/` has a 1:1 model file here. Field names are snake_case in Python
and serialize to/from camelCase JSON via `pydantic.alias_generators.to_camel` configured on
`WireModel` (see `_base.py`)."""

from app.domain.models.answer_mode import AnswerMode
from app.domain.models.api_error import ApiError
from app.domain.models.audit_entry import AuditEntry
from app.domain.models.billing_usage import BillingUsage
from app.domain.models.calendar_profile import CalendarProfile
from app.domain.models.chunk import Chunk, ChunkLanguage, Visibility
from app.domain.models.classified_query import (
    ClassifiedQuery,
    ConfidenceTier,
    Handling,
    RiskFlag,
    SensitivityPrimary,
)
from app.domain.models.evidence_packet import AdmittedChunk, EvidencePacket, LineageEdge
from app.domain.models.flagged_query import FlaggedQuery, FlagReason
from app.domain.models.ingest_job import IngestJob, IngestJobProgress, IngestJobStatus
from app.domain.models.model_route import (
    CertificationStatus,
    ModelRoute,
    RouteProvider,
    RoutePurpose,
)
from app.domain.models.parsed_block import BlockType, ParsedBlock
from app.domain.models.principal import DataRegion, Principal, Role, Scope
from app.domain.models.progress_event import (
    DoneVariant,
    ErrorVariant,
    ProgressEvent,
    ProgressStage,
    ProgressVariant,
)
from app.domain.models.retrieval_eval_run import (
    RetrievalConfigLabel,
    RetrievalEvalPurpose,
    RetrievalEvalRegression,
    RetrievalEvalRun,
)
from app.domain.models.retrieval_plan import (
    RetrievalBoost,
    RetrievalConfig,
    RetrievalFilters,
    RetrievalPlan,
    RetrievalRerankerConfig,
)
from app.domain.models.run_trace import RunTrace, RunTraceUsage, Stage, StageName, StageOutcome
from app.domain.models.scored_chunk import ScoredChunk
from app.domain.models.session import Session
from app.domain.models.source import (
    DigitizationProvenance,
    Source,
    SourceLanguage,
    SourceType,
)
from app.domain.models.tenant import Tenant, TenantConfig, TenantDataRegion, TenantStatus
from app.domain.models.user import User, UserStatus
from app.domain.models.verified_response import (
    Citation,
    CorpusOrigin,
    Reframing,
    Verification,
    VerifiedResponse,
    VerifiedResponseUsage,
)

__all__ = [
    "AdmittedChunk",
    "AnswerMode",
    "ApiError",
    "AuditEntry",
    "BillingUsage",
    "BlockType",
    "CalendarProfile",
    "CertificationStatus",
    "Chunk",
    "ChunkLanguage",
    "Citation",
    "ClassifiedQuery",
    "ConfidenceTier",
    "CorpusOrigin",
    "DataRegion",
    "DigitizationProvenance",
    "DoneVariant",
    "ErrorVariant",
    "EvidencePacket",
    "FlagReason",
    "FlaggedQuery",
    "Handling",
    "IngestJob",
    "IngestJobProgress",
    "IngestJobStatus",
    "LineageEdge",
    "ModelRoute",
    "ParsedBlock",
    "Principal",
    "ProgressEvent",
    "ProgressStage",
    "ProgressVariant",
    "Reframing",
    "RetrievalBoost",
    "RetrievalConfig",
    "RetrievalConfigLabel",
    "RetrievalEvalPurpose",
    "RetrievalEvalRegression",
    "RetrievalEvalRun",
    "RetrievalFilters",
    "RetrievalPlan",
    "RetrievalRerankerConfig",
    "RiskFlag",
    "Role",
    "RouteProvider",
    "RoutePurpose",
    "RunTrace",
    "RunTraceUsage",
    "Scope",
    "ScoredChunk",
    "SensitivityPrimary",
    "Session",
    "Source",
    "SourceLanguage",
    "SourceType",
    "Stage",
    "StageName",
    "StageOutcome",
    "Tenant",
    "TenantConfig",
    "TenantDataRegion",
    "TenantStatus",
    "User",
    "UserStatus",
    "Verification",
    "VerifiedResponse",
    "VerifiedResponseUsage",
    "Visibility",
]
