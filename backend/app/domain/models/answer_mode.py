"""AnswerMode enum — the canonical answer-mode taxonomy.

Mirrored byte-for-byte by ``docs/schemas/answer-mode.schema.json`` and the inline
``AnswerMode`` in ``docs/api/openapi.yaml``; parity is enforced in CI by
``scripts/verify_openapi_enums.py``.
"""

from __future__ import annotations

from typing import Literal

AnswerMode = Literal[
    "consensus",
    "institutional_policy",
    "scholarly_dispute",
    "pastoral_guidance",
    "insufficient",
]
