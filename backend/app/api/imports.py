"""Import job, mapping, history, and error-report endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import CurrentUserDep, SessionDep, SettingsDep, require_permission
from app.core.permissions import PermissionName
from app.integrations.storage.factory import build_storage
from app.repositories import imports as imports_repo
from app.schemas.imports import ImportJobRead, ImportMappingRequest, MappingTemplateRead
from app.services import imports as imports_service
from app.services.import_parsing import ImportMappingError
from app.services.imports import (
    ImportDispatchError,
    ImportJobNotFound,
    ImportJobNotPending,
    errors_as_csv,
)

router = APIRouter(
    prefix="/api/imports",
    tags=["imports"],
    dependencies=[Depends(require_permission(PermissionName.LEADS_VIEW_ALL))],
)


@router.get("", response_model=list[ImportJobRead])
async def list_imports(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ImportJobRead]:
    """Return import history with counts, newest first."""
    jobs = await imports_service.list_jobs(session, limit=limit, offset=offset)
    return [ImportJobRead.model_validate(job) for job in jobs]


@router.get("/mapping-template", response_model=MappingTemplateRead)
async def get_mapping_template(session: SessionDep, source_name: str) -> MappingTemplateRead:
    """Return the saved mapping for a source, if one exists."""
    template = await imports_repo.get_mapping_template(session, source_name)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return MappingTemplateRead.model_validate(template)


@router.get("/{job_id}", response_model=ImportJobRead)
async def get_import(job_id: uuid.UUID, session: SessionDep) -> ImportJobRead:
    """Return one import job and its counts."""
    try:
        job = await imports_service.get_job(session, job_id)
    except ImportJobNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found",
        ) from exc
    return ImportJobRead.model_validate(job)


@router.post("/{job_id}/mapping", response_model=ImportJobRead)
async def set_mapping(
    job_id: uuid.UUID,
    payload: ImportMappingRequest,
    session: SessionDep,
    settings: SettingsDep,
    user: CurrentUserDep,
) -> ImportJobRead:
    """Save a reusable mapping and start processing."""
    try:
        job = await imports_service.set_mapping_and_start(
            session,
            settings,
            build_storage(settings),
            job_id=job_id,
            mapping=payload.mapping,
            created_by_id=user.id,
        )
    except ImportJobNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found",
        ) from exc
    except ImportJobNotPending as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This import is already processing or complete",
        ) from exc
    except ImportMappingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ImportDispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return ImportJobRead.model_validate(job)


@router.get("/{job_id}/errors.csv")
async def download_errors(job_id: uuid.UUID, session: SessionDep) -> Response:
    """Download rejected rows as ``row_number,reason`` CSV."""
    try:
        results = await imports_service.get_errors(session, job_id)
    except ImportJobNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found",
        ) from exc

    return Response(
        content=errors_as_csv(results),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="import-{job_id}-errors.csv"',
        },
    )
