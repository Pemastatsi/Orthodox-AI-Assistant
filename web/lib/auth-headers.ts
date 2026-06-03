"use client";

/**
 * Client-side auth-header resolution.
 *
 * Clerk session tokens are short-lived, so callers resolve a FRESH `AuthHeaders` per request via the
 * async resolver returned by `useAuthResolver()` — never a value cached at render time. When Clerk is
 * disabled (dev mode) the resolver returns the dev principal, so the existing dev flow is unchanged.
 */
import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";

import { devPrincipalHeader, type AuthHeaders } from "./api-client";
import { CLERK_ENABLED } from "./auth-config";

/** Dev-mode principal from `NEXT_PUBLIC_DEV_PRINCIPAL` (`tenantId:role:userId`), with fallbacks. */
export function devAuthHeaders(devRole = "member"): AuthHeaders {
  const raw = process.env.NEXT_PUBLIC_DEV_PRINCIPAL;
  if (!raw) {
    return { devPrincipal: { tenantId: "tn_test", role: devRole, userId: "usr_test" } };
  }
  const [tenantId, role, userId] = raw.split(":");
  return {
    devPrincipal: {
      tenantId: tenantId || "tn_test",
      role: role || devRole,
      userId: userId || "usr_test",
    },
  };
}

/** `AuthHeaders` → a fetch header record (`Authorization` bearer or `x-dev-principal`). */
export function authHeaderRecord(auth: AuthHeaders): Record<string, string> {
  if (auth.authorization) return { authorization: auth.authorization };
  if (auth.devPrincipal) return devPrincipalHeader(auth.devPrincipal);
  return {};
}

function useClerkAuthResolver(devRole = "member"): () => Promise<AuthHeaders> {
  const { getToken } = useAuth();
  return useCallback(async () => {
    const token = await getToken();
    return token ? { authorization: `Bearer ${token}` } : devAuthHeaders(devRole);
  }, [getToken, devRole]);
}

function useDevAuthResolver(devRole = "member"): () => Promise<AuthHeaders> {
  return useCallback(async () => devAuthHeaders(devRole), [devRole]);
}

/**
 * Returns an async resolver for the current request's auth headers. The implementation is selected
 * at module-load time from the build-time `CLERK_ENABLED` constant, so each implementation's hook
 * calls stay unconditional (no rules-of-hooks violation) and dev mode never touches Clerk hooks.
 *
 * `devRole` is the fallback role used only in dev mode (e.g. admin surfaces pass "admin").
 */
export const useAuthResolver = CLERK_ENABLED ? useClerkAuthResolver : useDevAuthResolver;
