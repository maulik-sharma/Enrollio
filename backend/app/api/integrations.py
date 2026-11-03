"""Authenticated partner integration endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from app.api.deps import SessionDep, SettingsDep, require_permission
from app.core.domain import ImportRowStatus
from app.core.permissions import PermissionName
from app.models.api_key import ApiKey
from app.models.user import User
from app.repositories import catalogues as catalogues_repo
from app.schemas.integrations import (
    ApiKeyCreatedRead,
    ApiKeyCreateRequest,
    IngestBatchRead,
    IngestRecordRead,
)
from app.services import api_ingestion as ingestion_service
from app.services import api_keys as api_keys_service

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

INTEGRATIONS_MANAGE = PermissionName.INTEGRATIONS_MANAGE


def _api_key_from_request(request: Request) -> str | None:
    direct = request.headers.get("X-API-Key")
    if direct and direct.strip():
        return direct.strip()
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return None


async def get_api_key(
    request: Request,
    session: SessionDep,
) -> ApiKey:
    """Authenticate a partner request by its source-scoped API key."""
    presented = _api_key_from_request(request)
    if presented is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    api_key = await api_keys_service.authenticate_api_key(session, presented)
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key


ApiKeyDep = Annotated[ApiKey, Depends(get_api_key)]


@router.post(
    "/api-keys",
    response_model=ApiKeyCreatedRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    payload: ApiKeyCreateRequest,
    session: SessionDep,
    user: Annotated[User, Depends(require_permission(INTEGRATIONS_MANAGE))],
) -> ApiKeyCreatedRead:
    """Provision a one-time key for one lead source (admin only)."""
    source_id = payload.source_id
    if source_id is None and payload.source:
        source = await catalogues_repo.get_source(session, payload.source)
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="source_not_found",
            )
        source_id = source.id
    if source_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="source_required",
        )

    try:
        created = await api_keys_service.create_api_key(
            session,
            name=payload.name,
            source_id=source_id,
            created_by_id=user.id,
            expires_at=payload.expires_at,
        )
    except api_keys_service.ApiKeySourceNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="source_not_found",
        ) from exc

    return ApiKeyCreatedRead(
        id=created.api_key.id,
        name=created.api_key.name,
        source_id=created.api_key.source_id,
        key_prefix=created.api_key.key_prefix,
        key=created.plaintext,
        api_key=created.plaintext,
        expires_at=created.api_key.expires_at,
        created_at=created.api_key.created_at,
    )


@router.post("/leads", response_model=IngestBatchRead)
async def ingest_leads(
    api_key: ApiKeyDep,
    session: SessionDep,
    settings: SettingsDep,
    payload: Annotated[Any, Body()],
) -> IngestBatchRead:
    """Accept a JSON array of canonical leads, independently validated."""
    records = _batch_records(payload)
    try:
        results = await ingestion_service.ingest_batch(
            session,
            source_id=api_key.source_id,
            records=records,
            max_records=settings.API_INGESTION_MAX_RECORDS,
        )
    except ingestion_service.EmptyBatch as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="empty_batch",
        ) from exc
    except ingestion_service.BatchTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="batch_too_large",
        ) from exc

    counts = {outcome: 0 for outcome in ImportRowStatus}
    for result in results:
        counts[result.status] += 1

    return IngestBatchRead(
        total=len(results),
        created=counts[ImportRowStatus.CREATED],
        merged=counts[ImportRowStatus.MERGED],
        duplicate=counts[ImportRowStatus.DUPLICATE],
        rejected=counts[ImportRowStatus.REJECTED],
        results=[
            IngestRecordRead(
                index=result.index,
                row_number=result.row_number,
                status=result.status,
                student_id=result.student_id,
                lead_id=result.lead_id,
                reason=result.reason,
                message=result.message,
            )
            for result in results
        ],
    )


def _batch_records(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("leads", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="expected_json_array",
    )
