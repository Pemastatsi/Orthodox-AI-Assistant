"""Query-text redaction for `flagged_queries.query_text_redacted` writes.

ADR-0005 §7: "Sensitive logs store `query_text_redacted` by default." The redacted text is
what reviewers see in the admin UI. Raw plaintext lives only in `raw_sensitive_logs` under
envelope encryption (see `encryption_service.py`), and only for sensitivity-flagged rows.

This module owns two concerns:

1. `redact_query_text(q)` — value-level PII stripping (emails, phone-shape, digit runs of
   length >= 4). Conservative on purpose: better to over-mask than leak in a reviewer UI.
2. `should_capture_raw_sensitive(classified)` — decision whether to also persist an
   encrypted raw row. True when the A1 classifier flagged the query as non-normal
   sensitivity or attached any risk flag (`self_harm`, `medical_emergency`, etc.). Hard-
   safety paths always capture.
"""

from __future__ import annotations

import re

from app.domain.models.classified_query import ClassifiedQuery

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Phone shape: at least one explicit separator (space/dash/dot/paren/+) AND 7+ total digits.
# Pure digit runs fall through to _DIGIT_RUN_RE so credit cards and SSNs become [number].
_PHONE_RE = re.compile(
    r"(?=(?:[\s\-.()+]*\d){7,})\+?\d[\d\s\-.()+]*[\s\-.()][\d\s\-.()+]*\d"
)
_DIGIT_RUN_RE = re.compile(r"\d{4,}")


def redact_query_text(q: str) -> str:
    """Strip emails, phone-shape numbers, and any standalone digit run of length >= 4.

    Order matters: emails first (their `.` and digits would otherwise match the later
    rules), then phones (broader than digit runs), then leftover digit runs.
    """
    out = _EMAIL_RE.sub("[email]", q)
    out = _PHONE_RE.sub("[phone]", out)
    return _DIGIT_RUN_RE.sub("[number]", out)


def should_capture_raw_sensitive(classified: ClassifiedQuery) -> bool:
    """True when the raw query text warrants encrypted storage in `raw_sensitive_logs`.

    Triggers per ADR-0005 §"Sensitive logs": any non-normal A1 sensitivity classification,
    any risk flag, or a hard-safety handling decision.
    """
    if classified.sensitivity_primary != "normal":
        return True
    if classified.risk_flags:
        return True
    return classified.handling == "block_with_redirect"


__all__ = ["redact_query_text", "should_capture_raw_sensitive"]
