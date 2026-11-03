"""M2.9 source-scoped API keys and partner lead ingestion."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.domain import DuplicateCandidateStatus
from app.models.api_key import ApiKey
from app.models.campus import Campus
from app.models.duplicate_candidate import DuplicateCandidate
from app.models.lead import Lead
from app.models.lead_source import LeadSource
from app.models.programme import Programme
from app.models.student import Student
from tests.conftest import requires_postgres

pytestmark = [requires_postgres]

PASSWORD = "demo-password-123"
ADMIN = "admin@enrollio.dev"
MANAGER = "manager@enrollio.dev"


async def _token(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _source_id(
    session_factory: async_sessionmaker[AsyncSession],
    name: str,
) -> uuid.UUID:
    async with session_factory() as session:
        source = await session.scalar(select(LeadSource).where(LeadSource.name == name))
        assert source is not None
        return source.id


async def _create_key(
    client: AsyncClient,
    admin_token: str,
    source_id: uuid.UUID,
    *,
    name: str = "Test partner",
) -> dict[str, object]:
    response = await client.post(
        "/api/integrations/api-keys",
        headers=_auth(admin_token),
        json={"name": name, "source_id": str(source_id)},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


def _key_headers(key: str) -> dict[str, str]:
    return {"X-API-Key": key}


def _record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "first_name": "Partner",
        "last_name": "Lead",
        "email": f"partner.{uuid.uuid4().hex[:10]}@example.com",
        "programme": "BTECH-CSE",
        "campus": "Main Campus",
        "score": "82.5",
        "graduation_year": 2025,
    }
    value.update(overrides)
    return value


async def test_api_key_management_and_ingestion_uses_key_source(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = await _token(app_client, ADMIN)
    manager = await _token(app_client, MANAGER)
    referral_id = await _source_id(db_session_factory, "Referral")

    forbidden = await app_client.post(
        "/api/integrations/api-keys",
        headers=_auth(manager),
        json={"name": "Manager key", "source_id": str(referral_id)},
    )
    assert forbidden.status_code == 403

    unauthenticated = await app_client.post(
        "/api/integrations/api-keys",
        json={"name": "Anon key", "source_id": str(referral_id)},
    )
    assert unauthenticated.status_code == 401

    created = await _create_key(app_client, admin, referral_id)
    key = str(created["key"])
    assert key.startswith("enr_")
    assert created["api_key"] == key
    assert created["key_prefix"] == key[:12]
    assert created["source_id"] == str(referral_id)

    payload = _record(source="Website", email="api.source.scope@example.com")
    response = await app_client.post(
        "/api/integrations/leads",
        headers=_key_headers(key),
        json=[payload],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["created"] == 1
    assert body["results"][0]["status"] == "created"

    async with db_session_factory() as session:
        lead = await session.get(Lead, uuid.UUID(str(body["results"][0]["lead_id"])))
        assert lead is not None
        assert lead.source_id == referral_id
        student = await session.get(Student, lead.student_id)
        assert student is not None
        assert student.email_normalised == "api.source.scope@example.com"
        programme = await session.get(Programme, lead.programme_id)
        campus = await session.get(Campus, lead.campus_id)
        assert programme is not None and programme.code == "BTECH-CSE"
        assert campus is not None and campus.name == "Main Campus"


async def test_batch_reports_each_outcome_and_isolates_failures(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = await _token(app_client, ADMIN)
    referral_id = await _source_id(db_session_factory, "Referral")
    created = await _create_key(app_client, admin, referral_id)
    key = str(created["key"])

    async with db_session_factory() as session:
        merged_student = Student(
            first_name="Already",
            last_name="Known",
            email_normalised="already.known@example.com",
        )
        email_owner = Student(
            first_name="Email",
            last_name="Owner",
            email_normalised="email.owner@example.com",
        )
        phone_owner = Student(
            first_name="Phone",
            last_name="Owner",
            phone_e164="+919876543210",
        )
        session.add_all([merged_student, email_owner, phone_owner])
        await session.commit()

    records: list[object] = [
        _record(email="same.batch@example.com", phone=None),
        _record(email="same.batch@example.com", phone=None),
        _record(email=None, phone=None),
        _record(email="email.owner@example.com", phone="+919876543210"),
        _record(email="already.known@example.com", phone=None),
        "not-a-record",
        _record(email="invalid.programme@example.com", programme="DOES-NOT-EXIST"),
        _record(email="still.processed@example.com", phone=None),
    ]
    response = await app_client.post(
        "/api/integrations/leads",
        headers=_key_headers(key),
        json=records,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["total"] == len(records)
    assert body["created"] == 2
    assert body["duplicate"] == 1
    assert body["merged"] == 1
    assert body["rejected"] == 4
    statuses = [result["status"] for result in body["results"]]
    assert statuses == [
        "created",
        "duplicate",
        "rejected",
        "rejected",
        "merged",
        "rejected",
        "rejected",
        "created",
    ]
    assert [result["index"] for result in body["results"]] == list(range(len(records)))
    assert body["results"][2]["reason"] == "missing_contact"
    assert body["results"][3]["reason"] == "conflicting_contact"
    assert body["results"][5]["reason"] == "invalid_record"
    assert body["results"][6]["reason"] == "unknown_programme"
    assert body["results"][7]["lead_id"] is not None

    async with db_session_factory() as session:
        candidate_count = await session.scalar(
            select(func.count(DuplicateCandidate.id)).where(
                DuplicateCandidate.reason == "conflicting_contact",
                DuplicateCandidate.status == DuplicateCandidateStatus.PENDING,
            )
        )
        assert candidate_count == 1
        lead_sources = set((await session.execute(select(Lead.source_id))).scalars())
        assert lead_sources == {referral_id}


async def test_missing_invalid_and_expired_keys_are_rejected(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = await _token(app_client, ADMIN)
    referral_id = await _source_id(db_session_factory, "Referral")
    created = await _create_key(app_client, admin, referral_id)
    key = str(created["key"])
    record = _record(email="auth.required@example.com")

    assert (await app_client.post("/api/integrations/leads", json=[record])).status_code == 401
    assert (
        await app_client.post(
            "/api/integrations/leads",
            headers=_key_headers("enr_not-a-real-key"),
            json=[record],
        )
    ).status_code == 401
    bearer = await app_client.post(
        "/api/integrations/leads",
        headers={"Authorization": f"Bearer {key}"},
        json=[record],
    )
    assert bearer.status_code == 200, bearer.text

    async with db_session_factory() as session:
        api_key = await session.get(ApiKey, uuid.UUID(str(created["id"])))
        assert api_key is not None
        api_key.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()

    expired = await app_client.post(
        "/api/integrations/leads",
        headers=_key_headers(key),
        json=[record],
    )
    assert expired.status_code == 401


async def test_batch_limits_and_wire_shape(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = await _token(app_client, ADMIN)
    referral_id = await _source_id(db_session_factory, "Referral")
    created = await _create_key(app_client, admin, referral_id)
    key = str(created["key"])

    too_many = [
        {"first_name": "Bulk", "email": f"bulk.{index}@example.com"} for index in range(1001)
    ]
    response = await app_client.post(
        "/api/integrations/leads",
        headers=_key_headers(key),
        json=too_many,
    )
    assert response.status_code == 413, response.text
    assert response.json()["detail"] == "batch_too_large"

    empty = await app_client.post(
        "/api/integrations/leads",
        headers=_key_headers(key),
        json=[],
    )
    assert empty.status_code == 422

    malformed = await app_client.post(
        "/api/integrations/leads",
        headers=_key_headers(key),
        json={"first_name": "not a list"},
    )
    assert malformed.status_code == 422

    envelope = await app_client.post(
        "/api/integrations/leads",
        headers=_key_headers(key),
        json={"leads": [_record(email="envelope@example.com")]},
    )
    assert envelope.status_code == 200, envelope.text
    assert envelope.json()["created"] == 1


async def test_partner_can_push_500_leads(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    admin = await _token(app_client, ADMIN)
    referral_id = await _source_id(db_session_factory, "Referral")
    created = await _create_key(app_client, admin, referral_id)
    key = str(created["key"])

    records = [
        {
            "first_name": "Bulk",
            "last_name": f"Partner{index}",
            "email": f"bulk.partner.{index}@example.com",
            "programme": "BTECH-CSE",
            "admission_cycle": "2026-fall",
        }
        for index in range(500)
    ]
    response = await app_client.post(
        "/api/integrations/leads",
        headers=_key_headers(key),
        json=records,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 500
    assert body["created"] == 500
    assert len(body["results"]) == 500

    async with db_session_factory() as session:
        count = await session.scalar(select(func.count(Lead.id)))
        assert count == 500
