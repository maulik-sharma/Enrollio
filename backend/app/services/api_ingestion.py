"""Partner API batch ingestion with import-equivalent validation and dedupe."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain import DuplicateMatchReason, ImportRowStatus
from app.repositories import catalogues as catalogues_repo
from app.repositories import duplicates as duplicates_repo
from app.services import leads as leads_service
from app.services.import_parsing import ImportRowError, ValidatedImportRow, validate_import_row

_IDENTITY_MAPPING = {
    "name": "name",
    "email": "email",
    "phone": "phone",
    "course": "course",
    "score": "score",
    "graduation_year": "graduation_year",
    "campus": "campus",
    "admission_cycle": "admission_cycle",
}


class BatchTooLarge(Exception):
    """The request exceeds the configured per-request record limit."""


class EmptyBatch(Exception):
    """The request contains no records."""


class RecordError(Exception):
    """One record failed validation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class IngestRecordResult:
    index: int
    row_number: int
    status: ImportRowStatus
    student_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    reason: str | None = None
    message: str | None = None


async def ingest_batch(
    session: AsyncSession,
    *,
    source_id: uuid.UUID,
    records: list[object],
    max_records: int,
) -> list[IngestRecordResult]:
    """Process each record independently and return per-record outcomes."""
    if not records:
        raise EmptyBatch
    if len(records) > max_records:
        raise BatchTooLarge

    results: list[IngestRecordResult] = []
    for index, raw in enumerate(records):
        row_number = index + 1
        if not isinstance(raw, dict):
            results.append(
                IngestRecordResult(
                    index=index,
                    row_number=row_number,
                    status=ImportRowStatus.REJECTED,
                    reason="invalid_record",
                    message="Each record must be a JSON object",
                )
            )
            continue

        try:
            async with session.begin_nested():
                outcome = await _process_record(
                    session,
                    source_id=source_id,
                    raw=raw,
                    row_number=row_number,
                )
            results.append(
                IngestRecordResult(
                    index=index,
                    row_number=row_number,
                    status=outcome.status,
                    student_id=outcome.student_id,
                    lead_id=outcome.lead_id,
                )
            )
        except RecordError as exc:
            results.append(
                IngestRecordResult(
                    index=index,
                    row_number=row_number,
                    status=ImportRowStatus.REJECTED,
                    reason=exc.code,
                    message=str(exc),
                )
            )
        except leads_service.ConflictingContacts as exc:
            await duplicates_repo.create_candidate(
                session,
                student_id=exc.student_id,
                conflicting_student_id=exc.conflicting_student_id,
                reason=DuplicateMatchReason.CONFLICTING_CONTACT,
                row_number=row_number,
                raw_row=raw,
            )
            results.append(
                IngestRecordResult(
                    index=index,
                    row_number=row_number,
                    status=ImportRowStatus.REJECTED,
                    reason="conflicting_contact",
                    message="Email and phone belong to different students",
                )
            )
        except IntegrityError:
            results.append(
                IngestRecordResult(
                    index=index,
                    row_number=row_number,
                    status=ImportRowStatus.REJECTED,
                    reason="duplicate_contact",
                    message="A concurrent request created the same contact",
                )
            )

    await session.commit()
    return results


async def _process_record(
    session: AsyncSession,
    *,
    source_id: uuid.UUID,
    raw: dict[str, Any],
    row_number: int,
) -> IngestRecordResult:
    validated = _validate(raw)
    programme_id = await _resolve_programme(session, raw, validated)
    campus_id = await _resolve_campus(session, raw)

    created = await leads_service.create_or_get_lead(
        session,
        first_name=validated.first_name,
        last_name=validated.last_name,
        email=validated.email,
        phone=validated.phone,
        programme_id=programme_id,
        campus_id=campus_id,
        source_id=source_id,
        admission_cycle=validated.admission_cycle,
        academic_score=validated.score,
        graduation_year=validated.graduation_year,
        row_number=row_number,
        raw_row=raw,
    )

    if created.duplicate_detected:
        status = ImportRowStatus.DUPLICATE
    elif created.student_was_existing:
        status = ImportRowStatus.MERGED
    else:
        status = ImportRowStatus.CREATED
    return IngestRecordResult(
        index=row_number - 1,
        row_number=row_number,
        status=status,
        student_id=created.student.id,
        lead_id=created.lead.id,
    )


def _validate(raw: dict[str, Any]) -> ValidatedImportRow:
    name = _record_name(raw)
    programme_id = _optional_uuid(raw, "programme_id", "programme_id")
    campus_id = _optional_uuid(raw, "campus_id", "campus_id")
    mapped = {
        "name": name,
        "email": _first_present(raw, "email", "email_address"),
        "phone": _first_present(raw, "phone", "phone_number", "phone_e164"),
        "course": None
        if programme_id is not None
        else _first_present(raw, "programme", "course", "programme_code"),
        "score": _first_present(raw, "score", "academic_score"),
        "graduation_year": raw.get("graduation_year"),
        "campus": None if campus_id is not None else _first_present(raw, "campus", "campus_name"),
        "admission_cycle": raw.get("admission_cycle"),
    }
    try:
        return validate_import_row(mapped, _IDENTITY_MAPPING)
    except ImportRowError as exc:
        raise RecordError(exc.code, str(exc)) from exc


async def _resolve_programme(
    session: AsyncSession,
    raw: dict[str, Any],
    validated: ValidatedImportRow,
) -> uuid.UUID | None:
    programme_id = _optional_uuid(raw, "programme_id", "programme_id")
    if programme_id is not None:
        if await catalogues_repo.get_programme_by_id(session, programme_id) is None:
            raise RecordError("unknown_programme", f"Unknown programme: {programme_id}")
        return programme_id
    if validated.programme is None:
        return None
    programme = await catalogues_repo.get_programme(session, validated.programme)
    if programme is None:
        raise RecordError("unknown_programme", f"Unknown programme: {validated.programme}")
    return programme.id


async def _resolve_campus(
    session: AsyncSession,
    raw: dict[str, Any],
) -> uuid.UUID | None:
    campus_id = _optional_uuid(raw, "campus_id", "campus_id")
    if campus_id is not None:
        if await catalogues_repo.get_campus_by_id(session, campus_id) is None:
            raise RecordError("unknown_campus", f"Unknown campus: {campus_id}")
        return campus_id
    value = _first_present(raw, "campus", "campus_name")
    if value is None:
        return None
    campus = await catalogues_repo.get_campus(session, str(value))
    if campus is None:
        raise RecordError("unknown_campus", f"Unknown campus: {value}")
    return campus.id


def _optional_uuid(
    raw: dict[str, Any],
    field: str,
    code_field: str,
) -> uuid.UUID | None:
    value = raw.get(field)
    if value is None or str(value).strip() == "":
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise RecordError(f"invalid_{code_field}", f"{field} must be a UUID") from exc


def _first_present(raw: dict[str, Any], *keys: str) -> object:
    for key in keys:
        value = raw.get(key)
        if value is not None and str(value).strip() != "":
            return value
    return None


def _record_name(raw: dict[str, Any]) -> str:
    first = _text(raw.get("first_name"))
    last = _text(raw.get("last_name"))
    if first:
        return f"{first} {last}".strip()
    for key in ("name", "full_name"):
        value = _text(raw.get(key))
        if value:
            return value
    return ""


def _text(value: object) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)
