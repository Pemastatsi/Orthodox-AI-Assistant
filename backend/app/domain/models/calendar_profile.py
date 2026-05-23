"""CalendarProfile model — `docs/schemas/calendar-profile.schema.json`."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.domain.models._base import WireModel


class CalendarProfile(WireModel):
    version: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}\.[0-9]+$")
    fixed_feast_calendar: Literal["julian", "revised_julian", "gregorian"]
    paschalion: Literal["julian", "gregorian"]
    display_label: str | None = None
    notes: str | None = None
