"""Consent API, send checks, and promotional opt-out lifecycle handling."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.domain import ConsentCategory, ConsentChannel, LifecycleStatus
from app.models.lead import Lead
from app.models.student import Student
from app.services.consent import can_send
from tests.conftest import requires_postgres

pytestmark = [requires_postgres]

PASSWORD = "demo-password-123"
MANAGER = "manager@enrollio.dev"
COUNSELLOR = "counsellor@enrollio.dev"


async def _token(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _student_and_lead(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[uuid.UUID, uuid.UUID]:
    async with session_factory() as session:
        student = Student(
            first_name="Consent",
            last_name="Tester",
            email_normalised="consent.tester@example.com",
            phone_e164="+919876500010",
        )
        session.add(student)
        await session.flush()
        lead = Lead(
            student_id=student.id,
            admission_cycle="2026-fall",
            lifecycle_status=LifecycleStatus.NEW_ENQUIRY,
        )
        session.add(lead)
        await session.commit()
        return student.id, lead.id


async def test_grant_then_revoke_blocks_promotional_and_keeps_transactional(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    student_id, lead_id = await _student_and_lead(db_session_factory)
    token = await _token(app_client, MANAGER)

    grant = await app_client.post(
        f"/api/students/{student_id}/consent",
        headers=_auth(token),
        json={
            "channel": "email",
            "category": "promotional",
            "source": "web_form",
            "method": "checkbox",
        },
    )
    assert grant.status_code == 201, grant.text
    assert grant.json()["granted"] is True

    async with db_session_factory() as session:
        assert await can_send(
            session,
            student_id=student_id,
            channel=ConsentChannel.EMAIL,
            category=ConsentCategory.PROMOTIONAL,
        )

    revoke = await app_client.delete(
        f"/api/students/{student_id}/consent/email/promotional",
        headers=_auth(token),
        params={"source": "unsubscribe", "method": "link"},
    )
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["granted"] is False

    async with db_session_factory() as session:
        assert not await can_send(
            session,
            student_id=student_id,
            channel=ConsentChannel.EMAIL,
            category=ConsentCategory.PROMOTIONAL,
        )
        assert await can_send(
            session,
            student_id=student_id,
            channel=ConsentChannel.EMAIL,
            category=ConsentCategory.TRANSACTIONAL,
        )
        lead = await session.get(Lead, lead_id)
        assert lead is not None
        assert lead.lifecycle_status is LifecycleStatus.OPTED_OUT

    explicit_transactional_revoke = await app_client.delete(
        f"/api/students/{student_id}/consent/email/transactional",
        headers=_auth(token),
    )
    assert explicit_transactional_revoke.status_code == 200, explicit_transactional_revoke.text

    async with db_session_factory() as session:
        assert not await can_send(
            session,
            student_id=student_id,
            channel=ConsentChannel.EMAIL,
            category=ConsentCategory.TRANSACTIONAL,
        )


async def test_one_remaining_promotional_grant_prevents_opt_out(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    student_id, lead_id = await _student_and_lead(db_session_factory)
    token = await _token(app_client, MANAGER)

    for channel in ("email", "whatsapp"):
        response = await app_client.post(
            f"/api/students/{student_id}/consent",
            headers=_auth(token),
            json={"channel": channel, "category": "promotional"},
        )
        assert response.status_code == 201, response.text

    first = await app_client.delete(
        f"/api/students/{student_id}/consent/email/promotional",
        headers=_auth(token),
    )
    assert first.status_code == 200, first.text

    async with db_session_factory() as session:
        lead = await session.get(Lead, lead_id)
        assert lead is not None
        assert lead.lifecycle_status is LifecycleStatus.NEW_ENQUIRY

    second = await app_client.delete(
        f"/api/students/{student_id}/consent/whatsapp/promotional",
        headers=_auth(token),
    )
    assert second.status_code == 200, second.text

    async with db_session_factory() as session:
        lead = await session.get(Lead, lead_id)
        assert lead is not None
        assert lead.lifecycle_status is LifecycleStatus.OPTED_OUT


async def test_consent_endpoints_require_lead_view_all(
    seeded_database: None,
    app_client: AsyncClient,
) -> None:
    student_id = uuid.uuid4()
    counsellor = await _token(app_client, COUNSELLOR)
    response = await app_client.post(
        f"/api/students/{student_id}/consent",
        headers=_auth(counsellor),
        json={"channel": "email", "category": "promotional"},
    )
    assert response.status_code == 403
