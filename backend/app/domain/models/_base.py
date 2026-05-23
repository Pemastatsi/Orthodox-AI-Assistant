"""Shared base model.

Per code-gen-guide §8.1: Python attrs are snake_case, JSON aliases are camelCase."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class WireModel(BaseModel):
    """Base for every domain model that serializes to/from JSON wire payloads."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=False,
        str_strip_whitespace=False,
    )
