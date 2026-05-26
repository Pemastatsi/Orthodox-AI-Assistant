"""Anthropic adapter — Phase 1 owner of A1/A2 query analysis, A5 composition, and the
optional A6 consistency judge.

Per `provider-interface.md`:
- `generate_structured` uses Anthropic's tool-use mode for guaranteed JSON output.
- `stream_text` emits only `progress` events (Phase 1 prohibits token-level streaming).
- `embed_texts` raises `NotImplementedError`; OpenAI owns the embedding route.

Forbidden outside this module: `import anthropic`. See `provider-interface.md` §Forbidden.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Literal, cast

from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    AuthenticationError,
    RateLimitError,
)
from anthropic.types import Message, MessageParam, TextBlock, ToolParam, ToolUseBlock

from app.adapters.providers.base import ChatMessage, StreamEvent, StructuredResult
from app.core.config import Settings, get_settings
from app.core.errors import (
    ProviderAuthError,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderRefusedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

_STRUCTURED_TOOL_NAME = "return_structured_result"

FinishReason = Literal["stop", "length", "refusal"]


class AnthropicProvider:
    """Anthropic chat-completions adapter scoped to Phase 1 needs.

    One async client per instance; the API layer constructs a single instance per process
    and reuses it. Per-call options (`route_id`, `tenant_id`, etc.) are logged with the
    structured logger but never sent in the request body.
    """

    name = "anthropic"

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        model: str | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self._model = model or cfg.anthropic_model_a5
        self._client = AsyncAnthropic(api_key=cfg.anthropic_api_key)

    @property
    def model(self) -> str:
        return self._model

    @property
    def supports_prompt_cache(self) -> bool:
        return True

    @property
    def supports_batch(self) -> bool:
        return False

    @property
    def supports_json_mode(self) -> bool:
        return True

    @property
    def supports_embeddings(self) -> bool:
        return False

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
    ) -> StructuredResult:
        system, user_messages = _split_system_messages(messages)
        tool: ToolParam = {
            "name": _STRUCTURED_TOOL_NAME,
            "description": "Return the structured result.",
            "input_schema": schema,
        }
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_output_tokens,
                temperature=temperature,
                system=system,
                messages=user_messages,
                tools=[tool],
                tool_choice={"type": "tool", "name": _STRUCTURED_TOOL_NAME},
                timeout=timeout_s,
            )
        except APITimeoutError as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except RateLimitError as exc:
            raise ProviderRateLimitedError(str(exc)) from exc
        except AuthenticationError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except APIConnectionError as exc:
            raise ProviderUnavailableError(str(exc)) from exc
        except APIStatusError as exc:
            raise ProviderUnavailableError(str(exc)) from exc

        finish_reason: FinishReason = _map_stop_reason(response.stop_reason)
        if finish_reason == "refusal":
            logger.info(
                "anthropic.refusal",
                run_id=run_id,
                tenant_id=tenant_id,
                stop_reason=response.stop_reason,
            )
            raise ProviderRefusedError("Anthropic returned a refusal")

        tool_input = _extract_tool_use(response)
        if tool_input is None:
            raise ProviderInvalidResponseError(
                "Anthropic structured response missing tool_use block"
            )

        usage = response.usage
        return StructuredResult(
            data=tool_input,
            raw_text=json.dumps(tool_input, ensure_ascii=False),
            prompt_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            model_route_id=route_id,
            finish_reason=finish_reason,
            cached_prefix_tokens=int(
                getattr(usage, "cache_read_input_tokens", 0) or 0
            ),
        )

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
    ) -> str:
        del route_id, tenant_id, run_id
        system, user_messages = _split_system_messages(messages)
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_output_tokens,
                temperature=temperature,
                system=system,
                messages=user_messages,
                timeout=timeout_s,
            )
        except APITimeoutError as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except RateLimitError as exc:
            raise ProviderRateLimitedError(str(exc)) from exc
        except AuthenticationError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except APIConnectionError as exc:
            raise ProviderUnavailableError(str(exc)) from exc
        except APIStatusError as exc:
            raise ProviderUnavailableError(str(exc)) from exc

        finish_reason = _map_stop_reason(response.stop_reason)
        if finish_reason == "refusal":
            raise ProviderRefusedError("Anthropic returned a refusal")

        chunks = [block.text for block in response.content if isinstance(block, TextBlock)]
        return "".join(chunks)

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
    ) -> AsyncIterator[StreamEvent]:
        """Phase 1: progress events only — no token streaming (provider-interface.md §Phase 1
        prohibition). We yield a single `progress` event when the request starts and a `done`
        event with the fully-assembled text when it finishes."""
        del tenant_id, run_id
        system, user_messages = _split_system_messages(messages)
        model = self._model
        client = self._client

        async def _iter() -> AsyncIterator[StreamEvent]:
            yield StreamEvent(type="progress", payload={"stage": "generate_text:start"})
            try:
                response = await client.messages.create(
                    model=model,
                    max_tokens=max_output_tokens,
                    temperature=temperature,
                    system=system,
                    messages=user_messages,
                    timeout=timeout_s,
                )
            except APITimeoutError as exc:
                yield StreamEvent(type="error", payload={"code": "provider_unavailable"})
                raise ProviderTimeoutError(str(exc)) from exc
            except APIConnectionError as exc:
                yield StreamEvent(type="error", payload={"code": "provider_unavailable"})
                raise ProviderUnavailableError(str(exc)) from exc

            text = "".join(
                b.text for b in response.content if isinstance(b, TextBlock)
            )
            yield StreamEvent(type="done", payload={"text": text, "routeId": route_id})

        return _iter()

    async def count_tokens(self, *, text: str, model: str) -> int:
        try:
            response = await self._client.messages.count_tokens(
                model=model or self._model,
                messages=[cast(MessageParam, {"role": "user", "content": text})],
            )
            return int(response.input_tokens)
        except APIConnectionError as exc:
            raise ProviderUnavailableError(str(exc)) from exc
        except APIStatusError:
            # Fallback: tiktoken-style rough estimate.
            return max(1, len(text) // 4)

    async def embed_texts(
        self,
        *,
        texts: list[str],
        route_id: str,
        tenant_id: str,
        run_id: str,
        timeout_s: float = 30.0,
    ) -> list[list[float]]:
        del texts, route_id, tenant_id, run_id, timeout_s
        raise NotImplementedError(
            "AnthropicProvider does not support embeddings; use the OpenAI route."
        )


def _split_system_messages(
    messages: list[ChatMessage],
) -> tuple[str, list[MessageParam]]:
    system_parts = [m.content for m in messages if m.role == "system"]
    user_messages: list[MessageParam] = [
        cast(MessageParam, {"role": m.role, "content": m.content})
        for m in messages
        if m.role in ("user", "assistant")
    ]
    return "\n\n".join(system_parts), user_messages


def _map_stop_reason(stop_reason: str | None) -> FinishReason:
    if stop_reason == "max_tokens":
        return "length"
    if stop_reason == "refusal":
        return "refusal"
    return "stop"


def _extract_tool_use(response: Message) -> dict[str, Any] | None:
    for block in response.content:
        if isinstance(block, ToolUseBlock) and block.name == _STRUCTURED_TOOL_NAME:
            input_obj: Any = block.input
            if isinstance(input_obj, dict):
                return input_obj
            if isinstance(input_obj, str):
                try:
                    parsed = json.loads(input_obj)
                except json.JSONDecodeError:
                    return None
                if isinstance(parsed, dict):
                    return parsed
    return None


__all__ = ["AnthropicProvider"]
