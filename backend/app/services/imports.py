"""CSV/XLSX import: upload, column mapping, processing, and error reports."""

from __future__ import annotations

import csv
import uuid
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import ImportProcessingMode, Settings
from app.core.domain import (
    DuplicateMatchReason,
    ImportJobStatus,
    ImportRowStatus,
)
from app.integrations.storage.base import Storage, StorageError
from app.models.import_job import ImportJob, ImportRowResult
from app.models.lead import Lead
from app.models.student import Student
from app.repositories import catalogues as catalogues_repo
from app.repositories import duplicates as duplicates_repo
from app.repositories import imports as imports_repo
from app.repositories import leads as leads_repo
from app.repositories import students as students_repo
from app.services.deduplication import MatchKind, decide_match
from app.services.import_parsing import (
    ImportFileError,
    ImportRowError,
    ValidatedImportRow,
    parse_import_file,
    validate_import_row,
    validate_mapping,
)

MAX_SOURCE_NAME_LENGTH = 100
MAX_FILENAME_LENGTH = 255


class ImportJobNotFound(Exception):
    """No import job has the requested id."""


class ImportJobNotPending(Exception):
    """The job is no longer waiting for a mapping."""


class ImportDispatchError(Exception):
    """The background task could not be queued."""


class DuplicateReviewRequired(ImportRowError):
    """The row's email and phone point at different existing students."""

    def __init__(
        self,
        student_id: uuid.UUID,
        conflicting_student_id: uuid.UUID,
    ) -> None:
        self.student_id = student_id
        self.conflicting_student_id = conflicting_student_id
        super().__init__(
            "conflicting_contact",
            "Email and phone belong to different students",
        )


@dataclass(frozen=True)
class RowOutcome:
    status: ImportRowStatus
    student_id: uuid.UUID
    lead_id: uuid.UUID


