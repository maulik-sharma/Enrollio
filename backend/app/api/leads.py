"""Lead list, detail, manual CRUD, and bulk import endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentUserDep,
    SessionDep,
    SettingsDep,
    require_any_permission,
    require_permission,
)
from app.core.domain import LifecycleStatus
from app.core.normalisation import (
    NormalisationError,
    normalise_email,
    normalise_name,
    normalise_phone,
)
from app.core.permissions import PermissionName, user_has_permission
from app.integrations.storage.factory import build_storage
from app.models.lead import Lead
from app.models.user import User
from app.repositories import catalogues as catalogues_repo
from app.repositories import users as users_repo
from app.schemas.consent import ConsentRecordRead
from app.schemas.imports import ImportJobRead
from app.schemas.leads import (
    LeadCreateRead,
    LeadCreateRequest,
    LeadDetailRead,
    LeadListRead,
    LeadRead,
    LeadUpdateRequest,
    StudentRead,
)
from app.services import consent as consent_service
from app.services import imports as imports_service
from app.services import leads as leads_service
from app.services.import_parsing import ImportFileError
from app.services.imports import ImportDispatchError

router = APIRouter(prefix="/api/leads", tags=["leads"])
LeadReadDependency = Depends(
    require_any_permission(PermissionName.LEADS_VIEW_ALL, PermissionName.LEADS_VIEW_ASSIGNED)
)


@router.post(
    "/import",
    response_model=ImportJobRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(PermissionName.LEADS_VIEW_ALL))],
)
async def upload_leads(
    session: SessionDep,
    settings: SettingsDep,
    user: CurrentUserDep,
    file: Annotated[UploadFile, File()],
    source_name: Annotated[str | None, Form()] = None,
) -> ImportJobRead:
    """Upload a CSV/XLSX file and return its detected columns."""
    data = await file.read(settings.IMPORT_MAX_FILE_BYTES + 1)
    try:
        job = await imports_service.create_import_job(
            session,
            settings,
            build_storage(settings),
            filename=file.filename or "upload.csv",
            data=data,
            source_name=source_name,
            uploaded_by_id=user.id,
        )
    except ImportFileError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ImportDispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return ImportJobRead.model_validate(job)


@router.get("", response_model=LeadListRead, dependencies=[LeadReadDependency])
async def list_leads(
    session: SessionDep,
    user: CurrentUserDep,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[
        int, Query(ge=1, le=leads_service.MAX_LIST_LIMIT)
    ] = leads_service.DEFAULT_LIST_LIMIT,
    sort: Literal["created_at", "-created_at", "updated_at", "-updated_at"] = "created_at",
    lifecycle_status: LifecycleStatus | None = None,
    programme_id: uuid.UUID | None = None,
    source_id: uuid.UUID | None = None,
    campus_id: uuid.UUID | None = None,
    assigned_counsellor_id: uuid.UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> LeadListRead:
    """Return a stable cursor-paginated, scoped lead list."""
    try:
        page = await leads_service.list_leads(
            session,
            user,
            cursor=cursor,
            limit=limit,
            sort=sort,
            lifecycle_status=lifecycle_status,
            programme_id=programme_id,
            source_id=source_id,
            campus_id=campus_id,
            assigned_counsellor_id=assigned_counsellor_id,
            created_from=created_from,
            created_to=created_to,
        )
    except leads_service.InvalidCursor as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_cursor",
        ) from exc
    return LeadListRead(
        items=[LeadRead.model_validate(lead) for lead in page.items],
        next_cursor=page.next_cursor,
    )


@router.post(
    "",
    response_model=LeadCreateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[LeadReadDependency],
)
async def create_lead(
    payload: LeadCreateRequest,
    session: SessionDep,
    user: CurrentUserDep,
    response: Response,
) -> LeadCreateRead:
    """Create a lead manually, applying the import dedupe rules."""
    try:
        email = normalise_email(payload.email) if payload.email else None
        phone = normalise_phone(payload.phone) if payload.phone else None
        first_name = normalise_name(payload.first_name)
        last_name = normalise_name(payload.last_name) if payload.last_name.strip() else ""
    except NormalisationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.code,
        ) from exc

    if email is None and phone is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="contact_required",
        )
    await _validate_catalogues(
        session,
        payload.programme_id,
        payload.campus_id,
        payload.source_id,
    )
    assigned = await _resolve_assignee(
        session,
        user,
        payload.assigned_counsellor_id,
        default_self=not user_has_permission(user, PermissionName.LEADS_VIEW_ALL),
    )

    try:
        result = await leads_service.create_or_get_lead(
            session,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            programme_id=payload.programme_id,
            campus_id=payload.campus_id,
            source_id=payload.source_id,
            admission_cycle=payload.admission_cycle or _default_cycle(),
            academic_score=payload.academic_score,
            graduation_year=payload.graduation_year,
        )
    except leads_service.ConflictingContacts as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "conflicting_contact",
                "student_id": str(exc.student_id),
                "conflicting_student_id": str(exc.conflicting_student_id),
            },
        ) from exc
    except leads_service.ContactAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="contact_already_exists",
        ) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="contact_already_exists",
        ) from exc

    if assigned is not None:
        result.lead.assigned_counsellor_id = assigned
    await session.commit()
    await session.refresh(result.lead)

    if result.duplicate_detected:
        response.status_code = status.HTTP_200_OK
    return LeadCreateRead(
        **LeadRead.model_validate(result.lead).model_dump(),
        duplicate_detected=result.duplicate_detected,
    )


@router.get("/{lead_id}", response_model=LeadDetailRead, dependencies=[LeadReadDependency])
async def get_lead(
    lead_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUserDep,
) -> LeadDetailRead:
    """Return a lead, its student, and consent summary."""
    try:
        lead, student = await leads_service.get_lead(session, lead_id)
    except leads_service.LeadNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found") from exc
    if not _can_access(user, lead):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    records = await consent_service.consent_summary(session, student_id=student.id)
    return LeadDetailRead(
        lead=LeadRead.model_validate(lead),
        student=StudentRead.model_validate(student),
        consent_summary=[ConsentRecordRead.model_validate(record) for record in records],
        assessments=[],
    )


@router.patch("/{lead_id}", response_model=LeadRead, dependencies=[LeadReadDependency])
async def update_lead(
    lead_id: uuid.UUID,
    payload: LeadUpdateRequest,
    session: SessionDep,
    user: CurrentUserDep,
) -> LeadRead:
    """Edit lead or student fields; lifecycle changes use the lifecycle service."""
    try:
        lead, student = await leads_service.get_lead(session, lead_id)
    except leads_service.LeadNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found") from exc
    if not _can_access(user, lead):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    changes = payload.model_dump(exclude_unset=True)
    if "assigned_counsellor_id" in changes:
        changes["assigned_counsellor_id"] = await _resolve_assignee(
            session,
            user,
            payload.assigned_counsellor_id,
            default_self=False,
        )
    await _validate_catalogues(
        session,
        changes.get("programme_id"),
        changes.get("campus_id"),
        changes.get("source_id"),
    )
    try:
        lead, _ = await leads_service.update_lead(session, lead, student, changes)
    except leads_service.ContactAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="contact_already_exists",
        ) from exc
    except leads_service.ContactRequired as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="contact_required",
        ) from exc
    except NormalisationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.code,
        ) from exc
    return LeadRead.model_validate(lead)


def _can_access(user: User, lead: Lead) -> bool:
    if user_has_permission(user, PermissionName.LEADS_VIEW_ALL):
        return True
    return bool(
        user_has_permission(user, PermissionName.LEADS_VIEW_ASSIGNED)
        and lead.assigned_counsellor_id == user.id
    )


async def _resolve_assignee(
    session: AsyncSession,
    user: User,
    requested: uuid.UUID | None,
    *,
    default_self: bool,
) -> uuid.UUID | None:
    if requested is None:
        return user.id if default_self else None
    if not user_has_permission(user, PermissionName.LEADS_ASSIGN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    assignee = await users_repo.get_with_permissions(session, requested)
    if assignee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="counsellor_not_found")
    return assignee.id


async def _validate_catalogues(
    session: AsyncSession,
    programme_id: uuid.UUID | None,
    campus_id: uuid.UUID | None,
    source_id: uuid.UUID | None,
) -> None:
    checks = (
        (programme_id, catalogues_repo.get_programme_by_id, "programme_not_found"),
        (campus_id, catalogues_repo.get_campus_by_id, "campus_not_found"),
        (source_id, catalogues_repo.get_source_by_id, "source_not_found"),
    )
    for value, loader, detail in checks:
        if value is not None and await loader(session, value) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _default_cycle() -> str:
    return f"{datetime.now(UTC).year}-fall"
