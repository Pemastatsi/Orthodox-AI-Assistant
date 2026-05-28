/**
 * Typed API client. POSTs to /api/v1/query and (later) admin endpoints, attaching
 * the dev-mode `x-dev-principal` header in development, or a Clerk JWT in prod.
 *
 * SSE streaming is deliberately not wired here — `frontend-components.md` lists
 * it on `<ChatComposer>`, but it is deferred to a follow-up PR per the approved
 * sequencing plan. This client returns the full `VerifiedResponse` JSON when
 * the route finishes synchronously.
 */
import { ApiErrorSchema, VerifiedResponseSchema, type ApiError, type VerifiedResponse } from "./schemas";

const DEFAULT_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Encodes a dev principal as the backend's `x-dev-principal` header expects. */
function devPrincipalHeader(opts: {
  tenantId: string;
  role: string;
  userId: string;
}): Record<string, string> {
  const json = JSON.stringify({
    tenantId: opts.tenantId,
    role: opts.role,
    userId: opts.userId,
  });
  const encoded =
    typeof btoa === "function"
      ? btoa(json)
      : Buffer.from(json, "utf-8").toString("base64");
  return { "x-dev-principal": encoded };
}

export interface AuthHeaders {
  /** Authorization: Bearer <jwt> — when Clerk is wired. */
  authorization?: string;
  /** x-dev-principal payload — development only. */
  devPrincipal?: { tenantId: string; role: string; userId: string };
}

function buildHeaders(auth: AuthHeaders | undefined): HeadersInit {
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (auth?.authorization) headers.authorization = auth.authorization;
  if (auth?.devPrincipal) Object.assign(headers, devPrincipalHeader(auth.devPrincipal));
  return headers;
}

export class ApiClientError extends Error {
  readonly status: number;
  readonly apiError: ApiError | null;

  constructor(status: number, apiError: ApiError | null, message: string) {
    super(message);
    this.status = status;
    this.apiError = apiError;
  }
}

async function parseApiError(response: Response): Promise<ApiError | null> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (body && typeof body === "object" && "detail" in body) {
      const parsed = ApiErrorSchema.safeParse(body.detail);
      return parsed.success ? parsed.data : null;
    }
  } catch {
    /* not JSON */
  }
  return null;
}

export interface QueryRequest {
  queryText: string;
}

export interface QueryOptions {
  baseUrl?: string;
  auth?: AuthHeaders;
  signal?: AbortSignal;
}

export async function postQuery(
  request: QueryRequest,
  opts: QueryOptions = {},
): Promise<VerifiedResponse> {
  const baseUrl = opts.baseUrl ?? DEFAULT_API_BASE;
  const response = await fetch(`${baseUrl}/api/v1/query`, {
    method: "POST",
    headers: buildHeaders(opts.auth),
    body: JSON.stringify(request),
    signal: opts.signal,
  });

  if (!response.ok) {
    const apiError = await parseApiError(response);
    throw new ApiClientError(
      response.status,
      apiError,
      apiError?.message ?? `Request failed with status ${response.status}`,
    );
  }

  const json = await response.json();
  const parsed = VerifiedResponseSchema.safeParse(json);
  if (!parsed.success) {
    throw new ApiClientError(
      0,
      null,
      `VerifiedResponse failed schema validation: ${parsed.error.message}`,
    );
  }
  return parsed.data;
}

export { devPrincipalHeader };
