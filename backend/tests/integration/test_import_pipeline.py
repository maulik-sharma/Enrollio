"""M2.3 import pipeline: upload, mapping, counts, errors, and permissions."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.duplicate_candidate import DuplicateCandidate
from app.models.import_job import ImportJob
from app.models.lead import Lead
from app.models.student import Student
from tests.conftest import requires_postgres
from tests.fixtures.import_files import (
    HEADERS,
    MAPPER,
    merged_header_xlsx,
    mixed_csv,
    single_row_csv,
    too_many_rows_csv,
)

pytestmark = [pytest.mark.integration, requires_postgres]

PASSWORD = "demo-password-123"
MANAGER = "manager@enrollio.dev"
COUNSELLOR = "counsellor@enrollio.dev"


async def _token(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _upload(
    client: AsyncClient,
    token: str,
    *,
    filename: str = "mixed.csv",
    content: bytes | None = None,
    source_name: str = "Coaching Partner",
) -> dict[str, object]:
    response = await client.post(
        "/api/leads/import",
        headers=_auth(token),
        data={"source_name": source_name},
        files={"file": (filename, content or mixed_csv(), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _map(client: AsyncClient, token: str, job_id: object) -> dict[str, object]:
    response = await client.post(
        f"/api/imports/{job_id}/mapping",
        headers=_auth(token),
        json={"mapping": MAPPER},
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


async def _run_mixed_import(
    seeded_database: None,
    app_client: AsyncClient,
) -> tuple[dict[str, object], dict[str, object], str]:
    token = await _token(app_client, MANAGER)
    job = await _upload(app_client, token)
    result = await _map(app_client, token, job["id"])
    return job, result, token


async def test_mixed_import_produces_exact_counts_and_provenance(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    job, result, _ = await _run_mixed_import(seeded_database, app_client)

    assert job["headers"] == HEADERS
    assert job["status"] == "uploaded"
    assert job["total_rows"] == 100

    assert result["status"] == "completed"
    assert result["total_rows"] == 100
    assert result["created_count"] == 85
    assert result["merged_count"] == 0
    assert result["rejected_count"] == 10
    assert result["duplicate_count"] == 5

    async with db_session_factory() as session:
        student_count = (
            await session.execute(select(func.count()).select_from(Student))
        ).scalar_one()
        lead_count = (await session.execute(select(func.count()).select_from(Lead))).scalar_one()
        job_id = uuid.UUID(str(job["id"]))
        stored_job = await session.get(ImportJob, job_id)
        leads = (await session.execute(select(Lead))).scalars().all()
        students = (await session.execute(select(Student))).scalars().all()

    assert student_count == 85
    assert lead_count == 85
    assert stored_job is not None
    assert stored_job.created_count == 85
    assert all(lead.import_job_id == job_id for lead in leads)
    assert all(lead.raw_import_row for lead in leads)
    assert all(student.academic_score is not None for student in students)


async def test_mapping_is_saved_as_a_reusable_template(
    seeded_database: None,
    app_client: AsyncClient,
) -> None:
    job, _, token = await _run_mixed_import(seeded_database, app_client)

    response = await app_client.get(
        "/api/imports/mapping-template",
        params={"source_name": "Coaching Partner"},
        headers=_auth(token),
    )

    assert response.status_code == 200, response.text
    assert response.json()["source_name"] == "Coaching Partner"
    assert response.json()["mapping"] == MAPPER

    listing = await app_client.get("/api/imports", headers=_auth(token))
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == job["id"]
    assert listing.json()[0]["created_count"] == 85


async def test_error_csv_contains_original_rows_and_reasons(
    seeded_database: None,
    app_client: AsyncClient,
) -> None:
    job, result, token = await _run_mixed_import(seeded_database, app_client)
    assert result["rejected_count"] == 10

    response = await app_client.get(
        f"/api/imports/{job['id']}/errors.csv",
        headers=_auth(token),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    lines = response.text.strip().splitlines()
    assert lines[0] == "row_number,reason"
    assert len(lines) == 11

    rows_and_reasons = [line.split(",", 1) for line in lines[1:]]
    assert [int(row) for row, _ in rows_and_reasons] == list(range(92, 102))
    assert {reason for _, reason in rows_and_reasons} == {
        "invalid_name",
        "missing_contact",
        "invalid_email",
        "invalid_phone",
        "invalid_score",
        "unknown_programme",
        "unknown_campus",
        "unknown_source",
        "invalid_graduation_year",
        "conflicting_contact",
    }


async def test_reimporting_the_same_file_creates_nothing_new(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token = await _token(app_client, MANAGER)
    first = await _upload(app_client, token)
    await _map(app_client, token, first["id"])

    second = await _upload(app_client, token)
    result = await _map(app_client, token, second["id"])

    assert result["created_count"] == 0
    assert result["merged_count"] == 0
    assert result["rejected_count"] == 10
    assert result["duplicate_count"] == 90

    async with db_session_factory() as session:
        assert (await session.execute(select(func.count()).select_from(Student))).scalar_one() == 85
        assert (await session.execute(select(func.count()).select_from(Lead))).scalar_one() == 85


async def test_xlsx_with_merged_headers_returns_a_clear_error(
    seeded_database: None,
    app_client: AsyncClient,
) -> None:
    token = await _token(app_client, MANAGER)
    response = await app_client.post(
        "/api/leads/import",
        headers=_auth(token),
        data={"source_name": "Coaching Partner"},
        files={
            "file": (
                "merged.xlsx",
                merged_header_xlsx(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 422
    assert "Merged cells" in response.json()["detail"]


async def test_file_with_more_than_ten_thousand_rows_is_rejected(
    seeded_database: None,
    app_client: AsyncClient,
) -> None:
    token = await _token(app_client, MANAGER)
    response = await app_client.post(
        "/api/leads/import",
        headers=_auth(token),
        files={"file": ("too-many.csv", too_many_rows_csv(), "text/csv")},
    )

    assert response.status_code == 413
    assert "10000" in response.json()["detail"]


async def test_import_requires_leads_view_all(
    seeded_database: None,
    app_client: AsyncClient,
) -> None:
    anonymous = await app_client.post(
        "/api/leads/import",
        files={"file": ("mixed.csv", mixed_csv(), "text/csv")},
    )
    assert anonymous.status_code == 401

    counsellor = await _token(app_client, COUNSELLOR)
    forbidden = await app_client.post(
        "/api/leads/import",
        headers=_auth(counsellor),
        files={"file": ("mixed.csv", mixed_csv(), "text/csv")},
    )
    assert forbidden.status_code == 403

    history = await app_client.get("/api/imports", headers=_auth(counsellor))
    assert history.status_code == 403

    manager = await _token(app_client, MANAGER)
    listing = await app_client.get("/api/imports", headers=_auth(manager))
    assert listing.status_code == 200


async def test_name_only_match_creates_a_candidate_and_merge_combines_students(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token = await _token(app_client, MANAGER)
    async with db_session_factory() as session:
        existing = Student(
            first_name="Asha",
            last_name="Rao",
            email_normalised="asha.existing@example.com",
            phone_e164="+919876500002",
        )
        session.add(existing)
        await session.commit()
        existing_id = existing.id

    content = single_row_csv(
        **{
            "Full Name": "Asha Rao",
            "Email": "asha.new@example.com",
            "Phone": "+919876500001",
        }
    )
    job = await _upload(app_client, token, content=content)
    result = await _map(app_client, token, job["id"])
    assert result["created_count"] == 1

    async with db_session_factory() as session:
        candidate = (
            await session.execute(
                select(DuplicateCandidate).where(
                    DuplicateCandidate.reason == "name_only",
                )
            )
        ).scalar_one()
        candidate_id = candidate.id
        assert candidate.student_id == existing_id
        assert candidate.candidate_student_id is not None
        assert candidate.status == "pending"

    response = await app_client.post(
        f"/api/duplicates/{candidate_id}/resolve",
        headers=_auth(token),
        json={"action": "merge"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "resolved"
    assert response.json()["resolution"] == "merged"

    async with db_session_factory() as session:
        students = (await session.execute(select(Student))).scalars().all()
        leads = (await session.execute(select(Lead))).scalars().all()
        assert len(students) == 1
        assert students[0].id == existing_id
        assert len(leads) == 1
        assert leads[0].student_id == existing_id


async def test_conflicting_contacts_create_a_candidate_and_are_not_merged(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token = await _token(app_client, MANAGER)
    async with db_session_factory() as session:
        email_owner = Student(
            first_name="Email",
            last_name="Owner",
            email_normalised="email.owner@example.com",
            phone_e164="+919876500003",
        )
        phone_owner = Student(
            first_name="Phone",
            last_name="Owner",
            email_normalised="phone.owner@example.com",
            phone_e164="+919876500004",
        )
        session.add_all([email_owner, phone_owner])
        await session.commit()
        email_owner_id = email_owner.id
        phone_owner_id = phone_owner.id

    content = single_row_csv(
        **{
            "Full Name": "Conflict Row",
            "Email": "email.owner@example.com",
            "Phone": "+919876500004",
        }
    )
    job = await _upload(app_client, token, content=content)
    result = await _map(app_client, token, job["id"])
    assert result["rejected_count"] == 1

    listing = await app_client.get("/api/duplicates", headers=_auth(token))
    assert listing.status_code == 200, listing.text
    candidates = listing.json()
    assert len(candidates) == 1
    assert candidates[0]["reason"] == "conflicting_contact"
    assert candidates[0]["student_id"] == str(email_owner_id)
    assert candidates[0]["conflicting_student_id"] == str(phone_owner_id)

    response = await app_client.post(
        f"/api/duplicates/{candidates[0]['id']}/resolve",
        headers=_auth(token),
        json={"action": "keep_separate"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["resolution"] == "kept_separate"


async def test_existing_non_empty_contact_is_not_overwritten(
    seeded_database: None,
    app_client: AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token = await _token(app_client, MANAGER)
    async with db_session_factory() as session:
        existing = Student(
            first_name="Old",
            last_name="Contact",
            email_normalised="old.contact@example.com",
            phone_e164="+919876500005",
        )
        session.add(existing)
        await session.commit()
        existing_id = existing.id

    content = single_row_csv(
        **{
            "Full Name": "Old Contact",
            "Email": "different.contact@example.com",
            "Phone": "+919876500005",
        }
    )
    job = await _upload(app_client, token, content=content)
    result = await _map(app_client, token, job["id"])
    assert result["merged_count"] == 1

    async with db_session_factory() as session:
        student = await session.get(Student, existing_id)
        assert student is not None
        assert student.email_normalised == "old.contact@example.com"
