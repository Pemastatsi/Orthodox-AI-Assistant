import { z } from "zod"

export default z.object({ "answer": z.string(), "confidenceTier": z.enum(["GREEN","YELLOW","RED"]), "handling": z.enum(["answer","answer_with_disclaimer","reframe_to_teaching","block_with_redirect","insufficient_evidence"]), "citations": z.array(z.object({ "citationId": z.string(), "chunkId": z.string(), "sourceId": z.string(), "title": z.string(), "work": z.union([z.string(), z.null()]).optional(), "father": z.union([z.string(), z.null()]).optional(), "page": z.union([z.string(), z.null()]).optional(), "timestamp": z.union([z.string(), z.null()]).optional(), "quote": z.union([z.string(), z.null()]).optional(), "sourceHash": z.string().regex(new RegExp("^sha256:[0-9a-f]{64}$")).describe("Source-level integrity hash carried from EvidencePacket admittedChunks.sourceHash."), "chunkHash": z.string().regex(new RegExp("^sha256:[0-9a-f]{64}$")).describe("Chunk-level integrity hash carried from EvidencePacket admittedChunks.chunkHash."), "approved": z.literal(true).describe("Always true. A6 admits only approved chunks; this is restated on the user-facing citation for downstream consumers and audit."), "corpusOrigin": z.enum(["tenant","starter_corpus"]).describe("Disclosure of the corpus the chunk came from. starter_corpus only appears when the tenant has the (Phase 2) feature enabled.") }).strict()), "verification": z.object({ "passed": z.boolean(), "checkedAt": z.string().datetime({ offset: true }), "verifierVersion": z.string(), "failureReason": z.union([z.string(), z.null()]).optional() }), "reframing": z.object({ "wasReframed": z.boolean(), "originalQuery": z.union([z.string(), z.null()]).optional(), "reframedQuery": z.union([z.string(), z.null()]).optional(), "disclosureText": z.union([z.string(), z.null()]).optional() }), "usage": z.object({ "servedAnswerCount": z.number().int().gte(0).lte(1), "freshModelRunCount": z.number().int().gte(0).lte(1), "modelRouteId": z.union([z.string(), z.null()]), "promptTokens": z.union([z.number().int().gte(0), z.null()]).optional(), "completionTokens": z.union([z.number().int().gte(0), z.null()]).optional() }).strict().describe("Per-request accounting per ADR 0005. servedAnswerCount is always incremented (cache or fresh). freshModelRunCount only on cache miss."), "runId": z.string().describe("ULID identifying the pipeline run. Always present. Even on hard-safety bypass, a runId is minted and a minimal run_traces row is persisted (see phase1-implementation-contract.md §Run-trace persistence is unconditional).").optional(), "servedFromCache": z.boolean(), "schemaVersion": z.string().describe("Format YYYY-MM-DD.NN per docs/contracts/api-versioning.md."), "positions": z.union([z.array(z.object({ "name": z.string().describe("Neutral label for the position, drawn from the evidence (father/work/council/era). Never model-invented."), "thesis": z.string().describe("Short composed statement of this position, verified against this column's chunks only."), "citationIds": z.array(z.string()).describe("citationId values from the top-level citations[] belonging to THIS column only."), "confidenceTier": z.enum(["GREEN","YELLOW","RED"]).describe("Confidence for this column alone, via the same A4 coverage rule applied to the column's chunks.") }).strict()).describe("Present (non-null) only for scholarly_dispute answers (T-006 §Scholarly Dispute UX). Competing positions rendered side-by-side; each position's citationIds are scoped to that column and reference the top-level citations[] — citations are NEVER aggregated across columns. Add-only optional field (api-versioning.md §Add-only changes do not bump), so schemaVersion is unchanged."), z.null().describe("Present (non-null) only for scholarly_dispute answers (T-006 §Scholarly Dispute UX). Competing positions rendered side-by-side; each position's citationIds are scoped to that column and reference the top-level citations[] — citations are NEVER aggregated across columns. Add-only optional field (api-versioning.md §Add-only changes do not bump), so schemaVersion is unchanged.")]).describe("Present (non-null) only for scholarly_dispute answers (T-006 §Scholarly Dispute UX). Competing positions rendered side-by-side; each position's citationIds are scoped to that column and reference the top-level citations[] — citations are NEVER aggregated across columns. Add-only optional field (api-versioning.md §Add-only changes do not bump), so schemaVersion is unchanged.").optional() }).strict().and(z.any().superRefine((x, ctx) => {
    const schemas = [z.object({ "handling": z.enum(["answer","answer_with_disclaimer","reframe_to_teaching"]).optional() }).describe("Successful response paths must carry a runId."), z.object({ "handling": z.enum(["block_with_redirect","insufficient_evidence"]).optional() }).describe("Always present. Even on hard-safety bypass, a runId is minted and a minimal run_traces row is persisted (see phase1-implementation-contract.md §Run-trace persistence is unconditional).")];
    const { errors, failed } = schemas.reduce<{
      errors: z.core.$ZodIssue[];
      failed: number;
    }>(
      ({ errors, failed }, schema) =>
        ((result) =>
          result.error
            ? {
                errors: [...errors, ...result.error.issues],
                failed: failed + 1,
              }
            : { errors, failed })(
          schema.safeParse(x),
        ),
      { errors: [], failed: 0 },
    );
    const passed = schemas.length - failed;
    if (passed !== 1) {
      ctx.addIssue(errors.length ? {
        path: [],
        code: "invalid_union",
        errors: [errors],
        message: "Invalid input: Should pass single schema. Passed " + passed,
      } : {
        path: [],
        code: "custom",
        errors: [errors],
        message: "Invalid input: Should pass single schema. Passed " + passed,
      });
    }
  }))
