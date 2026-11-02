"""Pure normalisation helpers for incoming lead data (M2.2).

Every helper either returns a canonical value or raises a subclass of
``NormalisationError``. The exception carries a stable ``code`` so the import
pipeline can store a rejection reason without parsing messages.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import phonenumbers
from email_validator import EmailNotValidError, validate_email
from phonenumbers import NumberParseException, PhoneNumberFormat

DEFAULT_PHONE_REGION = "IN"


class NormalisationError(ValueError):
    """Base class for values that cannot be normalised."""

    code = "invalid_value"


class InvalidEmail(NormalisationError):
    """The email is empty or fails format validation."""

    code = "invalid_email"


class InvalidPhone(NormalisationError):
    """The phone number cannot be parsed or is not a valid number."""

    code = "invalid_phone"


class InvalidName(NormalisationError):
    """The name is empty or longer than the column allows."""

    code = "invalid_name"


class InvalidScore(NormalisationError):
    """The score is not numeric or is outside 0–100."""

    code = "invalid_score"


def normalise_email(value: str) -> str:
    """Trim and lowercase an email address and validate its shape.

    Delivery is not checked: imports must work offline for addresses the mail
    provider has not seen yet. ``EmailStr`` in request schemas uses the same
    library but rejects reserved domains, so this helper is the authority for
    imported data.
    """
    candidate = value.strip()
    if not candidate:
        raise InvalidEmail("Email is required")

    try:
        validated = validate_email(candidate, check_deliverability=False)
    except EmailNotValidError as exc:
        raise InvalidEmail("Invalid email address") from exc

    return validated.normalized.lower()


def normalise_phone(value: str, *, default_region: str = DEFAULT_PHONE_REGION) -> str:
    """Parse a phone number and return it in E.164 form.

    Numbers without a country code are interpreted in ``default_region`` (India
    by default). Parsed numbers must pass the library's validity check, so
    obviously fake numbers are rejected rather than stored as ``+91...``.
    """
    candidate = value.strip()
    if not candidate:
        raise InvalidPhone("Phone number is required")

    try:
        parsed = phonenumbers.parse(candidate, default_region)
    except NumberParseException as exc:
        raise InvalidPhone("Invalid phone number") from exc

    if not phonenumbers.is_valid_number(parsed):
        raise InvalidPhone("Invalid phone number")

    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)


def normalise_name(value: str) -> str:
    """Trim, collapse internal whitespace, and preserve the original case."""
    collapsed = " ".join(value.split())
    if not collapsed:
        raise InvalidName("Name is required")
    if len(collapsed) > 200:
        raise InvalidName("Name is longer than 200 characters")
    return collapsed


def normalise_score(value: str | int | float) -> float:
    """Return a score between 0 and 100, accepting an optional trailing ``%``.

    Booleans are rejected even though Python treats them as integers, and
    non-finite values (``nan``/``inf``) are not scores.
    """
    if isinstance(value, bool):
        raise InvalidScore("Score must be a number")

    if isinstance(value, str):
        text = value.strip()
        if text.endswith("%"):
            text = text[:-1].strip()
        if not text or "%" in text:
            raise InvalidScore("Score must be a number")
    elif isinstance(value, int | float):
        text = str(value)
    else:
        raise InvalidScore("Score must be a number")

    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise InvalidScore("Score must be a number") from exc

    if not number.is_finite() or not Decimal(0) <= number <= Decimal(100):
        raise InvalidScore("Score must be between 0 and 100")

    return float(number)
