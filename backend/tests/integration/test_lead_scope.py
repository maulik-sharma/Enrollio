"""The M1.3 cross-counsellor security gate, now against real leads (Q-006).

M1.3 could only unit-test ``can_access_lead`` because the ``leads`` table did
not exist. This test wires the same rule to real rows, real users, and real
tokens through a temporary endpoint that mirrors how M2.7 will use it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, status
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import CurrentUserDep, SessionDep
from app.core.config import Settings
from app.core.permissions import RoleSlug
from app.models.lead import Lead
from app.models.programme import Programme
from app.models.student import Student
from app.repositories import users as users_repo
from app.services import users as users_service
from app.services.access import can_access_lead
from tests.conftest import requires_postgres

pytestmark = requires_postgres

PASSWORD = "demo-password-123"
MANAGER = "manager@enrollio.dev"
COUNSELLOR = "counsellor@enrollio.dev"
SECOND_COUNSELLOR = "second.counsellor@enrollio.dev"


@dataclass(frozen=True)
class _Leads:
    assigned_to_first: uuid.UUID
    assigned_to_second: uuid.UUID
    unassigned: uuid.UUID


async def _access_token(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _add_lead_route(app: FastAPI) -> None:
    """Mirror the M2.7 read endpoint: a denied lead is indistinguishable from missing."""

    @app.get("/_test/leads/{lead_id}")
    async def read_lead(
        lead_id: uuid.UUID,
        session: SessionDep,
        user: CurrentUserDep,
    ) -> dict[str, str]:
        lead = await session.get(Lead, lead_id)
        if lead is None or not can_access_lead(user, lead):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found",
            )
        return {"id": str(lead.id)}


async def _seed_leads(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> _Leads:
    async with session_factory() as session:
        first = await users_repo.get_by_email(session, COUNSELLOR)
        assert first is not None, "seeded_database must create the demo counsellor"
        second = await users_service.create_user(
            session,
            settings,
            email=SECOND_COUNSELLOR,
            full_name="Second Counsellor",
            password=PASSWORD,
            role_slugs=[RoleSlug.ADMISSION_COUNSELLOR.value],
        )

        programme = await session.scalar(select(Programme).where(Programme.code == "BTECH-CSE"))
        assert programme is not None, "seeded_database must create the demo programme"

        def student(marker: str) -> Student:
            return Student(
                first_name="Lead",
                last_name=marker,
                email_normalised=f"{marker.lower()}@enrollio.dev",
            )

        first_student = student("First")
        second_student = student("Second")
        unassigned_student = student("Unassigned")
        session.add_all([first_student, second_student, unassigned_student])
        await session.flush()

        def lead(student_id: uuid.UUID, counsellor_id: uuid.UUID | None) -> Lead:
            return Lead(
                student_id=student_id,
                programme_id=programme.id,
                admission_cycle="2026-fall",
                assigned_counsellor_id=counsellor_id,
            )

        assigned_to_first = lead(first_student.id, first.id)
        assigned_to_second = lead(second_student.id, second.id)
        unassigned = lead(unassigned_student.id, None)
        session.add_all([assigned_to_first, assigned_to_second, unassigned])
        await session.commit()

        return _Leads(
            assigned_to_first=assigned_to_first.id,
            assigned_to_second=assigned_to_second.id,
            unassigned=unassigned.id,
        )


async def test_counsellors_cannot_read_each_others_leads(
    seeded_database: None,
    app: FastAPI,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    _add_lead_route(app)
    leads = await _seed_leads(db_session_factory, test_settings)

    first = await _access_token(app_client, COUNSELLOR)
    second = await _access_token(app_client, SECOND_COUNSELLOR)

    own = await app_client.get(f"/_test/leads/{leads.assigned_to_first}", headers=_auth(first))
    other = await app_client.get(f"/_test/leads/{leads.assigned_to_second}", headers=_auth(first))
    other_own = await app_client.get(
        f"/_test/leads/{leads.assigned_to_second}", headers=_auth(second)
    )
    other_denied = await app_client.get(
        f"/_test/leads/{leads.assigned_to_first}", headers=_auth(second)
    )
    unassigned = await app_client.get(f"/_test/leads/{leads.unassigned}", headers=_auth(first))

    assert own.status_code == 200
    assert other.status_code == 404
    assert other.json() == {"detail": "Lead not found"}
    assert other_own.status_code == 200
    assert other_denied.status_code == 404
    assert unassigned.status_code == 404


async def test_manager_can_read_any_lead_and_unknown_ids_are_404(
    seeded_database: None,
    app: FastAPI,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    _add_lead_route(app)
    leads = await _seed_leads(db_session_factory, test_settings)
    manager = await _access_token(app_client, MANAGER)

    responses: list[Response] = [
        await app_client.get(f"/_test/leads/{lead_id}", headers=_auth(manager))
        for lead_id in (
            leads.assigned_to_first,
            leads.assigned_to_second,
            leads.unassigned,
            uuid.uuid4(),
        )
    ]

    assert [response.status_code for response in responses] == [200, 200, 200, 404]
