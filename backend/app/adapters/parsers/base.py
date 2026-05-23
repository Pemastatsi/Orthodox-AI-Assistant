"""Parser Protocol per docs/contracts/parser-interface.md (ADR-0008).

T-001 ships the Protocol and dataclasses. Concrete PdfplumberParser and TesseractParser bodies
land in T-002. VisionParser is a Phase 2 stub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class ParsedBlock:
    text: str
    block_type: Literal["heading", "paragraph", "footnote", "caption", "other"]
    font_size: float | None
    bold: bool
    bbox: tuple[float, float, float, float] | None
    page_num: int


@dataclass(frozen=True)
class ParsedPage:
    page_num: int
    blocks: list[ParsedBlock]


@runtime_checkable
class Parser(Protocol):
    """Stateless PDF/text parser. Implementations live in `adapters/parsers/`."""

    name: str

    async def parse(
        self,
        *,
        file_bytes: bytes,
        mime_type: str,
    ) -> list[ParsedPage]: ...

    @property
    def supports_typography(self) -> bool: ...
