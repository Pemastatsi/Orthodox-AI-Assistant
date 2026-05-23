"""LLMProvider Protocol per docs/contracts/provider-interface.md.

Phase 1: AnthropicAdapter and OpenAIAdapter land in T-004. T-001 ships the Protocol surface
and the typed shapes the orchestrator imports."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class StructuredResult:
    data: dict[str, Any]
    raw_text: str
    prompt_tokens: int
    completion_tokens: int
    model_route_id: str
    finish_reason: Literal["stop", "length", "refusal"]
    cached_prefix_tokens: int = 0


@dataclass(frozen=True)
class StreamEvent:
    type: Literal["progress", "done", "error"]
    payload: dict[str, Any]


@runtime_checkable
class LLMProvider(Protocol):
    """The single typed surface every provider adapter implements.

    Forbidden: importing `anthropic` or `openai` outside `app/adapters/providers/`.
    See `docs/contracts/provider-interface.md`."""

    name: str

    async def generate_structured(
        self,
        *,
        messages: list[ChatMessage],
        schema: dict[str, Any],
        route_id: str,
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

    def stream_text(
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
        route_id: str,
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
