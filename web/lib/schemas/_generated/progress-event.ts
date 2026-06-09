import { z } from "zod"

export default z.any().superRefine((x, ctx) => {
    const schemas = [z.any(), z.any(), z.any()];
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
  }).describe("Typed JSON payload (the SSE 'data:' line) for events emitted on POST /query when streamProgress=true. The SSE 'event:' line names the variant (progress | done | error). Each variant is validated against the corresponding $defs entry. Progress events are emitted zero or more times during a fresh model run; a single terminal done event carries the full VerifiedResponse; an error event may terminate the stream with a typed ApiError. Cache hits emit a single done event with no preceding progress events. See docs/contracts/code-gen-guide.md section Server-Sent Events for the wire format and docs/contracts/frontend-components.md for the StageStatus consumer.")