async def create_import_job(
    session: AsyncSession,
    settings: Settings,
    storage: Storage,
    *,
    filename: str,
    data: bytes,
    source_name: str | None,
    uploaded_by_id: uuid.UUID | None,
) -> ImportJob:
    """Parse an upload, store the original file, and create an ``uploaded`` job."""
    safe_filename = Path(filename).name
    if not safe_filename:
        raise ImportFileError("invalid_filename", "A filename is required")
    if len(safe_filename) > MAX_FILENAME_LENGTH:
        raise ImportFileError("invalid_filename", "The filename is longer than 255 characters")

    parsed = parse_import_file(
        safe_filename,
        data,
        max_rows=settings.IMPORT_MAX_ROWS,
        max_bytes=settings.IMPORT_MAX_FILE_BYTES,
    )

    cleaned_source = _source_name(source_name, safe_filename)
    storage_key = f"imports/{uuid.uuid4()}/{safe_filename}"
    try:
        storage.save(storage_key, data)
    except StorageError as exc:
        raise ImportDispatchError("The uploaded file could not be stored") from exc

    job = ImportJob(
        source_name=cleaned_source,
        original_filename=safe_filename,
        storage_key=storage_key,
        file_type=parsed.file_type,
        status=ImportJobStatus.UPLOADED,
        headers=parsed.headers,
        total_rows=len(parsed.rows),
        uploaded_by_id=uploaded_by_id,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def set_mapping_and_start(
    session: AsyncSession,
    settings: Settings,
    storage: Storage,
    *,
    job_id: uuid.UUID,
    mapping: dict[str, str],
    created_by_id: uuid.UUID | None,
) -> ImportJob:
    """Save a reusable mapping and dispatch processing."""
    job = await imports_repo.get_job(session, job_id)
    if job is None:
        raise ImportJobNotFound
    if job.status is not ImportJobStatus.UPLOADED:
        raise ImportJobNotPending

    cleaned = validate_mapping(mapping, job.headers)
    await imports_repo.upsert_mapping_template(
        session,
        source_name=job.source_name,
        mapping=cleaned,
        created_by_id=created_by_id,
    )

    job.mapping = cleaned
    job.status = ImportJobStatus.PROCESSING
    job.error_message = None
    await session.commit()
    await session.refresh(job)

    if settings.IMPORT_PROCESSING_MODE is ImportProcessingMode.inline:
        return await process_import_job(session, settings, storage, job.id) or job

    try:
        from app.workers.imports import process_import

        process_import.delay(str(job.id))
    except Exception as exc:
        await _mark_failed(session, job.id, "The import task could not be queued")
        raise ImportDispatchError("The import task could not be queued") from exc

    return job


async def process_import_job(
    session: AsyncSession,
    settings: Settings,
    storage: Storage,
    job_id: uuid.UUID,
) -> ImportJob | None:
    """Validate every row, persist outcomes, and update job counts."""
    job = await imports_repo.get_job(session, job_id)
    if job is None:
        return None
    if job.status is ImportJobStatus.COMPLETED:
        return job

    job.status = ImportJobStatus.PROCESSING
    job.error_message = None
    await session.commit()

    try:
        data = storage.read(job.storage_key)
        parsed = parse_import_file(
            job.original_filename,
            data,
            max_rows=settings.IMPORT_MAX_ROWS,
            max_bytes=settings.IMPORT_MAX_FILE_BYTES,
        )
        mapping = job.mapping or {}
        default_source = await catalogues_repo.get_or_create_source(session, job.source_name)

        counts = {
            ImportRowStatus.CREATED: 0,
            ImportRowStatus.MERGED: 0,
            ImportRowStatus.REJECTED: 0,
            ImportRowStatus.DUPLICATE: 0,
        }

        for row_number, raw_row in parsed.rows:
            try:
                async with session.begin_nested():
                    outcome = await _process_row(
                        session,
                        raw_row=raw_row,
                        mapping=mapping,
                        job=job,
                        row_number=row_number,
                        default_source_id=default_source.id,
                    )
                    session.add(
                        ImportRowResult(
                            import_job_id=job.id,
                            row_number=row_number,
                            status=outcome.status,
                            student_id=outcome.student_id,
                            lead_id=outcome.lead_id,
                            raw_row=raw_row,
                        )
                    )
                counts[outcome.status] += 1
            except DuplicateReviewRequired as exc:
                await duplicates_repo.create_candidate(
                    session,
                    student_id=exc.student_id,
                    conflicting_student_id=exc.conflicting_student_id,
                    reason=DuplicateMatchReason.CONFLICTING_CONTACT,
                    import_job_id=job.id,
                    row_number=row_number,
                    raw_row=raw_row,
                )
                session.add(
                    ImportRowResult(
                        import_job_id=job.id,
                        row_number=row_number,
                        status=ImportRowStatus.REJECTED,
                        reason=exc.code,
                        message=str(exc),
                        raw_row=raw_row,
                    )
                )
                counts[ImportRowStatus.REJECTED] += 1
            except ImportRowError as exc:
                session.add(
                    ImportRowResult(
                        import_job_id=job.id,
                        row_number=row_number,
                        status=ImportRowStatus.REJECTED,
                        reason=exc.code,
                        message=str(exc),
                        raw_row=raw_row,
                    )
                )
                counts[ImportRowStatus.REJECTED] += 1
            except IntegrityError:
                session.add(
                    ImportRowResult(
                        import_job_id=job.id,
                        row_number=row_number,
                        status=ImportRowStatus.REJECTED,
                        reason="duplicate_contact",
                        message="A concurrent import created the same contact",
                        raw_row=raw_row,
                    )
                )
                counts[ImportRowStatus.REJECTED] += 1

        job.total_rows = len(parsed.rows)
        job.created_count = counts[ImportRowStatus.CREATED]
        job.merged_count = counts[ImportRowStatus.MERGED]
        job.rejected_count = counts[ImportRowStatus.REJECTED]
        job.duplicate_count = counts[ImportRowStatus.DUPLICATE]
        job.status = ImportJobStatus.COMPLETED
        await session.commit()
        await session.refresh(job)
        return job
    except Exception:
        await session.rollback()
        await _mark_failed(session, job_id, "Import processing failed")
        failed = await imports_repo.get_job(session, job_id)
        if failed is not None:
            await session.refresh(failed)
        return failed


async def list_jobs(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[ImportJob]:
    """Return import history."""
    return await imports_repo.list_jobs(session, limit=limit, offset=offset)


async def get_job(session: AsyncSession, job_id: uuid.UUID) -> ImportJob:
    """Return one job or raise a domain not-found error."""
    job = await imports_repo.get_job(session, job_id)
    if job is None:
        raise ImportJobNotFound
    return job


async def get_errors(session: AsyncSession, job_id: uuid.UUID) -> list[ImportRowResult]:
    """Return rejected rows for a job."""
    await get_job(session, job_id)
    return await imports_repo.get_errors(session, job_id)


def errors_as_csv(results: list[ImportRowResult]) -> str:
    """Render ``row_number,reason`` for the downloadable error report."""
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["row_number", "reason"])
    for result in results:
        writer.writerow([result.row_number, result.reason or "rejected"])
    return buffer.getvalue()


async def _process_row(
    session: AsyncSession,
    *,
    raw_row: dict[str, object],
    mapping: dict[str, str],
    job: ImportJob,
    row_number: int,
    default_source_id: uuid.UUID,
) -> RowOutcome:
    row = validate_import_row(raw_row, mapping)

    programme = None
    if row.programme is not None:
        programme = await catalogues_repo.get_programme(session, row.programme)
        if programme is None:
            raise ImportRowError("unknown_programme", f"Unknown programme: {row.programme}")

    campus = None
    if row.campus is not None:
        campus = await catalogues_repo.get_campus(session, row.campus)
        if campus is None:
            raise ImportRowError("unknown_campus", f"Unknown campus: {row.campus}")

    source = None
    if row.source is not None:
        source = await catalogues_repo.get_source(session, row.source)
        if source is None:
            raise ImportRowError("unknown_source", f"Unknown source: {row.source}")
    source_id = source.id if source is not None else default_source_id

    by_email = (
        await students_repo.get_by_email(session, row.email) if row.email is not None else None
    )
    by_phone = (
        await students_repo.get_by_phone(session, row.phone) if row.phone is not None else None
    )
    name_match = None
    if by_email is None and by_phone is None:
        name_match = await students_repo.find_by_name(
            session,
            first_name=row.first_name,
            last_name=row.last_name,
        )

    decision = decide_match(
        email_student_id=by_email.id if by_email is not None else None,
        phone_student_id=by_phone.id if by_phone is not None else None,
        name_student_id=name_match.id if name_match is not None else None,
    )
    if decision.kind is MatchKind.CONFLICTING_CONTACT:
        assert decision.student_id is not None and decision.conflicting_student_id is not None
        raise DuplicateReviewRequired(decision.student_id, decision.conflicting_student_id)

    existing = by_email or by_phone
    student, student_was_existing = await _resolve_student(session, row, existing)
    if decision.kind is MatchKind.NAME_ONLY and decision.student_id is not None:
        await duplicates_repo.create_candidate(
            session,
            student_id=decision.student_id,
            candidate_student_id=student.id,
            reason=DuplicateMatchReason.NAME_ONLY,
            import_job_id=job.id,
            row_number=row_number,
            raw_row=raw_row,
        )

    lead = await leads_repo.find_for_enquiry(
        session,
        student_id=student.id,
        programme_id=programme.id if programme is not None else None,
        admission_cycle=row.admission_cycle,
    )
    if lead is not None:
        return RowOutcome(
            status=ImportRowStatus.DUPLICATE,
            student_id=student.id,
            lead_id=lead.id,
        )

    lead = Lead(
        student_id=student.id,
        programme_id=programme.id if programme is not None else None,
        campus_id=campus.id if campus is not None else None,
        source_id=source_id,
        admission_cycle=row.admission_cycle,
        import_job_id=job.id,
        raw_import_row=raw_row,
    )
    session.add(lead)
    await session.flush()

    return RowOutcome(
        status=ImportRowStatus.MERGED if student_was_existing else ImportRowStatus.CREATED,
        student_id=student.id,
        lead_id=lead.id,
    )


async def _resolve_student(
    session: AsyncSession,
    row: ValidatedImportRow,
    existing: Student | None,
) -> tuple[Student, bool]:
    if existing is None:
        student = Student(
            first_name=row.first_name,
            last_name=row.last_name,
            email_normalised=row.email,
            phone_e164=row.phone,
            academic_score=row.score,
            graduation_year=row.graduation_year,
        )
        session.add(student)
        await session.flush()
        return student, False

    _fill_empty_student_fields(existing, row)
    await session.flush()
    return existing, True


def _fill_empty_student_fields(student: Student, row: ValidatedImportRow) -> None:
    if student.email_normalised is None and row.email is not None:
        student.email_normalised = row.email
    if student.phone_e164 is None and row.phone is not None:
        student.phone_e164 = row.phone
    if student.academic_score is None and row.score is not None:
        student.academic_score = row.score
    if student.graduation_year is None and row.graduation_year is not None:
        student.graduation_year = row.graduation_year
    if not student.last_name and row.last_name:
        student.last_name = row.last_name


async def _mark_failed(session: AsyncSession, job_id: uuid.UUID, message: str) -> None:
    job = await imports_repo.get_job(session, job_id)
    if job is None:
        return
    job.status = ImportJobStatus.FAILED
    job.error_message = message
    await session.commit()


def _source_name(source_name: str | None, filename: str) -> str:
    raw = (source_name or Path(filename).stem or "Import").strip()
    collapsed = " ".join(raw.split())
    if not collapsed:
        collapsed = "Import"
    if len(collapsed) > MAX_SOURCE_NAME_LENGTH:
        raise ImportFileError("invalid_source_name", "Source name is longer than 100 characters")
    return collapsed
