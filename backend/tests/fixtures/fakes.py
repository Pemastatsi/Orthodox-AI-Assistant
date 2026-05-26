"""Deterministic fakes for the ingestion and query pipelines.

`FakeEmbeddingProvider` lets the worker run without OpenAI API keys; `FakeParser` lets the
pipeline run without real PDF bytes; `FakeStructuredProvider` lets T-003's QueryAnalyzer
exercise A1/A2 without the (T-004) Anthropic adapter.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Callable
from typing import Any

from app.adapters.parsers.base import ParsedBlock, ParsedPage
from app.adapters.providers.base import ChatMessage, StreamEvent, StructuredResult


def deterministic_embedding(seed: str, dim: int) -> list[float]:
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    repeated = (h * ((dim // len(h)) + 1))[:dim]
    return [(b - 128) / 128.0 for b in repeated]


class FakeEmbeddingProvider:
    name = "fake-openai"

    def __init__(self, *, dimension: int = 1536) -> None:
        self._dim = dimension

    @property
    def embedding_dimension(self) -> int:
        return self._dim

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
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError

    async def count_tokens(self, *, text: str, model: str) -> int:
        return len(text.split())

    async def embed_texts(
        self,
        *,
        texts: list[str],
        route_id: str,
        tenant_id: str,
        run_id: str,
        timeout_s: float = 30.0,
    ) -> list[list[float]]:
        return [deterministic_embedding(t, self._dim) for t in texts]


class FakeParser:
    """Parser that emits a single `ParsedPage` per logical "page" extracted from the input bytes.

    Bytes are decoded as UTF-8; lines starting with `# ` become headings, blank lines split
    paragraphs, and `[footnote] ...` becomes a footnote block. Pages are separated by `\\f`.
    """

    def __init__(self, *, name: str = "fake-pdfplumber") -> None:
        self.name = name

    @property
    def supports_typography(self) -> bool:
        return True

    async def parse(self, *, file_bytes: bytes, mime_type: str) -> list[ParsedPage]:
        del mime_type
        text_value = file_bytes.decode("utf-8")
        page_texts = text_value.split("\f") if "\f" in text_value else [text_value]
        pages: list[ParsedPage] = []
        for page_num, page_text in enumerate(page_texts, start=1):
            blocks: list[ParsedBlock] = []
            current: list[str] = []
            for raw_line in page_text.splitlines():
                line = raw_line.strip()
                if not line:
                    if current:
                        blocks.append(
                            ParsedBlock(
                                text="\n".join(current).strip(),
                                block_type="paragraph",
                                font_size=11.0,
                                bold=False,
                                bbox=None,
                                page_num=page_num,
                            )
                        )
                        current = []
                    continue
                if line.startswith("# "):
                    if current:
                        blocks.append(
                            ParsedBlock(
                                text="\n".join(current).strip(),
                                block_type="paragraph",
                                font_size=11.0,
                                bold=False,
                                bbox=None,
                                page_num=page_num,
                            )
                        )
                        current = []
                    blocks.append(
                        ParsedBlock(
                            text=line[2:].strip(),
                            block_type="heading",
                            font_size=18.0,
                            bold=True,
                            bbox=None,
                            page_num=page_num,
                        )
                    )
                elif line.startswith("[footnote]"):
                    if current:
                        blocks.append(
                            ParsedBlock(
                                text="\n".join(current).strip(),
                                block_type="paragraph",
                                font_size=11.0,
                                bold=False,
                                bbox=None,
                                page_num=page_num,
                            )
                        )
                        current = []
                    blocks.append(
                        ParsedBlock(
                            text=line.replace("[footnote]", "").strip() or "fn",
                            block_type="footnote",
                            font_size=9.0,
                            bold=False,
                            bbox=None,
                            page_num=page_num,
                        )
                    )
                else:
                    current.append(line)
            if current:
                blocks.append(
                    ParsedBlock(
                        text="\n".join(current).strip(),
                        block_type="paragraph",
                        font_size=11.0,
                        bold=False,
                        bbox=None,
                        page_num=page_num,
                    )
                )
            pages.append(ParsedPage(page_num=page_num, blocks=blocks))
        return pages


ResponderResult = tuple[dict[str, Any], dict[str, Any]]
Responder = Callable[[str, dict[str, Any]], ResponderResult]


def default_query_analyzer_responder(
    query_text: str, schema: dict[str, Any]
) -> ResponderResult:
    """Conservative ClassifiedQuery + RetrievalPlan response for a generic query.

    Used by tests that don't care about the specific shape, only that the QueryAnalyzer
    produced something schema-valid and that the downstream Retriever runs.
    """
    del schema
    classified = {
        "rawQuery": query_text,
        "answerMode": "consensus",
        "sensitivityPrimary": "normal",
        "riskFlags": [],
        "handling": "answer",
        "preliminaryConfidenceTier": "YELLOW",
        "reframedQuery": None,
        "reframingDisclosureRequired": False,
        "classifierVersion": "fake-stub@1",
    }
    plan = {
        "semanticQuery": query_text,
        "answerMode": "consensus",
        "tenantId": "PLACEHOLDER",  # adapter overrides with Principal.tenant_id
        "filters": {
            "tenantId": "PLACEHOLDER",
            "approved": True,
        },
        "k": 8,
        "boosts": [],
        "retrieval": {"useBM25": False, "useHybrid": False},
    }
    return classified, plan


class FakeStructuredProvider:
    """An `LLMProvider` that returns canned `generate_structured` responses and deterministic
    embeddings.

    Pass a callable `responder` to drive specific scenarios from a unit test; the default
    responder returns a conservative `sensitivityPrimary='normal'` + `handling='answer'`
    response keyed off the user message text.
    """

    name = "fake-structured"

    def __init__(
        self,
        *,
        responder: Responder | None = None,
        dimension: int = 1536,
    ) -> None:
        self._responder = responder or default_query_analyzer_responder
        self._dim = dimension
        self.calls: list[dict[str, Any]] = []

    @property
    def embedding_dimension(self) -> int:
        return self._dim

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
        del max_output_tokens, temperature, timeout_s
        user_text = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        classified, plan = self._responder(user_text, schema)
        data = {"classifiedQuery": classified, "retrievalPlan": plan}
        self.calls.append(
            {
                "messages": messages,
                "route_id": route_id,
                "tenant_id": tenant_id,
                "run_id": run_id,
                "data": data,
            }
        )
        return StructuredResult(
            data=data,
            raw_text="<fake>",
            prompt_tokens=len(user_text.split()),
            completion_tokens=10,
            model_route_id=route_id,
            finish_reason="stop",
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
        raise NotImplementedError

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
        raise NotImplementedError

    async def count_tokens(self, *, text: str, model: str) -> int:
        return len(text.split())

    async def embed_texts(
        self,
        *,
        texts: list[str],
        route_id: str,
        tenant_id: str,
        run_id: str,
        timeout_s: float = 30.0,
    ) -> list[list[float]]:
        return [deterministic_embedding(t, self._dim) for t in texts]


class RefusingStructuredProvider(FakeStructuredProvider):
    """A FakeStructuredProvider that always returns `finish_reason='refusal'`.

    Used to exercise the QueryAnalyzer's deterministic fallback path."""

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
        del messages, schema, tenant_id, run_id, max_output_tokens, temperature, timeout_s
        return StructuredResult(
            data={},
            raw_text="",
            prompt_tokens=0,
            completion_tokens=0,
            model_route_id=route_id,
            finish_reason="refusal",
        )


