"""Public web enquiry request and response schemas."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class PublicEnquiryRequest(BaseModel):
    """Fields a public enquiry form may submit.

    The alias choices accept the common camelCase and shortened names used by
    frontend forms while the canonical wire format stays snake_case.
    """

    model_config = ConfigDict(populate_by_name=True)

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    email: str | None = None
    phone: str | None = None
    programme_id: uuid.UUID | None = None
    programme: str | None = Field(default=None, max_length=200)
    campus_id: uuid.UUID | None = None
    campus: str | None = Field(default=None, max_length=200)
    admission_cycle: str | None = Field(default=None, max_length=32)
    message: str | None = Field(default=None, max_length=2000)
    consent_promotional: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "consent_promotional",
            "promotional_consent",
            "marketing_consent",
            "marketing_opt_in",
            "consent",
        ),
    )
    consent_transactional: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "consent_transactional",
            "transactional_consent",
        ),
    )
    captcha_token: str = Field(
        default="",
        max_length=4096,
        validation_alias=AliasChoices("captcha_token", "captchaToken", "captcha"),
    )


class PublicEnquiryRead(BaseModel):
    """Minimal acknowledgement; never echoes student PII."""

    id: uuid.UUID
    lead_id: uuid.UUID
    student_id: uuid.UUID
    duplicate_detected: bool
    status: Literal["received"] = "received"
