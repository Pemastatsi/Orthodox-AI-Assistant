"""Unit tests for Clerk JWKS verification + identity resolution (no live Clerk, no DB).

`verify_clerk_token` runs against a locally-generated RSA keypair — real RS256 verification with
the JWKS client stubbed to return our public key. `_resolve_clerk_identity` runs against a fake
`IdentityRepository` so the tenant/user/JIT branches are covered without a database.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

import jwt
import pytest
from app.api.v1 import _deps
from app.core import auth
from app.core.config import Settings
from app.core.errors import (
    AuthInvalidTokenError,
    AuthMissingOrgError,
    AuthMissingTokenError,
    TenantInactiveError,
    TenantMismatchError,
    TenantNotFoundError,
)
from app.domain.repositories.identity_repository import TenantAuthRow, UserAuthRow
from cryptography.hazmat.primitives.asymmetric import rsa

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

_ISSUER = "https://clerk.example"
_AZP = "http://localhost:3000"


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "clerk_jwt_issuer": _ISSUER,
        "clerk_authorized_parties": _AZP,
        "clerk_jwks_cache_seconds": 3600,
    }
    base.update(overrides)
    return Settings(**base)


def _token(key: Any = _PRIVATE_KEY, **claims: Any) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": "user_clerk_1",
        "org_id": "org_clerk_1",
        "org_role": "org:member",
        "azp": _AZP,
        "iss": _ISSUER,
        "iat": now,
        "exp": now + 3600,
    }
    payload.update(claims)
    payload = {k: v for k, v in payload.items() if v is not None}
    return jwt.encode(payload, key, algorithm="RS256")


class _StubSigningKey:
    def __init__(self, key: Any) -> None:
        self.key = key


class _StubJWKClient:
    def __init__(self, public_key: Any) -> None:
        self._pk = public_key

    def get_signing_key_from_jwt(self, token: str) -> _StubSigningKey:  # noqa: ARG002
        return _StubSigningKey(self._pk)


@pytest.fixture(autouse=True)
def _stub_jwks(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(auth, "_get_jwks_client", lambda *_: _StubJWKClient(_PUBLIC_KEY))
    auth.reset_jwks_client_cache()
    yield
    auth.reset_jwks_client_cache()


# ---- verify_clerk_token --------------------------------------------------------------


def test_valid_token_returns_claims() -> None:
    claims = auth.verify_clerk_token(_token(), _settings())
    assert claims.sub == "user_clerk_1"
    assert claims.org_id == "org_clerk_1"
    assert claims.org_role == "org:member"
    assert claims.azp == _AZP


def test_bad_signature_rejected() -> None:
    token = _token(key=_OTHER_KEY)  # signed by a key the stubbed JWKS will not match
    with pytest.raises(AuthInvalidTokenError):
        auth.verify_clerk_token(token, _settings())


def test_expired_token_rejected() -> None:
    now = int(time.time())
    with pytest.raises(AuthInvalidTokenError):
        auth.verify_clerk_token(_token(iat=now - 7200, exp=now - 3600), _settings())


def test_wrong_azp_rejected() -> None:
    with pytest.raises(AuthInvalidTokenError):
        auth.verify_clerk_token(_token(azp="http://evil.example"), _settings())


def test_issuer_mismatch_rejected() -> None:
    with pytest.raises(AuthInvalidTokenError):
        auth.verify_clerk_token(_token(iss="https://wrong.example"), _settings())


def test_missing_sub_rejected() -> None:
    with pytest.raises(AuthInvalidTokenError):
        auth.verify_clerk_token(_token(sub=None), _settings())


# ---- bearer_token --------------------------------------------------------------------


def test_bearer_token_ok() -> None:
    assert auth.bearer_token("Bearer abc.def.ghi") == "abc.def.ghi"


@pytest.mark.parametrize("header", [None, "", "Token abc", "Bearer ", "abc"])
def test_bearer_token_rejects(header: str | None) -> None:
    with pytest.raises(AuthMissingTokenError):
        auth.bearer_token(header)


# ---- _resolve_clerk_identity ---------------------------------------------------------


@asynccontextmanager
async def _fake_scope() -> Any:
    yield object()


class _FakeRepo:
    def __init__(
        self,
        *,
        tenant: TenantAuthRow | None = None,
        user: UserAuthRow | None = None,
        jit_user: UserAuthRow | None = None,
    ) -> None:
        self._tenant = tenant
        self._user = user
        self._jit_user = jit_user
        self.jit_called = False

    async def get_tenant_by_clerk_org(self, clerk_org_id: str) -> TenantAuthRow | None:  # noqa: ARG002
        return self._tenant

    async def get_user_by_clerk_id(self, clerk_user_id: str) -> UserAuthRow | None:  # noqa: ARG002
        return self._user

    async def jit_provision_user(self, *, clerk_user_id: str, tenant_id: str) -> UserAuthRow | None:  # noqa: ARG002
        self.jit_called = True
        return self._jit_user


def _patch_identity(monkeypatch: pytest.MonkeyPatch, repo: _FakeRepo) -> None:
    monkeypatch.setattr(_deps, "admin_session_scope", lambda: _fake_scope())
    monkeypatch.setattr(_deps, "IdentityRepository", lambda *_: repo)


def _claims(**overrides: Any) -> auth.ClerkClaims:
    base: dict[str, Any] = {
        "sub": "user_clerk_1",
        "org_id": "org_clerk_1",
        "org_role": "org:member",
        "azp": _AZP,
    }
    base.update(overrides)
    return auth.ClerkClaims(**base)


async def test_identity_existing_user_builds_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepo(
        tenant=TenantAuthRow(tenant_id="tn_1", status="active", data_region="eu"),
        user=UserAuthRow(user_id="usr_1", tenant_id="tn_1", role="admin"),
    )
    _patch_identity(monkeypatch, repo)
    principal = await _deps._resolve_clerk_identity(_claims())
    assert principal.tenant_id == "tn_1"
    assert principal.user_id == "usr_1"
    assert principal.role == "admin"
    assert principal.clerk_org_id == "org_clerk_1"
    assert principal.data_region == "eu"
    assert "admin:audit:read" in principal.scopes
    assert repo.jit_called is False


async def test_identity_missing_org_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_identity(monkeypatch, _FakeRepo())
    with pytest.raises(AuthMissingOrgError):
        await _deps._resolve_clerk_identity(_claims(org_id=None))


async def test_identity_tenant_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_identity(monkeypatch, _FakeRepo(tenant=None))
    with pytest.raises(TenantNotFoundError):
        await _deps._resolve_clerk_identity(_claims())


async def test_identity_tenant_inactive(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _FakeRepo(tenant=TenantAuthRow(tenant_id="tn_1", status="suspended", data_region="us"))
    _patch_identity(monkeypatch, repo)
    with pytest.raises(TenantInactiveError):
        await _deps._resolve_clerk_identity(_claims())


async def test_identity_jit_provisions_member(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _FakeRepo(
        tenant=TenantAuthRow(tenant_id="tn_1", status="active", data_region="us"),
        user=None,
        jit_user=UserAuthRow(user_id="usr_new", tenant_id="tn_1", role="member"),
    )
    _patch_identity(monkeypatch, repo)
    principal = await _deps._resolve_clerk_identity(_claims())
    assert repo.jit_called is True
    assert principal.role == "member"
    assert principal.user_id == "usr_new"


async def test_identity_no_user_no_org_role_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepo(
        tenant=TenantAuthRow(tenant_id="tn_1", status="active", data_region="us"),
        user=None,
    )
    _patch_identity(monkeypatch, repo)
    with pytest.raises(AuthInvalidTokenError):
        await _deps._resolve_clerk_identity(_claims(org_role=None))


async def test_identity_tenant_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _FakeRepo(
        tenant=TenantAuthRow(tenant_id="tn_1", status="active", data_region="us"),
        user=UserAuthRow(user_id="usr_1", tenant_id="tn_OTHER", role="member"),
    )
    _patch_identity(monkeypatch, repo)
    with pytest.raises(TenantMismatchError):
        await _deps._resolve_clerk_identity(_claims())
