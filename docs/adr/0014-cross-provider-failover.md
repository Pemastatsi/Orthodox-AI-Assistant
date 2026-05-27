# ADR 0014: Cross-Provider Failover (Phase 2 design, Phase 1 contract reservation)

Date: 2026-05-22
Status: Accepted

## Context

`docs/contracts/provider-interface.md` §"Outage Handling (No Cross-Provider Fallback in Phase 1)" records the Phase-1 posture: when a provider is unavailable, rate-limited, or times out, the user receives the typed error (`provider_unavailable`, `rate_limited`) with `Retry-After`; the client retries explicitly. ADR-0004 names "Provider Outage Policy" as a deferred decision.

This ADR closes that gap with a design that can be implemented when the Phase-2 trigger fires (any of: certified peer routes exist for a `purpose`; sustained provider incident pattern; user-visible latency degradation tied to a single provider). The ADR also records the latency-threshold circuit breaker discipline (GS-4, 2026-05-22) so failover is not limited to hard 5xx/network errors.

The Phase-1 contract reservation is the seam in `provider-interface.md` — every `LLMProvider` adapter already implements the same typed errors, so adding failover later does not require a Protocol change.

## Decision

When the trigger conditions are met, the orchestrator's provider-call wrapper performs **bounded cross-provider failover** under these strict rules:

1. **Certified-peer-only.** Failover targets must be `ModelRoute` rows of the same `purpose` with `certification_status = 'certified'`. Failover from `query_analyzer` may only land on another certified `query_analyzer` route; from `verifier_judge` to another `verifier_judge`. Embedding routes are excluded entirely (embedding spaces across providers are not interchangeable without re-embedding the entire corpus).

2. **Trigger conditions (any of):**
   - Network error from the underlying HTTP client (timeout, connection reset, TLS failure).
   - HTTP 5xx from the provider.
   - HTTP 429 (`rate_limited`) **only if** `Retry-After` exceeds the route's `max_acceptable_retry_after` config (default 5s).
   - **Latency-threshold breach (GS-4):** the provider's observed p95 latency for the last `latency_breaker_window_seconds` (default 60s) exceeds `latency_breaker_threshold_ms`, tuned per `ModelRoute`. Default thresholds: A5 composition `12000ms`; A1/A2 query analyzer `4000ms`; A6 verifier judge `3000ms`. The circuit opens for `latency_breaker_cooldown_seconds` (default 120s) after which a single probe call retests the primary; if successful, the circuit closes.

3. **Never on refusal.** A provider refusal (the model declined to answer; surfaced via `LLMProvider.is_refusal()`) MUST NOT trigger failover. Theological safety is content-driven, not infrastructure-driven, and silently routing a refused query to a different provider would undermine A6 verification and the closed-corpus contract. Refusals propagate as today (the answer path emits the appropriate bounded fallback per `phase1-implementation-contract.md` Appendix A).

4. **Audit trail.** Every failover invocation writes a `model_route_invocations` row carrying `failover_from_route_id` (the primary that failed), the trigger condition (`5xx`, `network`, `rate_limit`, `latency_breach`), and the elapsed time before failover. `RunTrace.stages[].details.failoverEvents` lists these events for operator review.

5. **At most one failover per stage.** If both the primary and the failover target return errors, the stage fails and the request returns the typed error to the user. The orchestrator does not chain three or more providers per stage.

6. **No circular failover.** A `ModelRoute` MAY list a single `failover_peer_route_id`. The peer's own peer reference MUST NOT cycle back to the primary. Validated at route certification time.

## Modal-hosted Llama-3-70B as a candidate A5 peer (GS-4)

A Modal-hosted Llama-3-70B endpoint is a concrete candidate certified A5 peer once it passes the ADR-0004 gates (safety-suite + retrieval-eval). Certification work is tracked in `docs/task_cards/phase1/T-009-embedding-upgrade.md` §A5 peer certification. The ADR does NOT hard-code Llama-3-70B as the failover target — any certified A5 peer can fill the role. Llama-3-70B is listed only as the most concrete near-term candidate given that Modal infrastructure is already proposed by REC-018 for the reranker GPU.

