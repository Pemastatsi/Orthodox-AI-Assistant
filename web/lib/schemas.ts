/**
 * Zod schemas mirroring `docs/schemas/*.schema.json` and the response shapes
 * used by `app/api/v1/query.py` + admin endpoints. These act as the runtime
 * validation layer between the backend and the React components, per
 * `frontend-components.md`: "Schema validation: every API response is validated
 * client-side."
 *
 * The shapes are camelCase to match the FastAPI response_model_by_alias=True
 * serialization the backend uses.
 */
import { z } from "zod";

export const ConfidenceTierSchema = z.enum(["GREEN", "YELLOW", "RED"]);
export type ConfidenceTier = z.infer<typeof ConfidenceTierSchema>;

export const HandlingSchema = z.enum([
  "answer",
  "answer_with_disclaimer",
  "reframe_to_teaching",
  "block_with_redirect",
  "insufficient_evidence",
]);
export type Handling = z.infer<typeof HandlingSchema>;

export const SensitivityPrimarySchema = z.enum([
  "normal",
  "pastoral_advice",
  "political",
  "medical",
  "comparative_religion",
  "canonical_dispute",
  "other_sensitive",
]);
export type SensitivityPrimary = z.infer<typeof SensitivityPrimarySchema>;

export const CitationSchema = z.object({
  citationId: z.string(),
  chunkId: z.string(),
  sourceId: z.string(),
  title: z.string(),
  sourceHash: z.string(),
  chunkHash: z.string(),
  approved: z.literal(true),
  corpusOrigin: z.enum(["tenant", "starter_corpus"]),
  work: z.string().nullable().optional(),
  father: z.string().nullable().optional(),
  page: z.string().nullable().optional(),
  timestamp: z.string().nullable().optional(),
  quote: z.string().nullable().optional(),
});
export type Citation = z.infer<typeof CitationSchema>;

export const VerificationSchema = z.object({
  passed: z.boolean(),
  checkedAt: z.string(),
  verifierVersion: z.string(),
  failureReason: z.string().nullable().optional(),
});

export const ReframingSchema = z.object({
  wasReframed: z.boolean(),
  originalQuery: z.string().nullable().optional(),
  reframedQuery: z.string().nullable().optional(),
  disclosureText: z.string().nullable().optional(),
});
export type Reframing = z.infer<typeof ReframingSchema>;

export const VerifiedResponseUsageSchema = z.object({
  servedAnswerCount: z.number().int().min(0).max(1),
  freshModelRunCount: z.number().int().min(0).max(1),
  modelRouteId: z.string(),
  promptTokens: z.number().int().nullable().optional(),
  completionTokens: z.number().int().nullable().optional(),
});

/**
 * One position of a scholarly_dispute answer. Each position is composed from
 * its own sub-packet (A5 runs per column, per the T-006 task card); citations
 * are scoped to the column and NEVER aggregated across columns.
 *
 * The backend pipeline does not yet emit `positions`; the field is optional on
 * the wire today. When the per-column A5 composition lands (follow-up to T-006),
 * `<DisputeCard>` will pick up real data without further frontend changes.
 */
export const PositionSchema = z.object({
  name: z.string(),
  thesis: z.string(),
  citationIds: z.array(z.string()).default([]),
  confidenceTier: ConfidenceTierSchema,
});
export type Position = z.infer<typeof PositionSchema>;

export const VerifiedResponseSchema = z.object({
  answer: z.string(),
  confidenceTier: ConfidenceTierSchema,
  handling: HandlingSchema,
  citations: z.array(CitationSchema).default([]),
  verification: VerificationSchema,
  reframing: ReframingSchema,
  usage: VerifiedResponseUsageSchema,
  servedFromCache: z.boolean(),
  schemaVersion: z.string(),
  runId: z.string(),
  /** Present only when the answer is a scholarly_dispute; renders side-by-side. */
  positions: z.array(PositionSchema).optional(),
});
export type VerifiedResponse = z.infer<typeof VerifiedResponseSchema>;

