"""Response cache — canonical recipe per `docs/contracts/cache-key.md`.

Two layers live here:

1. **Pure functions** (`normalize_query`, `cache_key`, `build_cache_fields`) implement the
   contract byte-for-byte. The V1-V4 reference vectors in `cache-key.md` and the unit tests
   in `tests/unit/test_cache_key.py` are the executable specification — any change here that
   breaks those vectors requires bumping `schemaVersion` or `promptVersion`/`modelRouteId`
   and updating the contract.

2. **`ResponseCache`** wraps `redis.asyncio.Redis` with JSON serialisation of
   `VerifiedResponse`. Keys are prefixed `qcache:` so we can `SCAN MATCH qcache:*` in ops
   tools without colliding with arq queues or other Redis users.

The cache is intentionally dumb: no locking, no stampede protection. On a version bump the
whole scope is invalidated and the first miss serves a fresh A5 run per ADR-0005.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any, Final

from pydantic import ValidationError
from redis.asyncio import Redis

from app.core.logging import get_logger
from app.domain.models.principal import Principal
from app.domain.models.verified_response import VerifiedResponse

logger = get_logger(__name__)

CACHE_KEY_PREFIX: Final = "qcache:"

_REQUIRED_FIELDS: Final = frozenset(
    {
        "tenantId",
        "queryNormalized",
        "role",
        "sessionHash",
        "answerMode",
        "corpusVersion",
        "promptVersion",
        "modelRouteId",
        "schemaVersion",
        "configVersion",
        "calendarVersion",
    }
)


def normalize_query(q: str) -> str:
    """Canonical query normalization per `cache-key.md` §Query Normalization.

    NFKC + casefold + strip + collapse internal whitespace runs to a single space.
    Diacritics and punctuation are preserved (unlike the more aggressive A6 overlap normaliser).
    """
    q = unicodedata.normalize("NFKC", q)
    q = q.casefold().strip()
    return " ".join(q.split())


def cache_key(fields: dict[str, Any]) -> str:
    """SHA-256 hex digest of the canonical JSON encoding of `fields`.

    Reject any dict whose key-set differs from the 11 required fields — adding a key is a
    cache-flush event that requires a documented version bump.
    """
    keys = set(fields.keys())
    if keys != _REQUIRED_FIELDS:
        missing = _REQUIRED_FIELDS - keys
        extra = keys - _REQUIRED_FIELDS
        raise ValueError(
            f"cache_key field mismatch — missing={sorted(missing)} extra={sorted(extra)}"
        )
    canonical = json.dumps(
        fields,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_cache_fields(
    *,
    principal: Principal,
    raw_query: str,
    answer_mode: str,
    session_hash: str | None,
    corpus_version: str,
    config_version: str,
    calendar_version: str,
    prompt_version: str,
    model_route_id: str,
    schema_version: str,
) -> dict[str, Any]:
    """Assemble the 11-field cache-key dict for `cache_key()`.

    Each argument maps 1:1 to a contract field. The query is normalised here.
    """
    return {
        "tenantId": principal.tenant_id,
        "queryNormalized": normalize_query(raw_query),
        "role": principal.role,
        "sessionHash": session_hash,
        "answerMode": answer_mode,
        "corpusVersion": corpus_version,
        "promptVersion": prompt_version,
        "modelRouteId": model_route_id,
        "schemaVersion": schema_version,
        "configVersion": config_version,
        "calendarVersion": calendar_version,
    }


class ResponseCache:
    """Async Redis wrapper for cached `VerifiedResponse` payloads."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    @staticmethod
    def _redis_key(key: str) -> str:
        return f"{CACHE_KEY_PREFIX}{key}"

    async def get(self, key: str) -> VerifiedResponse | None:
        """Return the cached response or `None` on miss / corruption.

        A corrupt cache entry (invalid JSON, schema drift) is treated as a miss and logged;
        the entry is left in place so the next valid write overwrites it — deletion would
        race with concurrent writers.
        """
        raw = await self._redis.get(self._redis_key(key))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return VerifiedResponse.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "cache.corrupt_entry",
                cache_key=key,
                error_type=type(exc).__name__,
            )
            return None

    async def set(self, key: str, response: VerifiedResponse, ttl_seconds: int) -> None:
        """Write the response with a TTL. Caller decides whether to await or fire-and-forget."""
        payload = response.model_dump_json(by_alias=True).encode("utf-8")
        await self._redis.set(self._redis_key(key), payload, ex=ttl_seconds)


__all__ = [
    "CACHE_KEY_PREFIX",
    "ResponseCache",
    "build_cache_fields",
    "cache_key",
    "normalize_query",
]
