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
});
export type VerifiedResponse = z.infer<typeof VerifiedResponseSchema>;

export const ApiErrorSchema = z.object({
  code: z.string(),
  message: z.string(),
  requiredScope: z.string().optional(),
});
export type ApiError = z.infer<typeof ApiErrorSchema>;
