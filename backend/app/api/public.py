"""Unauthenticated public endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, SettingsDep
from app.core.normalisation import (
    NormalisationError,
    normalise_email,
    normalise_name,
    normalise_phone,
)
from app.integrations.captcha.base import CaptchaVerifier
from app.integrations.captcha.factory import build_captcha_verifier
from app.repositories import catalogues as catalogues_repo
from app.schemas.public import PublicEnquiryRead, PublicEnquiryRequest
from app.services import enquiries as enquiries_service
from app.services import leads as leads_service

router = APIRouter(prefix="/api/public", tags=["public"])


def get_redis(request: Request) -> Redis:
    """Return the application's shared Redis client."""
    client: Redis = request.app.state.redis_client
    return client


def get_captcha_verifier(settings: SettingsDep) -> CaptchaVerifier:
    """Build the configured CAPTCHA verifier for this request."""
    return build_captcha_verifier(settings)


RedisDep = Annotated[Redis, Depends(get_redis)]
CaptchaDep = Annotated[CaptchaVerifier, Depends(get_captcha_verifier)]


@router.post(
    "/enquiries",
    response_model=PublicEnquiryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_enquiry(
    payload: PublicEnquiryRequest,
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    redis: RedisDep,
    verifier: CaptchaDep,
) -> PublicEnquiryRead:
    """Receive a public enquiry, dedupe it, and store consent choices."""
    try:
        first_name = normalise_name(payload.first_name)
        last_name = normalise_name(payload.last_name) if payload.last_name.strip() else ""
        email = normalise_email(payload.email) if payload.email else None
        phone = normalise_phone(payload.phone) if payload.phone else None
    except NormalisationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.code,
        ) from exc

    if email is None and phone is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="contact_required",
        )

    programme_id = await _resolve_programme(session, payload)
    campus_id = await _resolve_campus(session, payload)
    remote_ip = request.client.host if request.client is not None else None

    try:
        result = await enquiries_service.submit_enquiry(
            session,
            settings,
            redis,
            verifier,
            remote_ip=remote_ip,
            captcha_token=payload.captcha_token,
            enquiry=enquiries_service.EnquiryInput(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                programme_id=programme_id,
                campus_id=campus_id,
                admission_cycle=payload.admission_cycle or _default_cycle(),
                consent_promotional=payload.consent_promotional,
                consent_transactional=payload.consent_transactional,
            ),
        )
    except enquiries_service.RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limited",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except enquiries_service.RateLimiterUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="rate_limiter_unavailable",
        ) from exc
    except enquiries_service.CaptchaFailed as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="captcha_failed",
        ) from exc
    except leads_service.ConflictingContacts as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "conflicting_contact",
                "student_id": str(exc.student_id),
                "conflicting_student_id": str(exc.conflicting_student_id),
            },
        ) from exc
    except leads_service.ContactAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="contact_already_exists",
        ) from exc

    return PublicEnquiryRead(
        id=result.lead.id,
        lead_id=result.lead.id,
        student_id=result.student.id,
        duplicate_detected=result.duplicate_detected,
    )


async def _resolve_programme(
    session: AsyncSession,
    payload: PublicEnquiryRequest,
) -> uuid.UUID | None:
    if payload.programme_id is not None:
        if await catalogues_repo.get_programme_by_id(session, payload.programme_id) is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="programme_not_found",
            )
        return payload.programme_id
    if payload.programme:
        programme = await catalogues_repo.get_programme(session, payload.programme)
        if programme is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="programme_not_found",
            )
        return programme.id
    return None


async def _resolve_campus(
    session: AsyncSession,
    payload: PublicEnquiryRequest,
) -> uuid.UUID | None:
    if payload.campus_id is not None:
        if await catalogues_repo.get_campus_by_id(session, payload.campus_id) is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="campus_not_found",
            )
        return payload.campus_id
    if payload.campus:
        campus = await catalogues_repo.get_campus(session, payload.campus)
        if campus is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="campus_not_found",
            )
        return campus.id
    return None


def _default_cycle() -> str:
    return f"{datetime.now(UTC).year}-fall"
