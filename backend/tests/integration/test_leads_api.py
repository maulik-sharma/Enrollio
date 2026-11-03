"""M2.7 lead list, detail, manual creation, and edit endpoints."""

from __future__ import annotations

import time
import uuid
from typing import cast

import pytest
from httpx import AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.domain import DuplicateCandidateStatus, LifecycleStatus
from app.models.duplicate_candidate import DuplicateCandidate
from app.models.lead import Lead
from app.models.programme import Programme
from app.models.student import Student
from app.repositories import users as users_repo
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


async def _programme_id(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        programme = await session.scalar(select(Programme).where(Programme.code == "BTECH-CSE"))
        assert programme is not None
        return programme.id


async def _counsellor_id(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        counsellor = await users_repo.get_by_email(session, COUNSELLOR)
        assert counsellor is not None
        return counsellor.id


async def _seed_leads(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    count: int,
    assigned_to: uuid.UUID | None = None,
) -> list[uuid.UUID]:
    async with session_factory() as session:
        ids: list[uuid.UUID] = []
        for index in range(count):
            student = Student(
                first_name="List",
                last_name=f"Lead{index}",
                email_normalised=f"list.lead{index}.{uuid.uuid4().hex[:8]}@example.com",
            )
            session.add(student)
            await session.flush()
            lead = Lead(
                student_id=student.id,
                admission_cycle="2026-fall",
                lifecycle_status=LifecycleStatus.NEW_ENQUIRY,
                assigned_counsellor_id=assigned_to,
            )
            session.add(lead)
            await session.flush()
            ids.append(lead.id)
        await session.commit()
        return ids


async def _create_manual(
    client: AsyncClient,
    token: str,
    programme_id: uuid.UUID,
    *,
    first_name: str = "Manual",
    last_name: str = "Lead",
    email: str | None = None,
    phone: str | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "first_name": first_name,
        "last_name": last_name,
        "programme_id": str(programme_id),
    }
    if email is not None:
        payload["email"] = email
    if phone is not None:
        payload["phone"] = phone
    payload.update(extra or {})
    response = await client.post("/api/leads", headers=_auth(token), json=payload)
    assert response.status_code in {200, 201}, response.text
    return cast(dict[str, object], response.json())


async def test_list_is_scoped_cursor_paginated_and_filterable(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    counsellor_id = await _counsellor_id(db_session_factory)
    own_ids = await _seed_leads(db_session_factory, count=3, assigned_to=counsellor_id)
    other_ids = await _seed_leads(db_session_factory, count=2)
    manager = await _token(app_client, MANAGER)
    counsellor = await _token(app_client, COUNSELLOR)

    first = await app_client.get(
        "/api/leads",
        headers=_auth(manager),
        params={"limit": 2},
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"]

    second = await app_client.get(
        "/api/leads",
        headers=_auth(manager),
        params={"limit": 2, "cursor": body["next_cursor"]},
    )
    assert second.status_code == 200, second.text
    seen = [item["id"] for item in body["items"]] + [item["id"] for item in second.json()["items"]]
    assert len(seen) == len(set(seen))

    scoped = await app_client.get(
        "/api/leads",
        headers=_auth(counsellor),
        params={"limit": 100},
    )
    assert scoped.status_code == 200, scoped.text
    scoped_ids = {item["id"] for item in scoped.json()["items"]}
    assert scoped_ids == {str(lead_id) for lead_id in own_ids}
    assert not scoped_ids & {str(lead_id) for lead_id in other_ids}

    filtered = await app_client.get(
        "/api/leads",
        headers=_auth(manager),
        params={"assigned_counsellor_id": str(counsellor_id)},
    )
    assert filtered.status_code == 200, filtered.text
    assert {item["id"] for item in filtered.json()["items"]} == {
        str(lead_id) for lead_id in own_ids
    }

    bad_cursor = await app_client.get(
        "/api/leads",
        headers=_auth(manager),
        params={"cursor": "not-a-cursor"},
    )
    assert bad_cursor.status_code == 422
    assert bad_cursor.json() == {"detail": "invalid_cursor"}


async def test_detail_returns_student_and_consent_summary_and_denies_foreign_leads(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    programme_id = await _programme_id(db_session_factory)
    manager = await _token(app_client, MANAGER)
    created = await _create_manual(
        app_client,
        manager,
        programme_id,
        email="detail.student@example.com",
        phone="+919876501001",
    )
    lead_id = str(created["id"])

    detail = await app_client.get(f"/api/leads/{lead_id}", headers=_auth(manager))
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["lead"]["id"] == lead_id
    assert body["student"]["email_normalised"] == "detail.student@example.com"
    assert body["consent_summary"] == []
    assert body["assessments"] == []

    counsellor = await _token(app_client, COUNSELLOR)
    hidden = await app_client.get(f"/api/leads/{lead_id}", headers=_auth(counsellor))
    assert hidden.status_code == 404

    missing = await app_client.get(f"/api/leads/{uuid.uuid4()}", headers=_auth(manager))
    assert missing.status_code == 404


async def test_manual_create_dedupes_contacts_and_creates_name_candidate(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    programme_id = await _programme_id(db_session_factory)
    manager = await _token(app_client, MANAGER)

    first = await _create_manual(
        app_client,
        manager,
        programme_id,
        first_name="Same",
        last_name="Person",
        email="same.person@example.com",
        phone="+919876501002",
    )
    assert first["duplicate_detected"] is False
    assert first["assigned_counsellor_id"] is None

    duplicate = await _create_manual(
        app_client,
        manager,
        programme_id,
        first_name="Same",
        last_name="Person",
        email="same.person@example.com",
        phone="+919876501002",
    )
    assert duplicate["duplicate_detected"] is True
    assert duplicate["id"] == first["id"]

    name_only = await _create_manual(
        app_client,
        manager,
        programme_id,
        first_name="Same",
        last_name="Person",
        email="same.person.other@example.com",
    )
    assert name_only["duplicate_detected"] is False
    assert name_only["id"] != first["id"]

    async with db_session_factory() as session:
        pending = await session.scalar(
            select(DuplicateCandidate).where(
                DuplicateCandidate.reason == "name_only",
                DuplicateCandidate.status == DuplicateCandidateStatus.PENDING,
            )
        )
        assert pending is not None
        assert str(pending.student_id) == first["student_id"]
        assert str(pending.candidate_student_id) == name_only["student_id"]


async def test_manual_create_rejects_conflicting_contacts(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    programme_id = await _programme_id(db_session_factory)
    manager = await _token(app_client, MANAGER)

    await _create_manual(
        app_client,
        manager,
        programme_id,
        first_name="Email",
        last_name="Owner",
        email="email.owner@example.com",
        phone="+919876501003",
    )
    await _create_manual(
        app_client,
        manager,
        programme_id,
        first_name="Phone",
        last_name="Owner",
        email="phone.owner@example.com",
        phone="+919876501004",
    )

    response = await app_client.post(
        "/api/leads",
        headers=_auth(manager),
        json={
            "first_name": "Conflict",
            "last_name": "Owner",
            "programme_id": str(programme_id),
            "email": "email.owner@example.com",
            "phone": "+919876501004",
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "conflicting_contact"


async def test_patch_edits_fields_but_never_lifecycle_and_enforces_scope(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    programme_id = await _programme_id(db_session_factory)
    counsellor_id = await _counsellor_id(db_session_factory)
    manager = await _token(app_client, MANAGER)
    counsellor = await _token(app_client, COUNSELLOR)

    created = await _create_manual(
        app_client,
        manager,
        programme_id,
        email="patch.student@example.com",
        phone="+919876501005",
    )
    lead_id = str(created["id"])

    forbidden_lifecycle = await app_client.patch(
        f"/api/leads/{lead_id}",
        headers=_auth(manager),
        json={"lifecycle_status": "contacted"},
    )
    assert forbidden_lifecycle.status_code == 422

    updated = await app_client.patch(
        f"/api/leads/{lead_id}",
        headers=_auth(manager),
        json={
            "first_name": "Patched",
            "academic_score": "88.5",
            "date_of_birth": "2004-02-29",
            "assigned_counsellor_id": str(counsellor_id),
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["assigned_counsellor_id"] == str(counsellor_id)

    detail = await app_client.get(f"/api/leads/{lead_id}", headers=_auth(counsellor))
    assert detail.status_code == 200, detail.text
    assert detail.json()["student"]["first_name"] == "Patched"
    assert (
        detail.json()["student"]["academic_score"] == "88.50"
        or detail.json()["student"]["academic_score"] == "88.5"
    )
    assert detail.json()["student"]["date_of_birth"] == "2004-02-29"
    assert detail.json()["lead"]["lifecycle_status"] == "new_enquiry"

    counsellor_assign = await app_client.patch(
        f"/api/leads/{lead_id}",
        headers=_auth(counsellor),
        json={"assigned_counsellor_id": str(counsellor_id)},
    )
    assert counsellor_assign.status_code == 403

    anonymous = await app_client.patch(f"/api/leads/{lead_id}", json={"first_name": "Nope"})
    assert anonymous.status_code == 401


async def test_counsellor_cannot_patch_someone_elses_lead(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    other_ids = await _seed_leads(db_session_factory, count=1)
    counsellor = await _token(app_client, COUNSELLOR)
    response = await app_client.patch(
        f"/api/leads/{other_ids[0]}",
        headers=_auth(counsellor),
        json={"first_name": "Nope"},
    )
    assert response.status_code == 404


@pytest.mark.performance
async def test_list_p95_stays_under_conservative_threshold_with_ten_thousand_leads(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    students: list[dict[str, object]] = []
    leads: list[dict[str, object]] = []
    for index in range(10_000):
        student_id = uuid.uuid4()
        lead_id = uuid.uuid4()
        students.append(
            {
                "id": student_id,
                "first_name": "Perf",
                "last_name": f"Lead{index}",
                "email_normalised": f"perf.lead{index}@example.com",
            }
        )
        leads.append(
            {
                "id": lead_id,
                "student_id": student_id,
                "admission_cycle": "2026-fall",
                "lifecycle_status": LifecycleStatus.NEW_ENQUIRY,
            }
        )

    async with db_session_factory() as session:
        await session.execute(insert(Student), students)
        await session.execute(insert(Lead), leads)
        await session.commit()

    manager = await _token(app_client, MANAGER)
    timings: list[float] = []
    for _ in range(21):
        started = time.perf_counter()
        response = await app_client.get(
            "/api/leads",
            headers=_auth(manager),
            params={"limit": 25},
        )
        timings.append(time.perf_counter() - started)
        assert response.status_code == 200, response.text
        assert len(response.json()["items"]) == 25

    timings.sort()
    p95 = timings[max(0, int(len(timings) * 0.95) - 1)]
    assert p95 < 1.5, f"P95 was {p95:.3f}s"
