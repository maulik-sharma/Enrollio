"""PII masking utilities.

The formats are part of the logging contract:

* ``rahul.sharma@gmail.com`` -> ``r***@gmail.com``
* ``+91 98765 43210`` -> ``98XXXX3210``
* fields marked sensitive -> ``[REDACTED]``
"""

from __future__ import annotations

import re

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Candidate runs of digits/separators. A run is only treated as a phone number
# when it contains at least 10 digits, so dates such as 2026-11-01 are kept.
PHONE_CANDIDATE_PATTERN = re.compile(r"\+?\d[\d\s().-]{7,}\d")
DIGITS_PATTERN = re.compile(r"\D")

SENSITIVE_FIELDS = frozenset(
    {
        "body",
        "content",
        "content_html",
        "content_text",
        "free_text",
        "notes",
        "recording",
        "recording_url",
        "sensitive",
        "transcript",
    }
)

REDACTED = "[REDACTED]"


def mask_email(value: str) -> str:
    """Keep the first character of the local part and the full domain."""
    local, separator, domain = value.partition("@")
    if not separator or not local or not domain or "." not in domain:
        return "***"
    return f"{local[0]}***@{domain}"


def mask_phone(value: str) -> str:
    """Mask all but the leading two and trailing four digits."""
    digits = DIGITS_PATTERN.sub("", value)
    # Drop the country code so Indian numbers always mask as 98XXXX3210.
    if len(digits) > 10:
        digits = digits[-10:]
    length = len(digits)
    if length == 0:
        return ""
    if length <= 4:
        return "X" * length
    if length <= 6:
        return f"{digits[:2]}{'X' * (length - 4)}{digits[-2:]}"
    return f"{digits[:2]}{'X' * (length - 6)}{digits[-4:]}"


def mask_text(value: str) -> str:
    """Mask every email address and phone number inside free text."""

    def _replace_phone(match: re.Match[str]) -> str:
        candidate = match.group(0)
        if len(DIGITS_PATTERN.sub("", candidate)) < 10:
            return candidate
        return mask_phone(candidate)

    without_emails = EMAIL_PATTERN.sub(lambda match: mask_email(match.group(0)), value)
    return PHONE_CANDIDATE_PATTERN.sub(_replace_phone, without_emails)


def mask_sensitive(value: str) -> str:
    """Replace a field explicitly marked sensitive."""
    return REDACTED if value else ""


def mask_extra_fields(fields: dict[str, object]) -> dict[str, object]:
    """Mask string values of extra log fields, redacting sensitive keys."""
    masked: dict[str, object] = {}
    for key, value in fields.items():
        if key in SENSITIVE_FIELDS:
            masked[key] = REDACTED if value else value
        elif isinstance(value, str):
            masked[key] = mask_text(value)
        else:
            masked[key] = value
    return masked
