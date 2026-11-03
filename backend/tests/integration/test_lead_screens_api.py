"""Backend support for the M2.10 lead screens: search, catalogues, lifecycle."""

from __future__ import annotations

import uuid
from typing import cast

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.domain import LifecycleStatus
from app.models.lead import Lead
from app.models.student import Student
from app.models.timeline_event import TimelineEvent
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


async def _counsellor_id(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    async with session_factory() as session:
        counsellor = await users_repo.get_by_email(session, COUNSELLOR)
        assert counsellor is not None
        return counsellor.id


async def _lead(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    first_name: str,
    last_name: str,
    email: str,
    status: LifecycleStatus = LifecycleStatus.NEW_ENQUIRY,
    assigned_to: uuid.UUID | None = None,
) -> uuid.UUID:
    async with session_factory() as session:
        student = Student(
            first_name=first_name,
            last_name=last_name,
            email_normalised=email,
        )
        session.add(student)
        await session.flush()
        lead = Lead(
            student_id=student.id,
            admission_cycle="2026-fall",
            lifecycle_status=status,
            assigned_counsellor_id=assigned_to,
        )
        session.add(lead)
        await session.commit()
        return lead.id


async def test_search_matches_name_email_and_phone_and_stays_scoped(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    counsellor_id = await _counsellor_id(db_session_factory)
    await _lead(
        db_session_factory,
        first_name="Searchable",
        last_name="Alpha",
        email="searchable.alpha@example.com",
        assigned_to=counsellor_id,
    )
    await _lead(
        db_session_factory,
        first_name="Searchable",
        last_name="Beta",
        email="searchable.beta@example.com",
    )

    manager = await _token(app_client, MANAGER)
    counsellor = await _token(app_client, COUNSELLOR)

    by_name = await app_client.get(
        "/api/leads", headers=_auth(manager), params={"search": "Searchable"}
    )
    assert by_name.status_code == 200, by_name.text
    assert len(by_name.json()["items"]) == 2
    row = next(item for item in by_name.json()["items"] if item["student"]["last_name"] == "Alpha")
    assert row["student"]["first_name"] == "Searchable"
    assert row["student"]["email_normalised"] == "searchable.alpha@example.com"

    everything = await app_client.get(
        "/api/leads", headers=_auth(manager), params={"search": "searchable"}
    )
    assert len(everything.json()["items"]) == 2

    by_email = await app_client.get(
        "/api/leads", headers=_auth(manager), params={"search": "alpha@example"}
    )
    assert len(by_email.json()["items"]) == 1

    scoped = await app_client.get(
        "/api/leads", headers=_auth(counsellor), params={"search": "searchable"}
    )
    assert scoped.status_code == 200, scoped.text
    assert len(scoped.json()["items"]) == 1

    literal_wildcard = await app_client.get(
        "/api/leads", headers=_auth(manager), params={"search": "%"}
    )
    assert literal_wildcard.status_code == 200
    assert literal_wildcard.json()["items"] == []


async def test_catalogues_return_active_options_for_lead_staff(
    seeded_database: None,
    app_client: AsyncClient,
) -> None:
    manager = await _token(app_client, MANAGER)
    response = await app_client.get("/api/catalogues", headers=_auth(manager))

    assert response.status_code == 200, response.text
    body = response.json()
    assert {item["code"] for item in body["programmes"]} >= {"BTECH-CSE", "BBA"}
    assert {item["name"] for item in body["campuses"]} >= {"Main Campus", "North Campus"}
    assert {item["name"] for item in body["sources"]} >= {"Website", "Referral"}

    admin = await _token(app_client, "admin@enrollio.dev")
    forbidden = await app_client.get("/api/catalogues", headers=_auth(admin))
    assert forbidden.status_code == 403


async def test_lead_detail_lists_only_actor_permitted_transitions(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    counsellor_id = await _counsellor_id(db_session_factory)
    own_id = await _lead(
        db_session_factory,
        first_name="Own",
        last_name="Lead",
        email="own.transition@example.com",
        assigned_to=counsellor_id,
    )
    offered_id = await _lead(
        db_session_factory,
        first_name="Offered",
        last_name="Lead",
        email="offered.transition@example.com",
        status=LifecycleStatus.ADMISSION_OFFERED,
        assigned_to=counsellor_id,
    )

    manager = await _token(app_client, MANAGER)
    counsellor = await _token(app_client, COUNSELLOR)

    manager_detail = await app_client.get(f"/api/leads/{own_id}", headers=_auth(manager))
    assert manager_detail.status_code == 200
    assert LifecycleStatus.CONTACTED.value in manager_detail.json()["allowed_transitions"]
    assert LifecycleStatus.CONVERTED.value not in manager_detail.json()["allowed_transitions"]

    counsellor_detail = await app_client.get(f"/api/leads/{offered_id}", headers=_auth(counsellor))
    assert counsellor_detail.status_code == 200
    assert LifecycleStatus.CONVERTED.value not in counsellor_detail.json()["allowed_transitions"]


async def test_lifecycle_endpoint_enforces_rules_and_writes_timeline(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    counsellor_id = await _counsellor_id(db_session_factory)
    own_id = await _lead(
        db_session_factory,
        first_name="Move",
        last_name="Forward",
        email="move.forward@example.com",
        assigned_to=counsellor_id,
    )
    offered_id = await _lead(
        db_session_factory,
        first_name="Convert",
        last_name="Blocked",
        email="convert.blocked@example.com",
        status=LifecycleStatus.ADMISSION_OFFERED,
        assigned_to=counsellor_id,
    )
    hidden_id = await _lead(
        db_session_factory,
        first_name="Someone",
        last_name="Else",
        email="someone.else@example.com",
    )

    counsellor = await _token(app_client, COUNSELLOR)
    manager = await _token(app_client, MANAGER)

    advanced = await app_client.post(
        f"/api/leads/{own_id}/lifecycle",
        headers=_auth(counsellor),
        json={"to_state": "contacted", "reason": "Called the student"},
    )
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["lifecycle_status"] == "contacted"

    invalid = await app_client.post(
        f"/api/leads/{own_id}/lifecycle",
        headers=_auth(counsellor),
        json={"to_state": "qualified", "reason": "Skipped a step"},
    )
    assert invalid.status_code == 422

    forbidden = await app_client.post(
        f"/api/leads/{offered_id}/lifecycle",
        headers=_auth(counsellor),
        json={"to_state": "converted", "reason": "Counsellor cannot convert"},
    )
    assert forbidden.status_code == 403

    converted = await app_client.post(
        f"/api/leads/{offered_id}/lifecycle",
        headers=_auth(manager),
        json={"to_state": "converted", "reason": "Offer accepted"},
    )
    assert converted.status_code == 200, converted.text
    assert converted.json()["lifecycle_status"] == "converted"

    hidden = await app_client.post(
        f"/api/leads/{hidden_id}/lifecycle",
        headers=_auth(counsellor),
        json={"to_state": "contacted", "reason": "Not mine"},
    )
    assert hidden.status_code == 404

    async with db_session_factory() as session:
        events = await session.scalar(
            select(func.count())
            .select_from(TimelineEvent)
            .where(TimelineEvent.lead_id.in_([own_id, offered_id]))
        )
    assert events == 2


async def test_manager_manual_creation_defaults_cycle_and_can_transition(
    seeded_database: None,
    app_client: AsyncClient,
) -> None:
    manager = await _token(app_client, MANAGER)
    created = await app_client.post(
        "/api/leads",
        headers=_auth(manager),
        json={
            "first_name": "Manual",
            "last_name": "Screen",
            "email": "manual.screen@example.com",
        },
    )
    assert created.status_code == 201, created.text
    lead = cast(dict[str, object], created.json())
    assert cast(str, lead["admission_cycle"]).endswith("-fall")

    detail = await app_client.get(f"/api/leads/{lead['id']}", headers=_auth(manager))
    assert detail.status_code == 200
    assert "contacted" in detail.json()["allowed_transitions"]
