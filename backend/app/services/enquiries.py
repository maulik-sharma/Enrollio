"""Public web enquiry creation, CAPTCHA checks, and IP rate limiting."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import cast

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.domain import ConsentCategory, ConsentChannel
from app.integrations.captcha.base import CaptchaVerifier
from app.repositories import catalogues as catalogues_repo
from app.services import consent as consent_service
from app.services import leads as leads_service

WEBSITE_SOURCE_NAME = "Website"
CONSENT_SOURCE = "web_form"
CONSENT_METHOD = "web_form"
ENQUIRY_RATE_KEY_PREFIX = "enrollio:enquiry-rate"

_RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
if ttl < 0 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
  ttl = tonumber(ARGV[1])
end
return {current, ttl}
"""


class RateLimitExceeded(Exception):
    """The client IP has used its enquiry allowance for this window."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("Enquiry rate limit exceeded")


class RateLimiterUnavailable(Exception):
    """Redis could not answer, so the public endpoint fails closed."""


class CaptchaFailed(Exception):
    """The supplied CAPTCHA token was missing or invalid."""


@dataclass(frozen=True)
class EnquiryInput:
    """Normalised values from the public form."""

    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    programme_id: uuid.UUID | None
    campus_id: uuid.UUID | None
    admission_cycle: str
    consent_promotional: bool = False
    consent_transactional: bool = False


async def submit_enquiry(
    session: AsyncSession,
    settings: Settings,
    redis: Redis,
    verifier: CaptchaVerifier,
    *,
    remote_ip: str | None,
    captcha_token: str,
    enquiry: EnquiryInput,
) -> leads_service.LeadCreation:
    """Rate-limit, verify CAPTCHA, create the lead, and store consent."""
    await enforce_rate_limit(
        redis,
        remote_ip=remote_ip,
        limit=settings.ENQUIRY_RATE_LIMIT_PER_HOUR,
        window_seconds=settings.ENQUIRY_RATE_LIMIT_WINDOW_SECONDS,
    )
    if not await verifier.verify(captcha_token, remote_ip=remote_ip):
        raise CaptchaFailed

    source = await catalogues_repo.get_or_create_source(session, WEBSITE_SOURCE_NAME)
    result = await leads_service.create_or_get_lead(
        session,
        first_name=enquiry.first_name,
        last_name=enquiry.last_name,
        email=enquiry.email,
        phone=enquiry.phone,
        programme_id=enquiry.programme_id,
        campus_id=enquiry.campus_id,
        source_id=source.id,
        admission_cycle=enquiry.admission_cycle,
    )

    channels: list[ConsentChannel] = []
    if enquiry.email:
        channels.append(ConsentChannel.EMAIL)
    if enquiry.phone:
        channels.append(ConsentChannel.WHATSAPP)

    for channel in channels:
        if enquiry.consent_promotional:
            await consent_service.record_consent(
                session,
                settings,
                student_id=result.student.id,
                channel=channel,
                category=ConsentCategory.PROMOTIONAL,
                source=CONSENT_SOURCE,
                method=CONSENT_METHOD,
                commit=False,
            )
        if enquiry.consent_transactional:
            await consent_service.record_consent(
                session,
                settings,
                student_id=result.student.id,
                channel=channel,
                category=ConsentCategory.TRANSACTIONAL,
                source=CONSENT_SOURCE,
                method=CONSENT_METHOD,
                commit=False,
            )

    await session.commit()
    await session.refresh(result.lead)
    return result


async def enforce_rate_limit(
    redis: Redis,
    *,
    remote_ip: str | None,
    limit: int,
    window_seconds: int,
) -> None:
    """Increment the fixed-window counter and raise when over ``limit``."""
    if limit <= 0:
        return
    key = f"{ENQUIRY_RATE_KEY_PREFIX}:{remote_ip or 'unknown'}"
    try:
        raw = await cast(
            Awaitable[object],
            redis.eval(_RATE_LIMIT_SCRIPT, 1, key, str(window_seconds)),
        )
        count, ttl = cast(list[int], raw)
    except Exception as exc:
        raise RateLimiterUnavailable from exc

    if count > limit:
        raise RateLimitExceeded(retry_after=max(int(ttl), 1))