export const ApiErrorSchema = z.object({
  code: z.string(),
  message: z.string(),
  requiredScope: z.string().optional(),
});
export type ApiError = z.infer<typeof ApiErrorSchema>;

/* -------------------------------------------------------------------------- */
/* Admin endpoint payloads (B.4 surfaces).                                    */
/* Wire shape matches FastAPI response_model_by_alias=True (camelCase).       */
/* -------------------------------------------------------------------------- */

export const StageSchema = z.object({
  stage: z.string(),
  startedAt: z.string(),
  finishedAt: z.string().nullable().optional(),
  outcome: z.string(),
  modelRouteId: z.string().nullable().optional(),
  notes: z.string().nullable().optional(),
});

export const RunTraceUsageSchema = z.object({
  servedAnswerCount: z.number().int().min(0).max(1),
  freshModelRunCount: z.number().int().min(0).max(1),
});

export const RunTraceSchema = z.object({
  runId: z.string(),
  tenantId: z.string(),
  userId: z.string(),
  sessionId: z.string().nullable().optional(),
  startedAt: z.string(),
  finishedAt: z.string().nullable().optional(),
  cacheHit: z.boolean(),
  stages: z.array(StageSchema).default([]),
  usage: RunTraceUsageSchema,
  finalHandling: HandlingSchema.nullable().optional(),
  finalConfidenceTier: ConfidenceTierSchema.nullable().optional(),
  verifierPassed: z.boolean().nullable().optional(),
  evidencePacketRef: z.string().nullable().optional(),
});
export type RunTrace = z.infer<typeof RunTraceSchema>;

export const FlaggedQueryWireSchema = z.object({
  flaggedQueryId: z.string(),
  tenantId: z.string(),
  userId: z.string(),
  runId: z.string().nullable().optional(),
  queryTextRedacted: z.string(),
  rawSensitiveLogId: z.string().nullable().optional(),
  flagReason: z.string(),
  sensitivityPrimary: z.string().nullable().optional(),
  riskFlags: z.array(z.string()).default([]),
  createdAt: z.string(),
});
export type FlaggedQueryWire = z.infer<typeof FlaggedQueryWireSchema>;

export const AuditEntrySchema = z.object({
  auditId: z.string(),
  tenantId: z.string(),
  actorUserId: z.string(),
  actorRole: z.string(),
  action: z.string(),
  resourceType: z.string(),
  resourceId: z.string(),
  occurredAt: z.string(),
  details: z.record(z.unknown()).default({}),
  ipAddress: z.string().nullable().optional(),
});
export type AuditEntry = z.infer<typeof AuditEntrySchema>;

export const VisibilitySchema = z.enum([
  "member",
  "scholar",
  "admin_only",
  "suppressed",
]);
export type Visibility = z.infer<typeof VisibilitySchema>;

export const ChunkSchema = z.object({
  chunkId: z.string(),
  sourceId: z.string(),
  tenantId: z.string(),
  text: z.string(),
  chunkHash: z.string(),
  approved: z.boolean(),
  visibility: VisibilitySchema,
  father: z.string().nullable().optional(),
  work: z.string().nullable().optional(),
  page: z.string().nullable().optional(),
  timestamp: z.string().nullable().optional(),
  language: z.string().optional(),
  reviewNote: z.string().nullable().optional(),
  createdAt: z.string(),
});
export type Chunk = z.infer<typeof ChunkSchema>;

export const PageSchema = <T extends z.ZodTypeAny>(item: T) =>
  z.object({
    items: z.array(item).default([]),
    nextCursor: z.string().nullable(),
  });

export const RunTracePageSchema = PageSchema(RunTraceSchema);
export const FlaggedQueryPageSchema = PageSchema(FlaggedQueryWireSchema);
export const AuditEntryPageSchema = PageSchema(AuditEntrySchema);
export const ChunkPageSchema = PageSchema(ChunkSchema);

export type Page<T> = { items: T[]; nextCursor: string | null };
