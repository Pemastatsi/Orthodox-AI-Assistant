"""A1 + A2 combined classifier prompt.

Versioned via `Settings.active_prompt_version_a1a2`. When the prompt or its JSON schema
changes, bump the version and re-certify the route per `docs/contracts/code-gen-guide.md`
§Prompt versioning.

The actual JSON Schema sent to the provider is derived from the Pydantic models
(`ClassifiedQuery` + `RetrievalPlan`) at call time so the schema and the deserialized data
cannot drift.
"""

from __future__ import annotations

from app.adapters.providers.base import ChatMessage
from app.domain.services.safety_config import SafetyMatch

_SYSTEM_PROMPT = """\
You are the Orthodox AI Assistant's query analyzer. For every user query you return a JSON
object with exactly two keys: `classifiedQuery` and `retrievalPlan`. You do not answer the
question. You do not invent citations. You do not rewrite the user's intent beyond a
transparent safety reframing when the question seeks personal advice on a sensitive topic.

## ClassifiedQuery rules

- `rawQuery` MUST equal the user's input verbatim.
- `answerMode` is one of: consensus, institutional_policy, scholarly_dispute,
  pastoral_guidance, insufficient.
- `sensitivityPrimary` is one of: normal, pastoral_advice, political, medical,
  comparative_religion, canonical_dispute, other_sensitive.
- `riskFlags` is a possibly-empty subset of: self_harm, medical_emergency,
  canonical_dispute_active, minor_protection.
- `handling` is one of: answer, answer_with_disclaimer, reframe_to_teaching,
  block_with_redirect, insufficient_evidence.
- `preliminaryConfidenceTier` ∈ {GREEN, YELLOW, RED} reflects only your pre-retrieval
  read of whether the corpus is likely to support an answer; the authoritative tier is
  computed after retrieval.
- `reframedQuery` is null unless you are reframing an advice-seeking question into a
  teaching question (e.g. "Should I divorce?" → "What does the Church teach about
  marriage?"). When you reframe, set `reframingDisclosureRequired` to true.

## RetrievalPlan rules

- `semanticQuery` MUST equal `reframedQuery` if you reframed; otherwise it MUST equal
  `rawQuery`. NEVER paraphrase or expand beyond a transparent safety reframing.
- `tenantId` and `filters.tenantId` are placeholders; the server overwrites them with the
  caller's tenant. Emit any non-empty string; it will be replaced.
- `filters.approved` is always true.
- `k` is an integer between 1 and 20; 8 is the safe default.
- `retrieval.useBM25` and `retrieval.useHybrid` default to false. Only set them to true
  when the query carries highly lexical content (specific Father names, canon numbers,
  Greek terms) that benefits from sparse retrieval.
- `retrieval.reranker.enabled` is always false in Phase 1.
"""


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
