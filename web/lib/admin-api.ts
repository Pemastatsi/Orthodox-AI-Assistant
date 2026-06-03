/**
 * Server-side fetch helpers for the admin endpoints (T-006 B.4 surfaces).
 * These are intentionally separate from `lib/api-client.ts` because admin
 * pages are React Server Components — they read auth from the server-side
 * environment: Clerk's `auth()` JWT in Clerk mode, or a `DEV_PRINCIPAL` env
 * var in dev mode.
 *
 * Each helper validates the response with the matching zod schema and throws
 * on schema mismatch so the Next.js error boundary surfaces the failure.
 */
import { auth } from "@clerk/nextjs/server";

import { CLERK_ENABLED } from "./auth-config";
import {
  AuditEntryPageSchema,
  ChunkPageSchema,
  FlaggedQueryPageSchema,
  RunTracePageSchema,
  type AuditEntry,
  type Chunk,
  type FlaggedQueryWire,
  type Page,
  type RunTrace,
} from "./schemas";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * Resolve the server-side dev principal from the `DEV_PRINCIPAL` env var
 * (format: `tenantId:role:userId`). Defaults to `tn_test:admin:usr_test` so
 * an unconfigured dev environment can still browse the admin surfaces.
 */
function serverDevPrincipal(): { tenantId: string; role: string; userId: string } {
  const raw = process.env.DEV_PRINCIPAL ?? "tn_test:admin:usr_test";
  const [tenantId, role, userId] = raw.split(":");
  return {
    tenantId: tenantId ?? "tn_test",
    role: role ?? "admin",
    userId: userId ?? "usr_test",
  };
}

async function serverAuthHeaders(): Promise<Record<string, string>> {
  if (CLERK_ENABLED) {
    const { getToken } = await auth();
    const token = await getToken();
    if (token) return { authorization: `Bearer ${token}` };
  }
  // Dev mode (or a missing Clerk token): fall back to the server dev principal.
  const principal = serverDevPrincipal();
  const encoded = Buffer.from(JSON.stringify(principal), "utf-8").toString("base64");
  return { "x-dev-principal": encoded };
}

export class AdminApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function adminFetch(path: string, query: Record<string, string | undefined>): Promise<unknown> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== "") params.set(k, v);
  }
  const url = `${API_BASE}${path}${params.toString() ? `?${params}` : ""}`;
  const res = await fetch(url, {
    method: "GET",
    headers: { ...(await serverAuthHeaders()), "content-type": "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new AdminApiError(res.status, `GET ${path} → ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

export interface QueryLogFilters {
  cursor?: string;
  limit?: number;
  handling?: string;
  confidenceTier?: "GREEN" | "YELLOW" | "RED";
  since?: string;
}

export async function listAdminQueries(
  filters: QueryLogFilters = {},
): Promise<Page<RunTrace>> {
  const data = await adminFetch("/api/v1/admin/queries", {
    cursor: filters.cursor,
    limit: filters.limit?.toString(),
    handling: filters.handling,
    confidenceTier: filters.confidenceTier,
    since: filters.since,
  });
  return RunTracePageSchema.parse(data);
}

export interface FlaggedFilters {
  cursor?: string;
  limit?: number;
  flagReason?: string;
}

export async function listAdminFlagged(
  filters: FlaggedFilters = {},
): Promise<Page<FlaggedQueryWire>> {
  const data = await adminFetch("/api/v1/admin/flagged", {
    cursor: filters.cursor,
    limit: filters.limit?.toString(),
    flagReason: filters.flagReason,
  });
  return FlaggedQueryPageSchema.parse(data);
}

export interface AuditFilters {
  cursor?: string;
  limit?: number;
  action?: string;
  resourceType?: string;
  since?: string;
}

export async function listAdminAudit(
  filters: AuditFilters = {},
): Promise<Page<AuditEntry>> {
  const data = await adminFetch("/api/v1/admin/audit", {
    cursor: filters.cursor,
    limit: filters.limit?.toString(),
    action: filters.action,
    resourceType: filters.resourceType,
    since: filters.since,
  });
  return AuditEntryPageSchema.parse(data);
}

export interface CorpusFilters {
  cursor?: string;
  limit?: number;
  approved?: boolean;
  visibility?: "member" | "scholar" | "admin_only" | "suppressed";
  sourceId?: string;
}

export async function listCorpus(
  filters: CorpusFilters = {},
): Promise<Page<Chunk>> {
  const data = await adminFetch("/api/v1/corpus", {
    cursor: filters.cursor,
    limit: filters.limit?.toString(),
    approved:
      filters.approved === undefined ? undefined : String(filters.approved),
    visibility: filters.visibility,
    sourceId: filters.sourceId,
  });
  return ChunkPageSchema.parse(data);
}

export { serverDevPrincipal };
