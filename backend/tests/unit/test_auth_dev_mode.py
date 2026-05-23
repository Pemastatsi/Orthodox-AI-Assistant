"""Dev-mode Principal resolution per auth-context.md §Development Mode."""

from __future__ import annotations

import base64
import json

from app.core.auth import make_dev_principal, resolve_principal, scopes_for_role
from app.core.config import Settings


def _dev_settings(**overrides: object) -> Settings:
    return Settings(auth_provider="dev", app_env="development", **overrides)  # type: ignore[arg-type]


def test_fallback_principal_is_dev_tenant_member() -> None:
    p = resolve_principal(
        authorization=None,
        dev_principal_header=None,
        settings=_dev_settings(),
    )
    assert p.tenant_id == "dev-tenant"
    assert p.role == "member"
    assert "query:read" in p.scopes


def test_header_with_admin_role_yields_admin_scopes() -> None:
    payload = {"tenantId": "t_real", "role": "admin"}
    header = base64.b64encode(json.dumps(payload).encode()).decode()
    p = resolve_principal(
        authorization=None,
        dev_principal_header=header,
        settings=_dev_settings(),
    )
    assert p.tenant_id == "t_real"
    assert p.role == "admin"
    assert "admin:audit:read" in p.scopes


def test_make_dev_principal_default_scopes() -> None:
    p = make_dev_principal(role="content_manager")
    assert p.role == "content_manager"
    assert "corpus:approve" in p.scopes
    assert "admin:audit:read" not in p.scopes


def test_scopes_for_role_unknown_falls_back_to_member() -> None:
    assert scopes_for_role("not_a_role") == scopes_for_role("member")
