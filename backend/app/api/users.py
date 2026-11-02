"""User administration endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import SessionDep, SettingsDep, require_permission
from app.core.permissions import PermissionName
from app.schemas.users import UserCreate, UserRead, UserUpdate
from app.services import users as users_service
from app.services.users import EmailAlreadyExists, UnknownRole, UserNotFound

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    dependencies=[Depends(require_permission(PermissionName.USERS_MANAGE))],
)


@router.get("", response_model=list[UserRead])
async def list_users(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[UserRead]:
    """List staff accounts with their roles."""
    users = await users_service.list_users(session, limit=limit, offset=offset)
    return [UserRead.model_validate(user) for user in users]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    session: SessionDep,
    settings: SettingsDep,
) -> UserRead:
    """Create an active user and assign roles."""
    try:
        user = await users_service.create_user(
            session,
            settings,
            email=str(payload.email),
            full_name=payload.full_name,
            password=payload.password,
            role_slugs=payload.roles,
        )
    except EmailAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        ) from exc
    except UnknownRole as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    session: SessionDep,
    settings: SettingsDep,
) -> UserRead:
    """Update profile fields, roles, password, or active state."""
    try:
        user = await users_service.update_user(
            session,
            user_id=user_id,
            settings=settings,
            full_name=payload.full_name,
            password=payload.password,
            is_active=payload.is_active,
            role_slugs=payload.roles,
        )
    except UserNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc
    except UnknownRole as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return UserRead.model_validate(user)


@router.post("/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(user_id: uuid.UUID, session: SessionDep) -> UserRead:
    """Deactivate a user and revoke their sessions."""
    try:
        user = await users_service.deactivate_user(session, user_id)
    except UserNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from exc

    return UserRead.model_validate(user)
