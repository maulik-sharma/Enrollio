"""Shared FastAPI dependencies: database session, settings, and current user."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.permissions import PermissionName, user_has_permission
from app.core.security import TokenError, decode_access_token
from app.models.user import User
from app.repositories import users as users_repo

bearer_scheme = HTTPBearer(auto_error=False)

UNAUTHENTICATED = "Not authenticated"
FORBIDDEN = "Insufficient permissions"


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a session bound to the application's engine.

    Services commit their writes; this dependency only guarantees rollback and
    cleanup on error.
    """
    factory = request.app.state.db_session_factory
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=UNAUTHENTICATED,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> User:
    """Return the active user behind the bearer token.

    The user is reloaded on every request so deactivation and role changes take
    effect immediately.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        user_id = decode_access_token(credentials.credentials, settings)
    except TokenError as exc:
        raise _unauthorized() from exc

    user = await users_repo.get_with_permissions(session, user_id)
    if user is None or not user.is_active:
        raise _unauthorized()

    return user


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_permission(
    permission: PermissionName | str,
) -> Callable[[User], Awaitable[User]]:
    """Build a dependency that rejects users without ``permission``.

    Permission failures are 403, not 404: the caller is authenticated and the
    fact that the endpoint exists is not a secret. Resource-level checks (for
    example a lead assigned to another counsellor) return 404 separately, so
    they do not reveal whether the resource exists.
    """

    async def dependency(user: CurrentUserDep) -> User:
        if not user_has_permission(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=FORBIDDEN,
            )
        return user

    return dependency
