"""M2.8 public web enquiry endpoint: smoke, consent, CAPTCHA, and rate limit."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.domain import ConsentCategory, ConsentChannel
from app.models.consent_record import ConsentRecord
from app.models.lead import Lead
from app.models.lead_source import LeadSource
from app.models.student import Student
from app.services.enquiries import ENQUIRY_RATE_KEY_PREFIX
from tests.conftest import requires_postgres, requires_redis

pytestmark = [requires_postgres, requires_redis]

PASSWORD = "demo-password-123"
MANAGER = "manager@enrollio.dev"


async def _token(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
async def clear_enquiry_rate_limits(
    app: FastAPI,
    app_client: AsyncClient,
) -> AsyncIterator[None]:
    """Keep fixed-window counters out of the way between test runs."""
    del app_client
    await _clear_rate_limits(app)
    yield
    await _clear_rate_limits(app)


async def _clear_rate_limits(app: FastAPI) -> None:
    client = cast(Redis, app.state.redis_client)
    keys = [key async for key in client.scan_iter(match=f"{ENQUIRY_RATE_KEY_PREFIX}:*")]
    if keys:
        await client.delete(*keys)


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "first_name": "Web",
        "last_name": "Enquiry",
        "email": f"web.enquiry.{uuid.uuid4().hex[:8]}@example.com",
        "phone": "+919876502001",
        "programme": "BTECH-CSE",
        "campus": "Main Campus",
        "captcha_token": "test-captcha",
    }
    payload.update(overrides)
    return payload


async def test_submission_creates_website_lead_with_consent_and_appears_in_list(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    payload = _payload(
        consent_promotional=True,
        consent_transactional=True,
    )
    response = await app_client.post("/api/public/enquiries", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "received"
    assert body["duplicate_detected"] is False
    assert body["id"] == body["lead_id"]

    async with db_session_factory() as session:
        lead = await session.get(Lead, uuid.UUID(str(body["lead_id"])))
        assert lead is not None
        source = await session.get(LeadSource, lead.source_id)
        assert source is not None
        assert source.name == "Website"
        student = await session.get(Student, lead.student_id)
        assert student is not None
        assert student.email_normalised == payload["email"]

        records = (
            (
                await session.execute(
                    select(ConsentRecord).where(ConsentRecord.student_id == student.id)
                )
            )
            .scalars()
            .all()
        )
        assert {(record.channel, record.category) for record in records} == {
            (ConsentChannel.EMAIL, ConsentCategory.PROMOTIONAL),
            (ConsentChannel.EMAIL, ConsentCategory.TRANSACTIONAL),
            (ConsentChannel.WHATSAPP, ConsentCategory.PROMOTIONAL),
            (ConsentChannel.WHATSAPP, ConsentCategory.TRANSACTIONAL),
        }
        assert all(record.method == "web_form" for record in records)

    manager = await _token(app_client, MANAGER)
    listing = await app_client.get(
        "/api/leads",
        headers=_auth(manager),
        params={"limit": 100},
    )
    assert listing.status_code == 200, listing.text
    assert str(body["lead_id"]) in {item["id"] for item in listing.json()["items"]}


async def test_missing_consent_checkbox_still_creates_lead_without_promotional_consent(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = await app_client.post(
        "/api/public/enquiries",
        json=_payload(email="no.consent@example.com", phone=None),
    )
    assert response.status_code == 201, response.text
    lead_id = uuid.UUID(str(response.json()["lead_id"]))

    async with db_session_factory() as session:
        lead = await session.get(Lead, lead_id)
        assert lead is not None
        count = await session.scalar(
            select(func.count(ConsentRecord.id)).where(
                ConsentRecord.student_id == lead.student_id,
                ConsentRecord.category == ConsentCategory.PROMOTIONAL,
            )
        )
        assert count == 0


async def test_duplicate_submission_returns_existing_lead_with_flag(
    seeded_database: None,
    app_client: AsyncClient,
) -> None:
    payload = _payload(email="public.duplicate@example.com", phone=None)
    first = await app_client.post("/api/public/enquiries", json=payload)
    second = await app_client.post("/api/public/enquiries", json=payload)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["duplicate_detected"] is False
    assert second.json()["duplicate_detected"] is True
    assert second.json()["lead_id"] == first.json()["lead_id"]


async def test_invalid_captcha_is_rejected_without_creating_a_lead(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = await app_client.post(
        "/api/public/enquiries",
        json=_payload(email="captcha.fail@example.com", captcha_token="invalid"),
    )
    assert response.status_code == 400, response.text
    assert response.json() == {"detail": "captcha_failed"}

    async with db_session_factory() as session:
        count = await session.scalar(
            select(func.count(Student.id)).where(
                Student.email_normalised == "captcha.fail@example.com"
            )
        )
        assert count == 0


async def test_eleventh_submission_from_one_ip_is_rate_limited(
    seeded_database: None,
    app_client: AsyncClient,
    app: FastAPI,
) -> None:
    await _clear_rate_limits(app)
    for index in range(10):
        response = await app_client.post(
            "/api/public/enquiries",
            json=_payload(email=f"rate.limit{index}@example.com", phone=None),
        )
        assert response.status_code == 201, response.text

    limited = await app_client.post(
        "/api/public/enquiries",
        json=_payload(email="rate.limit.blocked@example.com", phone=None),
    )
    assert limited.status_code == 429, limited.text
    assert limited.json() == {"detail": "rate_limited"}
    assert int(limited.headers["Retry-After"]) > 0


async def test_enquiry_requires_a_contact_key(
    seeded_database: None,
    app_client: AsyncClient,
) -> None:
    response = await app_client.post(
        "/api/public/enquiries",
        json=_payload(email=None, phone=None),
    )
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "contact_required"}


async def test_enquiry_rejects_unknown_programme(
    seeded_database: None,
    app_client: AsyncClient,
) -> None:
    response = await app_client.post(
        "/api/public/enquiries",
        json=_payload(email="unknown.programme@example.com", programme="NO-SUCH-COURSE"),
    )
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "programme_not_found"}
