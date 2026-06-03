"""Full Clerk JWT pipeline — skipped unless staging-Clerk creds are present (auth-context.md
§Testing posture). When `CLERK_SECRET_KEY`, `CLERK_JWT_ISSUER`, and a `CLERK_TEST_TOKEN` are set,
this verifies a real Clerk-issued token against the live JWKS endpoint.
"""

from __future__ import annotations

import os

import pytest

_TOKEN = os.environ.get("CLERK_TEST_TOKEN")

pytestmark = pytest.mark.skipif(
    not (os.environ.get("CLERK_SECRET_KEY") and os.environ.get("CLERK_JWT_ISSUER") and _TOKEN),
    reason="requires staging Clerk creds (CLERK_SECRET_KEY + CLERK_JWT_ISSUER + CLERK_TEST_TOKEN)",
)


def test_staging_clerk_token_verifies() -> None:
    from app.core.auth import reset_jwks_client_cache, verify_clerk_token

    reset_jwks_client_cache()
    assert _TOKEN is not None
    claims = verify_clerk_token(_TOKEN)
    assert claims.sub
