# Provider Interface

Status: Canonical
Date: 2026-05-02

This document defines the abstract interface every LLM/embedding provider adapter implements. Implemented in `app/adapters/providers/base.py`. Concrete adapters: `anthropic_adapter.py`, `openai_adapter.py`. Per ADR 0004, only certified `ModelRoute` entries (`docs/schemas/model-route.schema.json`) may serve production traffic.

## Goals

- A single typed surface so the orchestrator does not import provider SDKs.
- Predictable error mapping so the rest of the app deals only with codes from `docs/contracts/error-taxonomy.md`.
- A structured-output path (`generate_structured`) that always returns schema-valid data or raises.
- A streaming path (`stream_text`) that emits progress events but does **not** stream draft answer text before A6 (per AGENTS.md and decision register row M).

## Protocol

```python
from typing import AsyncIterator, Protocol, runtime_checkable
from app.domain.models import StructuredResult, StreamEvent, ChatMessage

@runtime_checkable
class LLMProvider(Protocol):
    name: str               # 'anthropic' | 'openai'

    async def generate_structured(
        self,
        *,
        messages: list[ChatMessage],
        schema: dict,                    # JSON Schema dict; output is validated against it
        route_id: str,                   # certified ModelRoute.routeId
        tenant_id: str,
        run_id: str,
        max_output_tokens: int = 1024,
        temperature: float = 0.0,
        timeout_s: float = 30.0,
    ) -> StructuredResult: ...

    async def generate_text(
        self,
        *,
        messages: list[ChatMessage],
        route_id: str,
        tenant_id: str,
        run_id: str,
        max_output_tokens: int = 1024,
        temperature: float = 0.0,
        timeout_s: float = 60.0,
    ) -> str: ...

    async def stream_text(
        self,
        *,
        messages: list[ChatMessage],
        route_id: str,
        tenant_id: str,
        run_id: str,
        max_output_tokens: int = 1024,
        temperature: float = 0.0,
        timeout_s: float = 60.0,
    ) -> AsyncIterator[StreamEvent]: ...

    async def count_tokens(
        self,
        *,
        text: str,
        model: str,
    ) -> int: ...

    async def embed_texts(
        self,
        *,
        texts: list[str],
        route_id: str,                  # certified ModelRoute.routeId with purpose='embedding'
        tenant_id: str,
        run_id: str,
        timeout_s: float = 30.0,
    ) -> list[list[float]]: ...

    @property
    def supports_prompt_cache(self) -> bool: ...

    @property
    def supports_batch(self) -> bool: ...

    @property
    def supports_json_mode(self) -> bool: ...

    @property
    def supports_embeddings(self) -> bool: ...
```

`embed_texts` exists so that ingestion and flagged-query workers honor the layering rule "no provider SDK import outside `adapters/providers/`" (per `docs/contracts/code-gen-guide.md` Forbidden Patterns). Callers:

- **Allowed:** `app/workers/tasks/embedding.py` (chunk indexing), `app/workers/tasks/flagged_embedding.py` (clustering, decision register row 4).
- **Forbidden:** any A1/A2/A3/A4/A5/A6 agent. Embeddings are an indexing concern, not an answer-time concern. A3 reads pre-indexed vectors from Qdrant; it never calls `embed_texts`.

Returned vectors must match `chunk.embeddingDimension` and the `route_id`'s registered model (validated at ingestion and rejected as `provider_invalid_response` if dimensions disagree). Implementations raise `ProviderUnavailableError`, `ProviderRateLimitedError`, or `ProviderTimeoutError` per the existing error mapping. A provider whose `supports_embeddings` is `False` raises `NotImplementedError` immediately on `embed_texts`; the route registry must not certify a non-embedding provider for an `embedding` purpose.

## `StructuredResult`

```python
@dataclass(frozen=True)
class StructuredResult:
    data: dict                  # validated against schema
    raw_text: str               # the raw model output before parsing
    prompt_tokens: int
    completion_tokens: int
    model_route_id: str
    finish_reason: str          # 'stop' | 'length' | 'refusal'
    cached_prefix_tokens: int   # 0 if no prompt cache
```

If the provider returns content that fails schema validation, the adapter retries up to 1 time with a stricter system message. A second failure raises `ProviderInvalidResponseError` (mapped to `provider_invalid_response`).

## `StreamEvent`

