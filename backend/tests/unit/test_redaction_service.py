"""redact_query_text + should_capture_raw_sensitive."""

from __future__ import annotations

import pytest
from app.domain.models.classified_query import ClassifiedQuery
from app.domain.services.redaction_service import (
    redact_query_text,
    should_capture_raw_sensitive,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("contact me at alice@example.com please", "contact me at [email] please"),
        ("call +1 (415) 555-9876 tonight", "call [phone] tonight"),
        ("the card is 4242424242424242", "the card is [number]"),
        ("born in 1987 to a faithful family", "born in [number] to a faithful family"),
        # No PII → unchanged.
        ("what do the fathers teach about prayer?", "what do the fathers teach about prayer?"),
        # Multiple types in one string.
        (
            "email alice@x.com, phone +1 415 555 0000, ssn 123456789",
            "email [email], phone [phone], ssn [number]",
        ),
    ],
)
def test_redact_query_text(raw: str, expected: str) -> None:
    assert redact_query_text(raw) == expected


def test_redact_query_text_preserves_greek_diacritics() -> None:
    raw = "τί διδάσκουν οἱ πατέρες περὶ προσευχῆς;"
    assert redact_query_text(raw) == raw


def _classified(
    *,
    sensitivity: str = "normal",
    handling: str = "answer",
    risk_flags: list[str] | None = None,
) -> ClassifiedQuery:
    return ClassifiedQuery(
        raw_query="q",
        answer_mode="consensus",
        sensitivity_primary=sensitivity,  # type: ignore[arg-type]
        risk_flags=risk_flags or [],  # type: ignore[arg-type]
        handling=handling,  # type: ignore[arg-type]
        preliminary_confidence_tier="GREEN",
    )


def test_should_capture_raw_sensitive_skips_normal_path() -> None:
    assert should_capture_raw_sensitive(_classified()) is False


@pytest.mark.parametrize(
    "sensitivity",
    ["pastoral_advice", "political", "medical", "comparative_religion", "canonical_dispute"],
)
def test_should_capture_raw_sensitive_triggers_on_non_normal_sensitivity(
    sensitivity: str,
) -> None:
    assert should_capture_raw_sensitive(_classified(sensitivity=sensitivity)) is True


def test_should_capture_raw_sensitive_triggers_on_risk_flag() -> None:
    assert (
        should_capture_raw_sensitive(_classified(risk_flags=["self_harm"])) is True
    )


def test_should_capture_raw_sensitive_triggers_on_hard_safety() -> None:
    assert (
        should_capture_raw_sensitive(_classified(handling="block_with_redirect")) is True
    )
