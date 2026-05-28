"""Unit tests for `app.adapters.providers.openrouter_provider.OpenRouterProvider`.

All tests mock the `AsyncOpenAI` client so they run without network access. Live-LLM
exercise of the adapter is covered by `tests/safety/test_20_queries_paraphrases.py`
(env-gated on OPENROUTER_API_KEY).
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from app.adapters.providers.base import ChatMessage
from app.adapters.providers.openrouter_provider import OpenRouterProvider
from app.core.errors import (
    ProviderAuthError,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


def _fake_response(
    arguments: str = '{"ok": true}',
    finish_reason: str = "stop",
    prompt_tokens: int = 10,
    completion_tokens: int = 4,
):
    tool_call = SimpleNamespace(function=SimpleNamespace(arguments=arguments))
    choice = SimpleNamespace(
        message=SimpleNamespace(tool_calls=[tool_call]),
        finish_reason=finish_reason,
    )
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
    )
    return SimpleNamespace(choices=[choice], usage=usage)


def _provider_with_client(create_mock: AsyncMock) -> OpenRouterProvider:
    """Construct an OpenRouterProvider with the create() method mocked."""
    with patch("app.adapters.providers.openrouter_provider.openai.AsyncOpenAI") as ctor:
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
        )
        ctor.return_value = client
        return OpenRouterProvider()


@pytest.fixture()
def messages() -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content="You are a classifier."),
        ChatMessage(role="user", content="Test query"),
    ]


@pytest.fixture()
def schema() -> dict[str, object]:
    return {"type": "object", "properties": {"ok": {"type": "boolean"}}}


async def test_generate_structured_happy_path(messages, schema):
    create = AsyncMock(return_value=_fake_response('{"answer": 42}'))
    provider = _provider_with_client(create)

    result = await provider.generate_structured(
        messages=messages,
        schema=schema,
        route_id="qa_analyze_openrouter@test",
        tenant_id="tn_t",
        run_id="run_t",
    )

    assert result.data == {"answer": 42}
    assert result.raw_text == '{"answer": 42}'
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 4
    assert result.model_route_id == "qa_analyze_openrouter@test"
    assert result.finish_reason == "stop"
    create.assert_awaited_once()
    kwargs = create.await_args.kwargs
    assert kwargs["tool_choice"]["function"]["name"] == "return_structured_result"
    assert kwargs["tools"][0]["function"]["parameters"] is schema


async def test_generate_structured_invalid_json_raises(messages, schema):
    create = AsyncMock(return_value=_fake_response("not-json-at-all"))
    provider = _provider_with_client(create)

    with pytest.raises(ProviderInvalidResponseError) as ei:
        await provider.generate_structured(
            messages=messages,
            schema=schema,
            route_id="r",
            tenant_id="t",
            run_id="x",
        )
    assert "not valid JSON" in str(ei.value)


async def test_generate_structured_missing_tool_call_raises(messages, schema):
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(tool_calls=None), finish_reason="stop"
            )
        ],
        usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0),
    )
    create = AsyncMock(return_value=response)
    provider = _provider_with_client(create)

    with pytest.raises(ProviderInvalidResponseError) as ei:
        await provider.generate_structured(
            messages=messages,
            schema=schema,
            route_id="r",
            tenant_id="t",
            run_id="x",
        )
    assert "missing tool_calls" in str(ei.value)


def _fake_http_response(status_code: int):
    import httpx

    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return httpx.Response(status_code=status_code, request=request)


def _fake_http_request():
    import httpx

    return httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")


async def test_generate_structured_rate_limit_error_maps(messages, schema):
    from openai import RateLimitError

    err = RateLimitError("limit hit", response=_fake_http_response(429), body={})
    create = AsyncMock(side_effect=err)
    provider = _provider_with_client(create)

    with pytest.raises(ProviderRateLimitedError):
        await provider.generate_structured(
            messages=messages,
            schema=schema,
            route_id="r",
            tenant_id="t",
            run_id="x",
        )


async def test_generate_structured_auth_error_maps(messages, schema):
    from openai import AuthenticationError

    err = AuthenticationError("bad key", response=_fake_http_response(401), body={})
    create = AsyncMock(side_effect=err)
    provider = _provider_with_client(create)

    with pytest.raises(ProviderAuthError):
        await provider.generate_structured(
            messages=messages,
            schema=schema,
            route_id="r",
            tenant_id="t",
            run_id="x",
        )


async def test_generate_structured_timeout_error_maps(messages, schema):
    from openai import APITimeoutError

    err = APITimeoutError(request=_fake_http_request())
    create = AsyncMock(side_effect=err)
    provider = _provider_with_client(create)

    with pytest.raises(ProviderTimeoutError):
        await provider.generate_structured(
            messages=messages,
            schema=schema,
            route_id="r",
            tenant_id="t",
            run_id="x",
        )


async def test_generate_structured_connection_error_maps(messages, schema):
    from openai import APIConnectionError

    err = APIConnectionError(request=_fake_http_request())
    create = AsyncMock(side_effect=err)
    provider = _provider_with_client(create)

    with pytest.raises(ProviderUnavailableError):
        await provider.generate_structured(
            messages=messages,
            schema=schema,
            route_id="r",
            tenant_id="t",
            run_id="x",
        )


async def test_other_llmprovider_methods_raise_not_implemented(messages):
    provider = _provider_with_client(AsyncMock())

    with pytest.raises(NotImplementedError):
        await provider.generate_text(
            messages=messages, route_id="r", tenant_id="t", run_id="x"
        )
    with pytest.raises(NotImplementedError):
        await provider.count_tokens(text="hi", model="m")
    with pytest.raises(NotImplementedError):
        await provider.embed_texts(texts=["a"], route_id="r", tenant_id="t", run_id="x")


def test_provider_protocol_properties(messages):
    del messages
    provider = _provider_with_client(AsyncMock())
    assert provider.name == "openrouter"
    assert provider.supports_json_mode is True
    assert provider.supports_prompt_cache is False
    assert provider.supports_batch is False
    assert provider.supports_embeddings is False


# round-trip safety: encoder used in the happy path must round-trip with json.loads
def test_json_round_trip_invariant():
    payload = {"classifiedQuery": {"sensitivity_primary": "normal"}}
    assert json.loads(json.dumps(payload)) == payload
