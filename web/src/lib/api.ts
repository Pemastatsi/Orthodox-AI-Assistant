/**
 * Minimal client for the backend chat endpoint, POST /api/v1/query.
 *
 * It calls the SAME-ORIGIN path `/api/v1/query`, which the Vite dev server proxies to the
 * backend on :8000 (see vite.config.ts) — so the browser never makes a cross-origin request
 * and no backend CORS configuration is required for local development.
 *
 * Auth: dev mode sends the backend's `x-dev-principal` header (base64 JSON). The query endpoint
 * requires the `query:read` scope, which the `member` role holds (docs/contracts/auth-context.md).
 * The full request/response contract mirrors web/lib/schemas/_generated/verified-response.ts.
 */
import { z } from "zod";

/** Dev principal used for local development. NOT used when a real auth provider is wired. */
const DEV_PRINCIPAL = { tenantId: "tn_test", role: "member", userId: "usr_test" };

function devPrincipalHeader(): Record<string, string> {
  const json = JSON.stringify(DEV_PRINCIPAL);
  const encoded =
    typeof btoa === "function" ? btoa(json) : Buffer.from(json, "utf-8").toString("base64");
  return { "x-dev-principal": encoded };
}

const CitationSchema = z.object({
  citationId: z.string(),
  chunkId: z.string(),
  sourceId: z.string(),
  title: z.string(),
  work: z.string().nullish(),
  father: z.string().nullish(),
  page: z.string().nullish(),
  timestamp: z.string().nullish(),
  quote: z.string().nullish(),
  sourceHash: z.string(),
  chunkHash: z.string(),
  approved: z.boolean(),
  corpusOrigin: z.enum(["tenant", "starter_corpus"]),
});

const PositionSchema = z.object({
  name: z.string(),
  thesis: z.string(),
  citationIds: z.array(z.string()),
  confidenceTier: z.enum(["GREEN", "YELLOW", "RED"]),
});

/** The subset of the backend VerifiedResponse the UI consumes (camelCase wire shape). */
export const VerifiedResponseSchema = z.object({
  answer: z.string(),
  confidenceTier: z.enum(["GREEN", "YELLOW", "RED"]),
  handling: z.enum([
    "answer",
    "answer_with_disclaimer",
    "reframe_to_teaching",
    "block_with_redirect",
    "insufficient_evidence",
  ]),
  citations: z.array(CitationSchema),
  verification: z.object({
    passed: z.boolean(),
    checkedAt: z.string(),
    verifierVersion: z.string(),
    failureReason: z.string().nullish(),
  }),
  reframing: z.object({
    wasReframed: z.boolean(),
    originalQuery: z.string().nullish(),
    reframedQuery: z.string().nullish(),
    disclosureText: z.string().nullish(),
  }),
  usage: z.object({
    servedAnswerCount: z.number(),
    freshModelRunCount: z.number(),
    modelRouteId: z.string().nullable(),
    promptTokens: z.number().nullish(),
    completionTokens: z.number().nullish(),
  }),
  runId: z.string().optional(),
  servedFromCache: z.boolean(),
  schemaVersion: z.string(),
  // Present (non-null) only for scholarly_dispute answers.
  positions: z.array(PositionSchema).nullish(),
});

export type VerifiedResponse = z.infer<typeof VerifiedResponseSchema>;
export type ApiCitation = z.infer<typeof CitationSchema>;

export class QueryApiError extends Error {
  readonly status: number;
  readonly code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/** Optional override for non-proxy/production use. Empty string → same-origin (dev proxy). */
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function postQuery(
  queryText: string,
  signal?: AbortSignal,
): Promise<VerifiedResponse> {
  const res = await fetch(`${API_BASE}/api/v1/query`, {
    method: "POST",
    headers: { "content-type": "application/json", ...devPrincipalHeader() },
    body: JSON.stringify({ queryText }),
    signal,
  });

  if (!res.ok) {
    let code: string | undefined;
    let message = `Request failed with status ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: { code?: string; message?: string } };
      if (body?.detail && typeof body.detail === "object") {
        code = body.detail.code;
        message = body.detail.message ?? message;
      }
    } catch {
      /* response body was not JSON */
    }
    throw new QueryApiError(res.status, message, code);
  }

  const parsed = VerifiedResponseSchema.safeParse(await res.json());
  if (!parsed.success) {
    throw new QueryApiError(0, `Unexpected response shape: ${parsed.error.message}`);
  }
  return parsed.data;
}