```python
@dataclass(frozen=True)
class StreamEvent:
    type: Literal['progress', 'token', 'done', 'error']
    payload: dict   # shape depends on type
```

The `query_orchestrator` consumes only `progress` and `done` events when `streamProgress=true`. `token` events are dropped before A6 verification — they are present only for non-user-facing flows (e.g., admin Prompt Lab preview when one is added in a later phase).

## Error Mapping

Each adapter catches its provider's exceptions and raises one of these typed exceptions, which the API layer maps to error codes:

| Adapter exception | API code | HTTP | Retryable |
|---|---|---|---|
| `ProviderTimeoutError` | `provider_unavailable` | 503 | yes |
| `ProviderUnavailableError` | `provider_unavailable` | 503 | yes |
| `ProviderRateLimitedError` | `rate_limited` | 429 | yes |
| `ProviderAuthError` | `internal_error` | 500 | no (config bug) |
| `ProviderRefusedError` | `provider_refused` | 502 | no |
| `ProviderInvalidResponseError` | `provider_invalid_response` | 502 | yes |
| `ProviderContextTooLargeError` | `validation_failed` | 422 | no |

Adapters MUST NOT leak the provider SDK's exception types upward.

## Outage Handling (No Cross-Provider Fallback in Phase 1)

When a `generate_*` or `embed_texts` call raises `ProviderUnavailableError` / `ProviderTimeoutError` / `ProviderRateLimitedError`, the orchestrator does **not** automatically retry the request on a different certified provider. The user-facing response is the matching error code from `docs/contracts/error-taxonomy.md` (`provider_unavailable`, `rate_limited`) with `Retry-After` populated. The client retries explicitly when ready.

Cross-provider failover is out of scope for Phase 1 (see ADR 0004 "Provider Outage Policy"). Adding it later requires:
1. A documented selection rule that does not violate route certification (you cannot fall back to an uncertified route).
2. Test coverage that demonstrates A5 still receives only evidence-grounded prompts when failover triggers.
3. An ADR update.

## Refusal Handling

When a provider returns a structured refusal (`finish_reason='refusal'` or equivalent):

1. The adapter raises `ProviderRefusedError` with a sanitized refusal text (no system-prompt leakage, no chain-of-thought).
2. For A1 calls: the orchestrator falls back to a deterministic classifier and proceeds; refusals on classification are common and not user-visible.
3. For A5 calls: the orchestrator returns a bounded fallback (`handling: insufficient_evidence`) to the user. Never expose the refusal text directly.

## JSON Mode

`supports_json_mode = True` means the adapter can ask the provider for guaranteed JSON output (Anthropic's `tool_use` mode or OpenAI's `response_format`). When supported, `generate_structured` uses it. When not supported, the adapter post-parses the raw text and validates against the schema.

## Streaming Boundaries

- The `query` endpoint accepts `streamProgress: true`. When set, the response is delivered as Server-Sent Events with `progress` events (`{stage: "...", at: "..."}`) followed by a single final `done` event whose payload is the full `VerifiedResponse`.
- Draft answer text is **never** streamed. Per decision register row M, streaming exists for UX progress only; final text appears all at once after A6 verification passes.

## Tool Use

A1/A2 use a structured tool call (Anthropic) or function call (OpenAI) defined by the schemas at `docs/schemas/classified-query.schema.json` and `docs/schemas/retrieval-plan.schema.json`. The adapter is responsible for shaping the tool definition; the orchestrator only passes the schema dict.

A5 does not use tool use. It returns a single structured object validated against an answer-mode-specific output schema (added in the implementation phase).

## Token Counting

`count_tokens` is best-effort. When the provider lacks an SDK token counter, the adapter falls back to `tiktoken` (OpenAI) or a documented estimator (Anthropic) and records `count_estimated: true` in the run trace stage entry.

## Configuration

Adapters read provider credentials only via `app/core/config.py`, which reads from `.env`. The adapter never reads `os.environ` directly. The adapter constructor is injected with a config object and an `httpx.AsyncClient`; the constructor validates that all required env vars are set and raises at startup if not.

## Forbidden

- Importing `anthropic` or `openai` outside `app/adapters/providers/`.
- Using a model or route name not present in the `model_routes` table with `certification_status='certified'`.
- Streaming raw text to the user before A6 has run (this is checked in tests).
- Logging request bodies that include raw chunk text or raw user query — those go to the run trace, not the log line.
- Any `# noqa` or `# type: ignore` in adapter code without a linked issue.
