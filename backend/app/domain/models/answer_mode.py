"""AnswerMode enum — `docs/schemas/answer-mode.schema.json`."""

from __future__ import annotations

from typing import Literal

AnswerMode = Literal[
    "consensus",
    "institutional_policy",
    "scholarly_dispute",
    "pastoral_guidance",
    "insufficient",
]
