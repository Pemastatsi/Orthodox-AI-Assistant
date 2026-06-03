from enum import StrEnum
from typing import Any


class ApiErrorCode(StrEnum):
    """Canonical error codes per docs/contracts/error-taxonomy.md."""

    AUTH_MISSING_TOKEN = "auth_missing_token"
    AUTH_INVALID_TOKEN = "auth_invalid_token"
    AUTH_MISSING_ORG = "auth_missing_org"
    TENANT_NOT_FOUND = "tenant_not_found"
    TENANT_INACTIVE = "tenant_inactive"
    TENANT_MISMATCH = "tenant_mismatch"
    FORBIDDEN_ROLE = "forbidden_role"
    FORBIDDEN_VISIBILITY = "forbidden_visibility"
    VALIDATION_FAILED = "validation_failed"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    NOT_FOUND = "not_found"
    CORPUS_EMPTY = "corpus_empty"
    UNAPPROVED_CHUNK = "unapproved_chunk"
    SAFETY_BLOCKED = "safety_blocked"
    VERIFIER_FAILED = "verifier_failed"
    QUOTA_EXCEEDED = "quota_exceeded"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_REFUSED = "provider_refused"
    PROVIDER_INVALID_RESPONSE = "provider_invalid_response"
    CACHE_UNAVAILABLE = "cache_unavailable"
    QDRANT_UNAVAILABLE = "qdrant_unavailable"
    VECTOR_STORE_UNAVAILABLE = "vector_store_unavailable"
    DB_UNAVAILABLE = "db_unavailable"
    INGEST_INVALID = "ingest_invalid"
    INGEST_TOO_LARGE = "ingest_too_large"
    WEBHOOK_BAD_SIGNATURE = "webhook_bad_signature"
    WEBHOOK_REPLAY = "webhook_replay"
    PRECONDITION_FAILED = "precondition_failed"
    FEATURE_DEFERRED = "feature_deferred"
    INTERNAL_ERROR = "internal_error"


class ApiException(Exception):  # noqa: N818  # base class; subclasses carry the Error suffix
    """Base class for typed API exceptions mapped to ApiError envelopes in core/middleware.py."""

    code: ApiErrorCode = ApiErrorCode.INTERNAL_ERROR
    http_status: int = 500
    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.retry_after_seconds = retry_after_seconds


class ProductionAuthConfigError(RuntimeError):
    """Raised at startup when APP_ENV=production and AUTH_PROVIDER=dev.

    See auth-context.md §Boot guard."""


class ForbiddenRoleError(ApiException):
    code = ApiErrorCode.FORBIDDEN_ROLE
    http_status = 403

    def __init__(self, *, required: str) -> None:
        super().__init__(f"Required scope: {required}", details={"requiredScope": required})


class TenantNotFoundError(ApiException):
    code = ApiErrorCode.TENANT_NOT_FOUND
    http_status = 404


class TenantInactiveError(ApiException):
    code = ApiErrorCode.TENANT_INACTIVE
    http_status = 403


class TenantMismatchError(ApiException):
    code = ApiErrorCode.TENANT_MISMATCH
    http_status = 403


class AuthMissingTokenError(ApiException):
    code = ApiErrorCode.AUTH_MISSING_TOKEN
    http_status = 401


class AuthInvalidTokenError(ApiException):
    code = ApiErrorCode.AUTH_INVALID_TOKEN
    http_status = 401


class AuthMissingOrgError(ApiException):
    code = ApiErrorCode.AUTH_MISSING_ORG
    http_status = 401


class ClerkConfigError(RuntimeError):
    """Raised at startup when AUTH_PROVIDER=clerk but Clerk JWKS settings are incomplete.

    See auth-context.md §Boot guard."""


class ProviderUnavailableError(Exception):
    """Adapter-layer: provider returned 5xx or timed out. Mapped to provider_unavailable at API."""


class ProviderTimeoutError(ProviderUnavailableError):
    pass


class ProviderRateLimitedError(Exception):
    pass


class ProviderAuthError(Exception):
    pass


class ProviderRefusedError(Exception):
    pass


class ProviderInvalidResponseError(Exception):
    pass


class ProviderContextTooLargeError(Exception):
    pass


class ParserCorruptFileError(Exception):
    pass


class ParserExtractionError(Exception):
    pass


class ParserTimeoutError(Exception):
    pass


class ParserPasswordProtectedError(Exception):
    pass


class VectorStoreTimeoutError(Exception):
    pass


class VectorStoreUnavailableError(Exception):
    pass


class VectorStoreInvalidDimensionError(Exception):
    pass


class VectorStoreTenantIsolationError(Exception):
    pass
