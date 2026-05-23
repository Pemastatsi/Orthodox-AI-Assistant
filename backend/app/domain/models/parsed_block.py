"""ParsedBlock model — `docs/schemas/parsed-block.schema.json`."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.domain.models._base import WireModel

BlockType = Literal["heading", "paragraph", "footnote", "caption", "other"]


class ParsedBlock(WireModel):
    text: str = Field(min_length=1)
    block_type: BlockType
    bold: bool
    page_num: int = Field(ge=1)
    font_size: float | None = Field(default=None, gt=0)
    bbox: tuple[float, float, float, float] | None = None
