"""Unit tests for the PII masking utilities."""

from __future__ import annotations

import pytest

from app.core.masking import mask_email, mask_extra_fields, mask_phone, mask_sensitive, mask_text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("rahul.sharma@gmail.com", "r***@gmail.com"),
        ("a@b.co", "a***@b.co"),
        ("first.last+tag@sub.domain.org", "f***@sub.domain.org"),
        ("not-an-email", "***"),
        ("", "***"),
    ],
)
def test_mask_email(raw: str, expected: str) -> None:
    assert mask_email(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+919876543210", "98XXXX3210"),
        ("9876543210", "98XXXX3210"),
        ("09876543210", "98XXXX3210"),
        ("+91 98765 43210", "98XXXX3210"),
        ("+1 (415) 555-2671", "41XXXX2671"),
        ("12345", "12X45"),
        ("12", "XX"),
        ("", ""),
    ],
)
def test_mask_phone(raw: str, expected: str) -> None:
    assert mask_phone(raw) == expected


def test_mask_text_masks_emails_and_phones_inside_free_text() -> None:
    raw = "Reach rahul.sharma@gmail.com or +91 98765 43210 before Friday."

    assert mask_text(raw) == "Reach r***@gmail.com or 98XXXX3210 before Friday."


def test_mask_text_leaves_dates_and_short_numbers_alone() -> None:
    raw = "Session on 2026-11-01 for order 12345."

    assert mask_text(raw) == raw


def test_mask_sensitive_redacts_content() -> None:
    assert mask_sensitive("Rahul is interested in CSE") == "[REDACTED]"
    assert mask_sensitive("") == ""


def test_mask_extra_fields_redacts_sensitive_keys_and_masks_strings() -> None:
    masked = mask_extra_fields(
        {
            "notes": "call me on 9876543210",
            "email": "rahul.sharma@gmail.com",
            "attempt": 3,
            "empty_notes": "",
        }
    )

    assert masked == {
        "notes": "[REDACTED]",
        "email": "r***@gmail.com",
        "attempt": 3,
        "empty_notes": "",
    }
