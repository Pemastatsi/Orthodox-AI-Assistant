/**
 * Maps the backend `VerifiedResponse` (see lib/api.ts) onto the UI's presentation `Query`
 * type (src/data/types.ts) that the Assistant Workbench renders.
 *
 * The `/query` response does not carry every field the UI can display (evidence counts,
 * per-citation classification/quote-integrity, and the consensus/timeline/policy structures).
 * Those are defaulted or left undefined here; the corresponding cards degrade gracefully.
 */
import type {
  AnswerMode,
  Citation,
  ConfidenceTier,
  Handling,
  ProgressStep,
  Query,
} from "@/data/types";
import type { ApiCitation, VerifiedResponse } from "./api";

const TIER_TO_CONFIDENCE: Record<"GREEN" | "YELLOW" | "RED", ConfidenceTier> = {
  GREEN: "high",
  YELLOW: "moderate",
  RED: "low",
};

const TIER_TO_COVERAGE: Record<"GREEN" | "YELLOW" | "RED", number> = {
  GREEN: 0.9,
  YELLOW: 0.6,
  RED: 0.3,
};

const COMPLETED_STEPS: ProgressStep[] = [
  "classified",
  "retrieval_planned",
  "vector_search",
  "evidence_admitted",
  "answer_composed",
  "citations_verified",
  "ready",
];

function toHandling(h: VerifiedResponse["handling"]): Handling {
  switch (h) {
    case "reframe_to_teaching":
      return "reframed";
    case "block_with_redirect":
      return "blocked";
    default:
      // answer | answer_with_disclaimer | insufficient_evidence
      return "standard";
  }
}

function toConfidence(resp: VerifiedResponse): ConfidenceTier {
  if (resp.handling === "insufficient_evidence") return "insufficient";
  return TIER_TO_CONFIDENCE[resp.confidenceTier];
}

function toVariant(resp: VerifiedResponse, mode: AnswerMode): Query["variant"] {
  if (resp.positions && resp.positions.length > 0) return "scholarly_dispute";
  switch (resp.handling) {
    case "reframe_to_teaching":
      return "reframed_sensitive";
    case "block_with_redirect":
      return "blocked_redirect";
    case "insufficient_evidence":
      return "insufficient_evidence";
    default:
      // A successful answer: reflect the requested presentation mode where the UI has a card for it.
      if (mode === "consensus") return "consensus";
      if (mode === "historical_development") return "historical_development";
      if (mode === "institutional_policy") return "institutional_policy";
      return "verified_cited";
  }
}

function adaptCitation(c: ApiCitation, index: number): Citation {
  const page = c.page ? Number.parseInt(c.page, 10) : NaN;
  return {
    marker: index + 1,
    sourceId: c.sourceId,
    chunkId: c.chunkId,
    excerpt: c.quote ?? c.title,
    page: Number.isNaN(page) ? undefined : page,
    classification: "exact",
    quoteIntegrity: 1,
    approval: "approved",
    // Additive display fields (see types.ts) so cards render real data without the mock `sources` lookup.
    title: c.title,
    author: c.father ?? undefined,
    work: c.work ?? undefined,
    chunkHash: c.chunkHash,
  };
}

export interface AdaptContext {
  question: string;
  mode: AnswerMode;
  scope: string;
  language: string;
  asker: string;
  latencyMs: number;
}

export function toQuery(resp: VerifiedResponse, ctx: AdaptContext): Query {
  const citations = resp.citations.map(adaptCitation);
  const variant = toVariant(resp, ctx.mode);
  const tokens = (resp.usage.promptTokens ?? 0) + (resp.usage.completionTokens ?? 0);

  const positions = resp.positions?.map((p) => ({
    name: p.name,
    thesis: p.thesis,
    // Backend positions reference citationIds; resolve them to sourceIds for the dispute card.
    sourceIds: resp.citations
      .filter((c) => p.citationIds.includes(c.citationId))
      .map((c) => c.sourceId),
  }));

  return {
    id: resp.runId ?? `run_${Date.now()}`,
    question: ctx.question,
    mode: ctx.mode,
    scope: ctx.scope,
    language: ctx.language,
    asked: "just now",
    asker: ctx.asker,
    variant,
    confidence: toConfidence(resp),
    handling: toHandling(resp.handling),
    cached: resp.servedFromCache,
    body: resp.answer,
    citations,
    evidence: {
      admittedChunks: citations.length,
      suppressed: 0,
      policyExclusions: 0,
      coverage: TIER_TO_COVERAGE[resp.confidenceTier],
    },
    trace: {
      classification: resp.handling.replace(/_/g, " "),
      retrievalPlan: variant.replace(/_/g, " "),
      modelRoute: resp.usage.modelRouteId ?? "—",
      latencyMs: ctx.latencyMs,
      tokens,
      steps: resp.handling === "block_with_redirect" ? ["classified", "ready"] : COMPLETED_STEPS,
    },
    reframed: resp.reframing.wasReframed
      ? {
          original: resp.reframing.originalQuery ?? ctx.question,
          reframed: resp.reframing.reframedQuery ?? "",
          reason: resp.reframing.disclosureText ?? "Reframed for safe handling.",
        }
      : undefined,
    positions,
    blocked:
      resp.handling === "block_with_redirect"
        ? {
            reason: resp.verification.failureReason ?? "Redirected at the safety gate.",
            redirect: resp.answer,
          }
        : undefined,
  };
}