class ComposerFakeProvider:
    """A FakeStructuredProvider variant whose responder is composer-shaped (`answer` +
    `citedChunkIds`). Use this in T-004 tests to drive A5 deterministically."""

    name = "fake-composer"

    def __init__(
        self,
        *,
        answer: str = "Saint Basil writes that prayer requires patience.",
        cited_chunk_ids: list[str] | None = None,
        finish_reason: str = "stop",
    ) -> None:
        self._answer = answer
        self._cited = cited_chunk_ids or []
        self._finish_reason = finish_reason
        self.calls: list[dict[str, Any]] = []

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
        del schema, max_output_tokens, temperature, timeout_s
        self.calls.append(
            {
                "messages": messages,
                "route_id": route_id,
                "tenant_id": tenant_id,
                "run_id": run_id,
            }
        )
        data = {"answer": self._answer, "citedChunkIds": list(self._cited)}
        return StructuredResult(
            data=data,
            raw_text="<fake>",
            prompt_tokens=10,
            completion_tokens=20,
            model_route_id=route_id,
            finish_reason=self._finish_reason,  # type: ignore[arg-type]
        )

    async def generate_text(self, **kwargs: Any) -> str:
        raise NotImplementedError

    def stream_text(self, **kwargs: Any) -> AsyncIterator[StreamEvent]:
        raise NotImplementedError

    async def count_tokens(self, *, text: str, model: str) -> int:
        return len(text.split())

    async def embed_texts(self, **kwargs: Any) -> list[list[float]]:
        raise NotImplementedError


__all__ = [
    "ComposerFakeProvider",
    "FakeEmbeddingProvider",
    "FakeParser",
    "FakeStructuredProvider",
    "RefusingStructuredProvider",
    "default_query_analyzer_responder",
    "deterministic_embedding",
]
