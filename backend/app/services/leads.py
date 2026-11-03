"""Lead CRUD, scoped listing, and cursor pagination."""

from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain import (
    DuplicateMatchReason,
    LifecycleStatus,
)
from app.core.normalisation import (
    NormalisationError,
    normalise_email,
    normalise_name,
    normalise_phone,
)
from app.core.permissions import PermissionName, user_has_permission
from app.models.lead import Lead
from app.models.student import Student
from app.models.user import User
from app.repositories import duplicates as duplicates_repo
from app.repositories import leads as leads_repo
from app.repositories import students as students_repo
from app.services.deduplication import MatchKind, decide_match

DEFAULT_LIST_LIMIT = 25
MAX_LIST_LIMIT = 100


class LeadNotFound(Exception):
    """No lead has the requested id."""


class ConflictingContacts(Exception):
    """Email and phone point at different existing students."""

    def __init__(self, student_id: uuid.UUID, conflicting_student_id: uuid.UUID) -> None:
        self.student_id = student_id
        self.conflicting_student_id = conflicting_student_id
        super().__init__("Email and phone belong to different students")


class ContactAlreadyExists(Exception):
    """A contact key already belongs to another student."""


class ContactRequired(Exception):
    """A student must keep at least one contact key."""


class InvalidCursor(Exception):
    """The pagination cursor is malformed or for another sort order."""


@dataclass(frozen=True)
class LeadPage:
    items: list[Lead]
    next_cursor: str | None


@dataclass(frozen=True)
class LeadCreation:
    lead: Lead
    student: Student
    duplicate_detected: bool
    student_was_existing: bool


async def list_leads(
    session: AsyncSession,
    user: User,
    *,
    cursor: str | None,
    limit: int,
    sort: str,
    search: str | None,
    lifecycle_status: LifecycleStatus | None,
    programme_id: uuid.UUID | None,
    source_id: uuid.UUID | None,
    campus_id: uuid.UUID | None,
    assigned_counsellor_id: uuid.UUID | None,
    created_from: datetime | None,
    created_to: datetime | None,
) -> LeadPage:
    """Return one scoped, filtered, stable page."""
    sort_field, descending = _parse_sort(sort)
    after = decode_cursor(cursor, sort_field=sort_field) if cursor else None
    scope: uuid.UUID | None = None
    if not user_has_permission(user, PermissionName.LEADS_VIEW_ALL):
        scope = user.id

    rows = await leads_repo.list_page(
        session,
        scoped_counsellor_id=scope,
        search=search,
        lifecycle_status=lifecycle_status,
        programme_id=programme_id,
        source_id=source_id,
        campus_id=campus_id,
        assigned_counsellor_id=assigned_counsellor_id,
        created_from=created_from,
        created_to=created_to,
        sort_field=sort_field,
        descending=descending,
        after=after,
        limit=limit + 1,
    )
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = encode_cursor(items[-1], sort_field=sort_field) if has_more and items else None
    return LeadPage(items=items, next_cursor=next_cursor)


async def get_lead(session: AsyncSession, lead_id: uuid.UUID) -> tuple[Lead, Student]:
    """Return a lead and its student or raise ``LeadNotFound``."""
    lead = await leads_repo.get(session, lead_id)
    if lead is None:
        raise LeadNotFound
    student = await students_repo.get(session, lead.student_id)
    if student is None:
        raise LeadNotFound
    return lead, student


async def create_or_get_lead(
    session: AsyncSession,
    *,
    first_name: str,
    last_name: str,
    email: str | None,
    phone: str | None,
    programme_id: uuid.UUID | None,
    campus_id: uuid.UUID | None,
    source_id: uuid.UUID | None,
    admission_cycle: str,
    academic_score: Decimal | None = None,
    graduation_year: int | None = None,
    import_job_id: uuid.UUID | None = None,
    row_number: int | None = None,
    raw_row: dict[str, object] | None = None,
) -> LeadCreation:
    """Apply the import dedupe rules to a manually entered lead."""
    by_email = await students_repo.get_by_email(session, email) if email else None
    by_phone = await students_repo.get_by_phone(session, phone) if phone else None
    name_match = None
    if by_email is None and by_phone is None:
        name_match = await students_repo.find_by_name(
            session,
            first_name=first_name,
            last_name=last_name,
        )

    decision = decide_match(
        email_student_id=by_email.id if by_email is not None else None,
        phone_student_id=by_phone.id if by_phone is not None else None,
        name_student_id=name_match.id if name_match is not None else None,
    )
    if decision.kind is MatchKind.CONFLICTING_CONTACT:
        assert decision.student_id is not None and decision.conflicting_student_id is not None
        raise ConflictingContacts(decision.student_id, decision.conflicting_student_id)

    existing = by_email or by_phone
    student_was_existing = existing is not None
    if existing is None:
        student = Student(
            first_name=first_name,
            last_name=last_name,
            email_normalised=email,
            phone_e164=phone,
            academic_score=academic_score,
            graduation_year=graduation_year,
        )
        session.add(student)
        await session.flush()
    else:
        student = existing
        _fill_empty_student_fields(
            student,
            last_name,
            email,
            phone,
            academic_score,
            graduation_year,
        )
        await session.flush()

    if decision.kind is MatchKind.NAME_ONLY and decision.student_id is not None:
        await duplicates_repo.create_candidate(
            session,
            student_id=decision.student_id,
            candidate_student_id=student.id,
            reason=DuplicateMatchReason.NAME_ONLY,
            import_job_id=import_job_id,
            row_number=row_number,
            raw_row=raw_row,
        )

    lead = await leads_repo.find_for_enquiry(
        session,
        student_id=student.id,
        programme_id=programme_id,
        admission_cycle=admission_cycle,
    )
    if lead is not None:
        return LeadCreation(
            lead=lead,
            student=student,
            duplicate_detected=True,
            student_was_existing=student_was_existing,
        )

    lead = Lead(
        student_id=student.id,
        programme_id=programme_id,
        campus_id=campus_id,
        source_id=source_id,
        admission_cycle=admission_cycle,
        import_job_id=import_job_id,
        raw_import_row=raw_row,
    )
    session.add(lead)
    await session.flush()
    return LeadCreation(
        lead=lead,
        student=student,
        duplicate_detected=False,
        student_was_existing=student_was_existing,
    )


