"""OpenAI adapter — Phase 1 is embeddings-only per ADR-0006.

`text-embedding-3-small` is the certified embedding route; the other LLMProvider methods raise
`NotImplementedError` because OpenAI is not a certified A1/A5 provider in Phase 1 (Anthropic owns
those routes; OpenAIProvider only exposes the embedding seam the ingestion worker needs).

Forbidden outside this module: `import openai`. See `provider-interface.md` §Forbidden imports.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import openai
from openai import APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError

from app.adapters.providers.base import ChatMessage, StreamEvent, StructuredResult
from app.core.config import Settings, get_settings
from app.core.errors import (
    ProviderAuthError,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

_OPENAI_EMBEDDING_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


def embedding_dimension_for(model: str) -> int:
    if model not in _OPENAI_EMBEDDING_DIMENSIONS:
        raise ProviderInvalidResponseError(f"Unknown OpenAI embedding model: {model}")
    return _OPENAI_EMBEDDING_DIMENSIONS[model]


class OpenAIProvider:
    """Phase 1 embeddings adapter.

    A single client is held per instance; the worker constructs one per process and reuses it.
    """

    name = "openai"

    def __init__(self, *, settings: Settings | None = None, model: str | None = None) -> None:
        cfg = settings or get_settings()
        self._model = model or "text-embedding-3-small"
        self._dimension = embedding_dimension_for(self._model)
        self._client = openai.AsyncOpenAI(api_key=cfg.openai_api_key)

    @property
    def model(self) -> str:
        return self._model

    @property
    def embedding_dimension(self) -> int:
        return self._dimension

    @property
    def supports_prompt_cache(self) -> bool:
        return False

    @property
    def supports_batch(self) -> bool:
        return False

    @property
    def supports_json_mode(self) -> bool:
        return False

    @property
    def supports_embeddings(self) -> bool:
        return True

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
        del messages, schema, route_id, tenant_id, run_id, max_output_tokens, temperature, timeout_s
        raise NotImplementedError("OpenAIProvider does not serve A1/A2 in Phase 1 (Anthropic does).")  # noqa: E501

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
        raise NotImplementedError("OpenAIProvider does not serve A5 in Phase 1 (Anthropic does).")

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
        raise NotImplementedError("OpenAIProvider does not stream in Phase 1.")

    async def count_tokens(self, *, text: str, model: str) -> int:
        del text, model
        raise NotImplementedError("Use tiktoken directly via chunking_service for token counts.")

    async def embed_texts(
        self,
        *,
        texts: list[str],
        route_id: str,
        tenant_id: str,
        run_id: str,
        timeout_s: float = 30.0,
    ) -> list[list[float]]:
        del route_id, tenant_id, run_id  # available for downstream logging; not used by SDK call
        if not texts:
            return []
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
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
        except openai.OpenAIError as exc:
            raise ProviderUnavailableError(str(exc)) from exc

        vectors = [list(d.embedding) for d in response.data]
        if len(vectors) != len(texts):
            raise ProviderInvalidResponseError(
                f"OpenAI returned {len(vectors)} vectors for {len(texts)} inputs"
            )
        for v in vectors:
            if len(v) != self._dimension:
                raise ProviderInvalidResponseError(
                    f"OpenAI embedding dimension {len(v)} != expected {self._dimension}"
                )
        return vectors


__all__ = ["OpenAIProvider", "embedding_dimension_for"]
