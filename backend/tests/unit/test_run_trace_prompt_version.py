"""GS-3: RunTrace stages record the prompt version/id of model-backed stages.

The other half of T-008 (the schema documents `stages[].details.promptVersion`/`promptId`;
this asserts the query path actually populates them for the A1/A2 and A5 stages).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.v1.query import _stage_a1a2, _stage_a5
from app.core.config import get_settings

NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def test_a1a2_stage_records_prompt_version() -> None:
    settings = get_settings()
    stage = _stage_a1a2(NOW, settings, outcome="ok")
    assert stage.details["promptVersion"] == settings.active_prompt_version_a1a2
    assert stage.details["promptId"] == "a1_classifier/en"
    assert stage.model_route_id == settings.active_model_route_a1a2


def test_a5_stage_records_prompt_version() -> None:
    settings = get_settings()
    stage = _stage_a5(NOW, settings, outcome="ok")
    assert stage.details["promptVersion"] == settings.active_prompt_version_a5
    assert stage.details["promptId"] == "a5_composer/en"
    assert stage.model_route_id == settings.active_model_route_a5
