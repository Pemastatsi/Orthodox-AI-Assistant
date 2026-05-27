# T-2XX: Phase-2 Platform Bundle

Status: Phase 2 — opens after Phase 1 → Phase 2 exit criteria pass (per `phase1-implementation-contract.md` §Exit Criteria).

The card bundles four independently-reversible platform swaps. Each part can land separately; they share this card only because they are sequenced around the Phase-2 launch event.

## Required Reads

- REC-025 in the 2026-05-22 frontier meta-evaluation.
- `docs/contracts/observability.md` §"OpenTelemetry" — Phase-2 sink wiring.
- `docs/runbooks/frontier-sync.md` — the quarterly process that may have already invalidated some of these candidates by Phase 2.

## Part (a) — Redis → Valkey 8.1

- **Why:** ≈20% lower cost; license stability (Linux Foundation, BSD-3) vs Redis BSL/SSPL.
- **How:** Valkey is a RESP drop-in. Replay the cache-key V1–V4 reference vectors (`tests/unit/test_cache_key.py`) against a Valkey instance before cutover.
- **Acceptance:** all cache-key reference vectors match; p99 latency at or below the Redis baseline; cost reduction confirmed on the first full billing cycle.

## Part (b) — Clerk → WorkOS evaluation (or full swap)

- **Trigger:** SSO connections exceed 5 enterprise customers OR Clerk MAO costs become dominant.
- **Why:** $0 to 1M MAU on WorkOS; $125/SSO connection; first-class immutable audit logs.
- **How:** Dual-path evaluation per the existing auth-context contract. Preserve `org_id` JWT claim semantics + HMAC webhook signing during the migration window.
- **Acceptance:** zero auth regressions in `tests/integration/test_auth_context.py`; founder Phase-2 sign-off `audit_entries` row continues to land.

## Part (c) — Langfuse self-host

- **Why:** Per-trace cost + tree views for LLM observability without SaaS egress (closed-corpus posture preserved). MIT-licensed since Jan 2026 ClickHouse acquisition.
- **How:** Stand up the Langfuse stack (Postgres + ClickHouse + Langfuse server) on Railway custom-Docker. Wire the OTel exporter from REC-010 to Langfuse's OTel ingest endpoint. Extend Langfuse's `mask` hook to mirror the structlog/OTel redaction rules from `observability.md`.
- **Acceptance:** all traces from the past 7 days are queryable in Langfuse; no chunk text or query text appears in any Langfuse record (validated against the redaction list).

## Part (d) — Different-family A6 judge

- **Why:** Once Haiku 4.5 takes over A1/A2 + A6 (REC-006), having the judge in the same model family as the upstream raises bias-resonance risk. A different family judge (e.g., Gemini 3 Flash or GPT-5-mini) reduces the resonance.
- **How:** New `ModelRoute` row for `purpose='verifier_judge'` with a non-Anthropic provider. Re-cert through the same retrieval-eval-judge gate at `retrieval-eval-suite.md`.
- **Acceptance:** judge agreement rate with the prior Haiku judge on a fixed gold-set sample is between 0.85 and 0.95 (not identical — that would mean no independent signal; not below 0.85 — that would mean the new judge has different calibration that needs retuning).

## Forbidden Scope

- No bundle PR — each part lands as a separate PR with its own review.
- No regressions on Phase-2 exit criteria during any part of the bundle.
- No SaaS LLM-observability backend (Logfire, Datadog LLM Obs, Braintrust cloud) — they violate the closed-corpus posture by egressing Confidential traffic.

## Notes for Future Sessions

- Re-run `docs/runbooks/frontier-sync.md` before opening any part of this bundle. The 2026-05-22 candidate list may have been superseded by 2026/2027 entrants.
- Parts (a) and (c) are infrastructure swaps with low theological-safety risk. Parts (b) and (d) touch auth/model-routing surfaces and need extra care.
