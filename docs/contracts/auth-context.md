# Auth Context

Status: Canonical
Date: 2026-05-01

This document defines how an incoming HTTP request is converted into a `Principal` (`docs/schemas/principal.schema.json`) and how tenant resolution behaves across edge cases. Implemented in `app/core/auth.py` and `app/core/middleware.py`.

## Sources of Truth

- **Identity:** Clerk. `clerkUserId` and `clerkOrgId` come from a Clerk-issued JWT in the `Authorization: Bearer <token>` header.
- **Tenant mapping:** the `tenants.clerk_org_id` column joins Clerk orgs to internal tenants 1:1.
- **Roles and scopes:** the `users.role` column. Scopes are derived from role per the table below; they are not stored.

## JWT Claims

Required claims on every authenticated request:

| Claim | Source | Notes |
|---|---|---|
| `sub` | Clerk user id | Maps to `users.clerk_user_id`. |
| `org_id` | Clerk active organization id | Maps to `tenants.clerk_org_id`. |
| `org_role` | Clerk org membership role | Used only as a hint; internal `users.role` is authoritative. |
| `iat`, `exp` | Standard | Verified against Clerk JWKS. |
| `azp` | Authorized party (frontend) | Verified against the configured allowlist. |

Tokens missing `org_id` produce `auth_missing_org`. Tokens whose `org_id` does not resolve to a `tenants` row produce `tenant_not_found`. Tokens whose tenant has `status != 'active'` produce `tenant_inactive`.

## Resolution Order

For every request to `/api/v1/*` (except webhooks):

1. Extract the bearer token. Missing → `auth_missing_token`.
2. Verify the token against Clerk JWKS (cached). Failure → `auth_invalid_token`.
3. Read `org_id` claim. Missing → `auth_missing_org`.
4. Look up `tenants` by `clerk_org_id`. Missing → `tenant_not_found`. `status != 'active'` → `tenant_inactive`.
5. Look up `users` by `clerk_user_id`. If absent, JIT-provision a row with `role='member'` and `status='active'`, bound to the resolved tenant. (JIT only when `org_role` is non-null.)
6. Verify `users.tenant_id == tenants.tenant_id`. Mismatch → `tenant_mismatch` (this should never happen for a Clerk-resolved org; if it does, log and reject).
7. Build the `Principal` and bind it to the request scope.
8. The `Principal` is available to handlers via `Depends(get_principal)`.

## Multi-Org Users

Clerk allows a user to belong to multiple orgs. The active org is selected by the user in the Clerk widget; the JWT carries exactly one `org_id`. No backend logic is required to "switch" tenants — switching means the frontend obtains a new token with a different `org_id`.

If the frontend renders a tenant switcher, it must call Clerk's `setActive({ organization })` API and refresh the token before issuing further backend calls.

## Roles and Scopes

| Role | Default scopes |
|---|---|
| `member` | `query:read`, `corpus:read` |
| `scholar` | member + `tenant:config:read` |
| `content_manager` | scholar + `corpus:write`, `corpus:approve`, `admin:queries:read`, `admin:flagged:read` |
| `admin` | content_manager + `admin:audit:read`, `tenant:config:write`, `billing:read` |
| `owner` | admin + (no additional scope; reserved for future delegation rules) |

Scopes are checked in handlers via a small dependency:

```python
def require_scope(scope: str) -> Callable:
    def _dep(p: Principal = Depends(get_principal)) -> Principal:
        if scope not in p.scopes:
            raise ForbiddenRoleError(required=scope)
        return p
    return _dep
```

Content managers see sensitive/flagged content **redacted by default**. Raw sensitive views require admin role and produce an `audit_entries` row with `action='raw_sensitive_view'`.

## Webhook Auth

Webhook endpoints (`/webhooks/{stripe,clerk,make}`) do **not** use Clerk JWTs. They verify HMAC signatures specific to each provider:

- **Stripe:** `Stripe-Signature` header per Stripe webhooks docs. Missing/invalid → `webhook_bad_signature`.
- **Clerk:** `svix-signature` per Svix. Missing/invalid → `webhook_bad_signature`.
- **Make.com:** custom HMAC per decision-register row O. Verifies (a) timestamp window ≤ 5 min, (b) nonce not seen in the last 24h, (c) HMAC over `timestamp + body`, (d) idempotency-key header. Missing/invalid → `webhook_bad_signature` or `webhook_replay`.

Webhooks resolve their tenant from the payload (e.g., `metadata.tenantId` for Stripe events) and never trust an `org_id` claim. The resolved tenant is logged but the action is gated on the verified payload, not on the request's identity.

## Errors

All auth errors use the `ApiError` envelope (`docs/schemas/api-error.schema.json`) with codes from `docs/contracts/error-taxonomy.md`. Specifically:

| Failure | Code | HTTP |
|---|---|---|
| Missing/invalid bearer | `auth_missing_token`, `auth_invalid_token` | 401 |
| Missing org claim | `auth_missing_org` | 401 |
| Org has no tenant | `tenant_not_found` | 404 |
| Tenant suspended/closed | `tenant_inactive` | 403 |
| Tenant mismatch | `tenant_mismatch` | 403 |
| Insufficient scope | `forbidden_role` | 403 |
| Webhook signature | `webhook_bad_signature` | 401 |
| Webhook replay | `webhook_replay` | 409 |

## Forbidden Patterns

- Reading `tenant_id` from the request body or query string. **Always** derive it from `Principal`.
- Caching the JWT verification result beyond Clerk's recommended JWKS TTL.
- Allowing JIT user provisioning to assign a non-`member` role.
- Any handler that accepts an unauthenticated principal without an explicit `Depends(allow_anonymous)` marker (used only by webhooks and `/health`).
