"""A1 + A2 combined classifier prompt.

The prompt text is loaded from the `/prompts` registry
(`prompts/a1_classifier/en/<version>.j2`), selected by `Settings.active_prompt_version_a1a2`.
When the prompt or its JSON schema changes, add a new version file and re-certify the route
per `docs/contracts/code-gen-guide.md` §Prompt versioning and `/prompts/README.md`.

The actual JSON Schema sent to the provider is derived from the Pydantic models
(`ClassifiedQuery` + `RetrievalPlan`) at call time so the schema and the deserialized data
cannot drift.
"""

from __future__ import annotations

from app.adapters.providers.base import ChatMessage
from app.core.config import get_settings
from app.domain.services.prompt_loader import load_prompt
from app.domain.services.safety_config import SafetyMatch

_STAGE, _LANGUAGE = "a1_classifier", "en"
# A1/A2 system prompt — canonical text lives in the /prompts registry (GS-3), not inline;
# selected by Settings.active_prompt_version_a1a2. See /prompts/README.md.
_PROMPT_VERSION = get_settings().active_prompt_version_a1a2
_SYSTEM_PROMPT = load_prompt(_STAGE, _LANGUAGE, _PROMPT_VERSION.split("@", 1)[-1])


def build_messages(
    *,
    query_text: str,
    soft_trigger: SafetyMatch | None,
) -> list[ChatMessage]:
    """Build the (system, user) message pair for the A1/A2 structured call.

    If a soft-trigger keyword rule fired, surface it to the LLM as a *candidate* — the LLM
    confirms or downgrades. Hard triggers never reach this prompt; they short-circuit
    upstream in the QueryAnalyzer."""
    candidate_note = ""
    if soft_trigger is not None:
        candidate_note = (
            f"\n\nKeyword pre-screen flagged this query as a candidate match for "
            f"sensitivity={soft_trigger.sensitivity!r} (rule_id={soft_trigger.rule_id!r}). "
            f"Confirm or downgrade based on the actual phrasing."
        )

    return [
        ChatMessage(role="system", content=_SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=f"User query:\n{query_text}{candidate_note}",
        ),
    ]


__all__ = ["build_messages"]
