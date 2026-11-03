"""Read-only catalogue options for lead screens."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, require_any_permission
from app.core.permissions import PermissionName
from app.repositories import catalogues as catalogues_repo
from app.schemas.catalogues import (
    CampusOption,
    CatalogueRead,
    LeadSourceOption,
    ProgrammeOption,
)

router = APIRouter(
    prefix="/api/catalogues",
    tags=["catalogues"],
    dependencies=[
        Depends(
            require_any_permission(
                PermissionName.LEADS_VIEW_ALL,
                PermissionName.LEADS_VIEW_ASSIGNED,
            )
        )
    ],
)


@router.get("", response_model=CatalogueRead)
async def read_catalogues(session: SessionDep) -> CatalogueRead:
    """Return the active programmes, campuses, and sources."""
    programmes = await catalogues_repo.list_programmes(session)
    campuses = await catalogues_repo.list_campuses(session)
    sources = await catalogues_repo.list_sources(session)
    return CatalogueRead(
        programmes=[ProgrammeOption.model_validate(item) for item in programmes],
        campuses=[CampusOption.model_validate(item) for item in campuses],
        sources=[LeadSourceOption.model_validate(item) for item in sources],
    )
