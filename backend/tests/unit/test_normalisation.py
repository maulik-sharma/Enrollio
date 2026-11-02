"""Normalisation utilities: at least 20 cases per helper (M2.2)."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.normalisation import (
    InvalidEmail,
    InvalidName,
    InvalidPhone,
    InvalidScore,
    normalise_email,
    normalise_name,
    normalise_phone,
    normalise_score,
)

EMAIL_VALID: list[tuple[str, str]] = [
    ("Rahul.Sharma@Gmail.com", "rahul.sharma@gmail.com"),
    (" rahul.sharma@gmail.com ", "rahul.sharma@gmail.com"),
    ("ASHA@ENROLLIO.DEV", "asha@enrollio.dev"),
    ("first.last+tag@example.com", "first.last+tag@example.com"),
    ("user_name@sub.domain.co.in", "user_name@sub.domain.co.in"),
    ("  User@Example.COM", "user@example.com"),
    ("a@b.co", "a@b.co"),
    ("x.y@z.io", "x.y@z.io"),
    ("NAME@EXAMPLE.ORG", "name@example.org"),
    ("test123@example.net", "test123@example.net"),
    ("hello+world@example.com", "hello+world@example.com"),
    ("\tTabbed@Example.com\n", "tabbed@example.com"),
]

EMAIL_INVALID: list[str] = [
    "",
    "   ",
    "not-an-email",
    "@example.com",
    "user@",
    "user@@example.com",
    "user example@example.com",
    "user@example",
    "user@.com",
    "user@example..com",
    "user@-example.com",
    ".user@example.com",
    "user.@example.com",
    "user@example.com.",
    "a" * 300 + "@example.com",
]


@pytest.mark.parametrize(("raw", "expected"), EMAIL_VALID)
def test_normalise_email_valid(raw: str, expected: str) -> None:
    assert normalise_email(raw) == expected


@pytest.mark.parametrize("raw", EMAIL_INVALID)
def test_normalise_email_invalid(raw: str) -> None:
    with pytest.raises(InvalidEmail) as exc_info:
        normalise_email(raw)

    assert exc_info.value.code == "invalid_email"


PHONE_VALID: list[tuple[str, str]] = [
    ("9876543210", "+919876543210"),
    ("+91 98765 43210", "+919876543210"),
    ("09876543210", "+919876543210"),
    ("0091 98765 43210", "+919876543210"),
    ("98765-43210", "+919876543210"),
    (" 9876543210 ", "+919876543210"),
    ("+919876543210", "+919876543210"),
    ("(+91) 98765 43210", "+919876543210"),
    ("91 98765 43210", "+919876543210"),
    ("+1 415 555 2671", "+14155552671"),
    ("9123456789", "+919123456789"),
]

PHONE_INVALID: list[str] = [
    "",
    "   ",
    "abc",
    "12345",
    "0000000000",
    "+91 00000 00000",
    "987654321",
    "98765432100",
    "+999 1234567",
    "98765 4321O",
    "not a phone",
    "+++",
]


@pytest.mark.parametrize(("raw", "expected"), PHONE_VALID)
def test_normalise_phone_valid(raw: str, expected: str) -> None:
    assert normalise_phone(raw) == expected


@pytest.mark.parametrize("raw", PHONE_INVALID)
def test_normalise_phone_invalid(raw: str) -> None:
    with pytest.raises(InvalidPhone) as exc_info:
        normalise_phone(raw)

    assert exc_info.value.code == "invalid_phone"


def test_normalise_phone_uses_the_requested_default_region() -> None:
    assert normalise_phone("415 555 2671", default_region="US") == "+14155552671"


NAME_VALID: list[tuple[str, str]] = [
    ("Asha Rao", "Asha Rao"),
    ("  Asha   Rao  ", "Asha Rao"),
    ("Asha\tRao\nKulkarni", "Asha Rao Kulkarni"),
    ("A", "A"),
    ("Élodie D'Souza", "Élodie D'Souza"),
    ("Dr. Asha R. Rao", "Dr. Asha R. Rao"),
    ("Asha  -  Rao", "Asha - Rao"),
    ("  leading", "leading"),
    ("trailing  ", "trailing"),
    ("A" * 200, "A" * 200),
    ("Asha\u00a0Rao", "Asha Rao"),
    ("Asha\u2003Rao", "Asha Rao"),
    ("Rao, Asha", "Rao, Asha"),
    ("Asha\r\nRao", "Asha Rao"),
]

NAME_INVALID: list[str] = [
    "",
    "   ",
    "\t\n",
    "\u00a0\u2003",
    "A" * 201,
    "A" * 150 + " " + "B" * 60,
    " " + "A" * 201,
]


@pytest.mark.parametrize(("raw", "expected"), NAME_VALID)
def test_normalise_name_valid(raw: str, expected: str) -> None:
    assert normalise_name(raw) == expected


@pytest.mark.parametrize("raw", NAME_INVALID)
def test_normalise_name_invalid(raw: str) -> None:
    with pytest.raises(InvalidName) as exc_info:
        normalise_name(raw)

    assert exc_info.value.code == "invalid_name"


SCORE_VALID: list[tuple[str | int | float, float]] = [
    ("85%", 85.0),
    (" 85 % ", 85.0),
    ("0", 0.0),
    ("100", 100.0),
    (85, 85.0),
    (85.5, 85.5),
    ("0%", 0.0),
    ("100%", 100.0),
    ("5e1", 50.0),
    ("85.5%", 85.5),
    (0, 0.0),
    (100.0, 100.0),
    (" 42 ", 42.0),
]

SCORE_INVALID: list[Any] = [
    "abc",
    "",
    "   ",
    "85%%",
    "-1",
    "-0.1",
    "100.1",
    "101%",
    "1,000",
    "1e3",
    float("nan"),
    float("inf"),
    float("-inf"),
    True,
    False,
    None,
    object(),
]


@pytest.mark.parametrize(("raw", "expected"), SCORE_VALID)
def test_normalise_score_valid(raw: str | int | float, expected: float) -> None:
    assert normalise_score(raw) == expected


@pytest.mark.parametrize("raw", SCORE_INVALID)
def test_normalise_score_invalid(raw: Any) -> None:
    with pytest.raises(InvalidScore) as exc_info:
        normalise_score(raw)

    assert exc_info.value.code == "invalid_score"
