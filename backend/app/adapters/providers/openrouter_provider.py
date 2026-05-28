"""OpenRouter adapter — generic OpenAI-compatible provider for A1/A5 structured generation.

Used by the live-LLM paraphrase suite (`tests/safety/test_20_queries_paraphrases.py`) to
route the same Haiku 4.5 model through OpenRouter rather than direct Anthropic,
consolidating billing into a single key. Production A1/A5 routing still goes through
AnthropicProvider per ADR-0006; this adapter is a parallel test-time path and is not
wired into `_get_anthropic_provider` / `get_query_analyzer_provider`.

Uses OpenAI-compatible tool calling for guaranteed schema compliance (equivalent to
AnthropicProvider's tool-use mode); `response_format={"type":"json_object"}` is weaker
and produces validation drift on ~5% of calls.

Forbidden outside this module: `import openai`. See `provider-interface.md` §Forbidden.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, Literal, cast

import openai
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)
from openai.types.chat.chat_completion_named_tool_choice_param import (
    ChatCompletionNamedToolChoiceParam,
)

from app.adapters.providers.base import ChatMessage, StreamEvent, StructuredResult
from app.core.config import Settings, get_settings
from app.core.errors import (
    ProviderAuthError,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

_STRUCTURED_TOOL_NAME = "return_structured_result"

FinishReason = Literal["stop", "length", "refusal"]


class OpenRouterProvider:
    """OpenAI-compatible adapter pointed at OpenRouter.

    One async client per instance. Constructed directly by tests; the production wiring
    factory in `app/api/v1/_deps.py` does not reference this class.
    """

    name = "openrouter"

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        model: str | None = None,
    ) -> None:
        cfg = settings or get_settings()
        self._model = model or cfg.openrouter_model_a1a2
        self._client = openai.AsyncOpenAI(
            api_key=cfg.openrouter_api_key,
            base_url=cfg.openrouter_base_url,
        )

    @property
    def model(self) -> str:
        return self._model

    @property
    def supports_prompt_cache(self) -> bool:
        return False

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
        del tenant_id, run_id  # available for downstream logging; not sent in request body
        tool: ChatCompletionToolParam = cast(
            ChatCompletionToolParam,
            {
                "type": "function",
                "function": {
                    "name": _STRUCTURED_TOOL_NAME,
                    "description": "Return the structured A1/A2 result.",
                    "parameters": schema,
                },
            },
        )
        tool_choice: ChatCompletionNamedToolChoiceParam = cast(
            ChatCompletionNamedToolChoiceParam,
            {"type": "function", "function": {"name": _STRUCTURED_TOOL_NAME}},
        )
        openai_messages: list[ChatCompletionMessageParam] = [
            cast(ChatCompletionMessageParam, {"role": m.role, "content": m.content})
            for m in messages
        ]
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=openai_messages,
                tools=[tool],
                tool_choice=tool_choice,
                temperature=temperature,
                max_tokens=max_output_tokens,
                timeout=timeout_s,
            )
        except APITimeoutError as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except RateLimitError as exc:
            raise ProviderRateLimitedError(str(exc)) from exc
        except AuthenticationError as exc:
            raise ProviderAuthError(str(exc)) from exc
        except (APIConnectionError, APIStatusError, BadRequestError) as exc:
            raise ProviderUnavailableError(str(exc)) from exc
        except openai.OpenAIError as exc:
            raise ProviderUnavailableError(str(exc)) from exc

        choice = response.choices[0]
        finish_reason: FinishReason = _map_finish_reason(choice.finish_reason)
        tool_calls = choice.message.tool_calls or []
        if not tool_calls:
            raise ProviderInvalidResponseError(
                "OpenRouter response missing tool_calls block"
            )
        first_call = tool_calls[0]
        function = getattr(first_call, "function", None)
        if function is None:
            raise ProviderInvalidResponseError(
                "OpenRouter tool_call has no function block (custom tool call?)"
            )
        arguments = function.arguments
        try:
            data = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise ProviderInvalidResponseError(
                f"OpenRouter tool_call arguments are not valid JSON: {arguments[:200]!r}"
            ) from exc
        if not isinstance(data, dict):
            raise ProviderInvalidResponseError(
                f"OpenRouter tool_call arguments must be a JSON object, got {type(data).__name__}"
            )

        usage = response.usage
        return StructuredResult(
            data=data,
            raw_text=arguments,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            model_route_id=route_id,
            finish_reason=finish_reason,
            cached_prefix_tokens=0,
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
        del messages, route_id, tenant_id, run_id, max_output_tokens, temperature, timeout_s
        raise NotImplementedError(
            "OpenRouterProvider serves A1 structured generation only in Phase 1."
        )

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
        del messages, route_id, tenant_id, run_id, max_output_tokens, temperature, timeout_s
        raise NotImplementedError("OpenRouterProvider does not stream in Phase 1.")

    async def count_tokens(self, *, text: str, model: str) -> int:
        del text, model
        raise NotImplementedError(
            "OpenRouterProvider does not implement count_tokens; use tiktoken."
        )

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
            "OpenRouterProvider does not implement embeddings; use OpenAIProvider."
        )


def _map_finish_reason(reason: str | None) -> FinishReason:
    if reason == "length":
        return "length"
    if reason == "content_filter":
        return "refusal"
    return "stop"


__all__ = ["OpenRouterProvider"]
