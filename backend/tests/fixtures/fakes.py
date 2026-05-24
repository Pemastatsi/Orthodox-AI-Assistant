"""Deterministic fakes for the ingestion pipeline.

`FakeEmbeddingProvider` lets the worker run without OpenAI API keys; `FakeParser` lets the
pipeline run without real PDF bytes (the underlying chunking + embedding + upsert path is what
the F-23 round-trip is exercising, not pdfplumber).
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
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


__all__ = ["FakeEmbeddingProvider", "FakeParser", "deterministic_embedding"]
