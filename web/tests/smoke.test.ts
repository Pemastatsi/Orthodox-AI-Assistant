import { describe, expect, it } from "vitest";

import errors from "../lib/i18n/errors.en.json";

describe("i18n error catalog", () => {
  it("exposes a fallback for unknown error codes", () => {
    // F-24: unknown error codes must fall back to errors.en.json#unknown_error.
    const lookup = (code: string): string =>
      (errors as Record<string, string>)[code] ??
      (errors as Record<string, string>)["unknown_error"];
    expect(lookup("not_a_real_code")).toBe(
      (errors as Record<string, string>)["unknown_error"],
    );
    expect(lookup("auth_missing_token")).toBe(
      (errors as Record<string, string>)["auth_missing_token"],
    );
  });

  it("includes an entry for every error-taxonomy.md code", () => {
    const required = [
      "auth_missing_token",
      "auth_invalid_token",
      "auth_missing_org",
      "tenant_not_found",
      "tenant_inactive",
      "tenant_mismatch",
      "forbidden_role",
      "forbidden_visibility",
      "validation_failed",
      "unsupported_media_type",
      "not_found",
      "corpus_empty",
      "unapproved_chunk",
      "safety_blocked",
      "verifier_failed",
      "quota_exceeded",
      "rate_limited",
      "provider_unavailable",
      "provider_refused",
      "provider_invalid_response",
      "cache_unavailable",
      "qdrant_unavailable",
      "vector_store_unavailable",
      "db_unavailable",
      "ingest_invalid",
      "ingest_too_large",
      "webhook_bad_signature",
      "webhook_replay",
      "precondition_failed",
      "feature_deferred",
      "internal_error",
      "unknown_error",
    ];
    const keys = Object.keys(errors as Record<string, string>).filter(
      (k) => !k.startsWith("$"),
    );
    for (const code of required) {
      expect(keys, `missing i18n entry for ${code}`).toContain(code);
    }
  });
});
