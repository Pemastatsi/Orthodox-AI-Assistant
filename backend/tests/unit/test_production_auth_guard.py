"""Boot guard: APP_ENV=production + AUTH_PROVIDER=dev refuses to start.

See auth-context.md §Boot guard."""

from __future__ import annotations

import pytest
from app.core.config import Settings
from app.core.errors import ProductionAuthConfigError
from app.main import _production_auth_guard


def test_production_with_dev_auth_raises() -> None:
    settings = Settings(app_env="production", auth_provider="dev")
    with pytest.raises(ProductionAuthConfigError):
        _production_auth_guard(settings)


def test_production_with_clerk_auth_passes() -> None:
    settings = Settings(app_env="production", auth_provider="clerk")
    _production_auth_guard(settings)


def test_development_with_dev_auth_passes() -> None:
    settings = Settings(app_env="development", auth_provider="dev")
    _production_auth_guard(settings)
