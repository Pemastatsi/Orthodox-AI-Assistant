import logging
import sys
from typing import Any, cast

import structlog
from structlog.typing import Processor

from app.core.config import get_settings

REDACTED_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "authorization",
        "cookie",
        "set-cookie",
        "private_key",
        "signing_key",
        "hmac",
        "otp",
        "mfa",
        "ssn",
        "dob",
        "credit_card",
        "card_number",
        "cvv",
        "pan",
        "query_text",
        "raw_query",
        "raw_answer",
        "chunk_text",
        "source_text",
    }
)


def _redact_recursive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: "[redacted]" if k.lower() in REDACTED_KEYS else _redact_recursive(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_recursive(v) for v in value]
    return value


def _redact_processor(
    _logger: object,
    _name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Redact sensitive values from log records before serialization."""
    redacted = _redact_recursive(event_dict)
    return cast(dict[str, Any], redacted)


def configure_logging() -> None:
    """Wire structlog to emit JSON to stdout with the log shape from observability.md."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        cast(Processor, _redact_processor),
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
