"""Boot guard: APP_ENV=production refuses to start with a missing/malformed
SENSITIVE_LOG_DATA_KEY_BASE64. See ADR-0005 §Encryption strategy."""

from __future__ import annotations

import base64

import pytest
from app.core.config import Settings
from app.domain.services.encryption_service import KEY_BYTES, CipherKeyError
from app.main import _production_sensitive_log_guard

_VALID_KEY_B64 = base64.b64encode(b"\x00" * KEY_BYTES).decode("ascii")


def test_production_with_empty_key_raises() -> None:
    settings = Settings(app_env="production", sensitive_log_data_key_base64="")
    with pytest.raises(CipherKeyError):
        _production_sensitive_log_guard(settings)


def test_production_with_non_base64_key_raises() -> None:
    settings = Settings(
        app_env="production", sensitive_log_data_key_base64="not-base64!!"
    )
    with pytest.raises(CipherKeyError):
        _production_sensitive_log_guard(settings)


def test_production_with_wrong_length_key_raises() -> None:
    short = base64.b64encode(b"\x00" * 16).decode("ascii")
    settings = Settings(app_env="production", sensitive_log_data_key_base64=short)
    with pytest.raises(CipherKeyError):
        _production_sensitive_log_guard(settings)


def test_production_with_valid_key_passes() -> None:
    settings = Settings(
        app_env="production", sensitive_log_data_key_base64=_VALID_KEY_B64
    )
    _production_sensitive_log_guard(settings)


def test_development_with_empty_key_passes() -> None:
    settings = Settings(app_env="development", sensitive_log_data_key_base64="")
    _production_sensitive_log_guard(settings)