async def update_lead(
    session: AsyncSession,
    lead: Lead,
    student: Student,
    changes: dict[str, object],
) -> tuple[Lead, Student]:
    """Apply supported lead/student changes; lifecycle is not editable here."""
    first_name = _optional_str(changes, "first_name")
    last_name = _optional_str(changes, "last_name")
    if first_name is not None:
        student.first_name = normalise_name(first_name)
    if last_name is not None:
        student.last_name = "" if not last_name.strip() else normalise_name(last_name)

    if "email" in changes:
        email = _normalise_optional_contact(changes["email"], normalise_email)
        if email is not None:
            other = await students_repo.get_by_email(session, email)
            if other is not None and other.id != student.id:
                raise ContactAlreadyExists
        student.email_normalised = email
    if "phone" in changes:
        phone = _normalise_optional_contact(changes["phone"], normalise_phone)
        if phone is not None:
            other = await students_repo.get_by_phone(session, phone)
            if other is not None and other.id != student.id:
                raise ContactAlreadyExists
        student.phone_e164 = phone
    if student.email_normalised is None and student.phone_e164 is None:
        raise ContactRequired

    if "academic_score" in changes:
        score = changes["academic_score"]
        student.academic_score = score if isinstance(score, Decimal) else None
    if "graduation_year" in changes:
        year = changes["graduation_year"]
        student.graduation_year = year if isinstance(year, int) else None
    if "date_of_birth" in changes:
        dob = changes["date_of_birth"]
        student.date_of_birth = dob if isinstance(dob, _DATE_TYPES) else None

    for field in ("programme_id", "campus_id", "source_id", "assigned_counsellor_id"):
        if field in changes:
            value = changes[field]
            setattr(lead, field, value if isinstance(value, uuid.UUID) else None)
    if "admission_cycle" in changes and isinstance(changes["admission_cycle"], str):
        lead.admission_cycle = changes["admission_cycle"]

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ContactAlreadyExists from exc
    await session.refresh(lead)
    await session.refresh(student)
    return lead, student


def encode_cursor(lead: Lead, *, sort_field: str) -> str:
    """Encode the ordering key of ``lead`` for the next page."""
    value: datetime = getattr(lead, sort_field)
    payload = {"s": sort_field, "v": value.isoformat(), "id": str(lead.id)}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str, *, sort_field: str) -> tuple[datetime, uuid.UUID]:
    """Decode and validate a pagination cursor."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        if payload["s"] != sort_field:
            raise ValueError
        value = datetime.fromisoformat(payload["v"])
        if value.tzinfo is None:
            raise ValueError
        return value, uuid.UUID(payload["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidCursor from exc


def _parse_sort(sort: str) -> tuple[Literal["created_at", "updated_at"], bool]:
    descending = sort.startswith("-")
    field = sort.lstrip("-")
    if field not in {"created_at", "updated_at"}:
        raise ValueError("Unsupported sort field")
    return field, descending  # type: ignore[return-value]


def _normalise_optional_contact(
    value: object,
    normaliser: Callable[[str], str],
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise NormalisationError("Contact must be text")
    if not value.strip():
        return None
    return normaliser(value)


def _optional_str(changes: dict[str, object], field: str) -> str | None:
    value = changes.get(field)
    return value if isinstance(value, str) else None


def _fill_empty_student_fields(
    student: Student,
    last_name: str,
    email: str | None,
    phone: str | None,
    academic_score: Decimal | None,
    graduation_year: int | None,
) -> None:
    if student.email_normalised is None and email is not None:
        student.email_normalised = email
    if student.phone_e164 is None and phone is not None:
        student.phone_e164 = phone
    if student.academic_score is None and academic_score is not None:
        student.academic_score = academic_score
    if student.graduation_year is None and graduation_year is not None:
        student.graduation_year = graduation_year
    if not student.last_name and last_name:
        student.last_name = last_name


_DATE_TYPES = (date, datetime)