The closed-corpus invariant is preserved: A5 composition still draws only from `EvidencePacket`, regardless of which provider runs the composition.

## Interface Contract

### `provider-interface.md` extensions

```python
class ModelRoute(BaseModel):
    # ... existing fields ...
    failover_peer_route_id: str | None = None
    latency_breaker_threshold_ms: int | None = None     # None disables latency-based failover
    latency_breaker_window_seconds: int = 60
    latency_breaker_cooldown_seconds: int = 120
    max_acceptable_retry_after_seconds: int = 5
```

The provider-call wrapper (e.g., `app/services/llm/call_provider.py`) reads these fields from the active `ModelRoute` row, maintains a per-route latency moving-window in memory (and persists last-N samples to Redis for cross-replica consistency), and decides per-call whether to honor the primary or trip the breaker.

### `model_route_invocations` extensions

```sql
ALTER TABLE model_route_invocations
  ADD COLUMN failover_from_route_id text REFERENCES model_routes(route_id),
  ADD COLUMN failover_trigger      text;  -- '5xx' | 'network' | 'rate_limit' | 'latency_breach'
```

### `RunTrace.stages[].details.failoverEvents`

```json
{
  "failoverEvents": [
    {
      "fromRouteId": "anthropic_opus_4_7_a5_compose",
      "toRouteId":   "modal_llama3_70b_a5_compose",
      "trigger":     "latency_breach",
      "primaryElapsedMs": 12_543
    }
  ]
}
```

## Tests

- A primary route that returns `429 Retry-After: 30` with `max_acceptable_retry_after_seconds=5` triggers failover.
- A primary route that returns `429 Retry-After: 2` with the same config does NOT trigger failover (we wait).
- A provider refusal returns the refusal up the stack without invoking the peer.
- A latency-breach trigger fires when 95% of the last 60s of samples exceed the configured threshold, and the breaker enters cooldown for 120s before the next probe.
- A `ModelRoute` whose `failover_peer_route_id` points at an `experiment`-status route fails route validation at certification time.
- A circular peer reference (`A.peer = B`, `B.peer = A`) fails route validation.
- The `model_route_invocations` row for a failed-over call carries both the primary and peer `route_id` plus the `failover_trigger`.

## Consequences

- **Resilience.** Single-provider incidents (Anthropic outage, Modal outage, OpenAI degradation) no longer cause whole-request failure when a certified peer exists.
- **Cost surface.** Failover targets are still paid routes. Operators must monitor `model_route_invocations` for runaway failover patterns (which indicate either a real primary outage or a misconfigured latency threshold).
- **Bias resonance.** When the primary and peer are the same model family, latency-driven failover is observability; when they differ in family (Anthropic primary, Llama-3 peer), the user-visible composition style may differ subtly. The peer must pass the same safety-suite + retrieval-eval gates as the primary, so quality floor is preserved.
- **Refusal posture stays infrastructure-agnostic.** Theological safety is preserved by the carve-out that refusals never trigger failover.

## Alternatives Considered

- **Always-failover on any error.** Rejected: refusals would route around safety; rate-limit handling would break the upstream provider's contract with us.
- **Failover within the same provider's models** (e.g., Opus 4.7 → Sonnet 4.6 on Anthropic-only outage). Rejected as insufficient because the failure mode driving the design is provider-level outage, not model-level. Same-provider fallback is covered by `experiment` routes within a single `purpose` and does not need this ADR.
- **Client-side retry only.** Rejected: an Opus outage during a long composition leaves the user staring at a spinner for minutes before the typed error surfaces. Server-side circuit-breaking with peer failover is the right place for this concern.

## References

- ADR-0004 — provider/model route certification protocol (deferred this decision; now closed).
- `docs/contracts/provider-interface.md` §Outage Handling — Phase 1 posture preserved; extensions land in §JSON Mode and §Outage Handling once this ADR is implemented.
- `docs/task_cards/phase1/T-009-embedding-upgrade.md` — Modal Llama-3-70B A5 peer certification block (GS-4).
- 2026-05-22 frontier meta-evaluation report — REC-017 (cross-provider failover) and GS-4 (latency-threshold circuit breaker).
