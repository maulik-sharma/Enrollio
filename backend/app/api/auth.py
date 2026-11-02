"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep, SettingsDep
from app.core.config import Settings
from app.core.permissions import user_permission_names
from app.schemas.auth import CurrentUser, LoginRequest, RoleSummary, StatusResponse, TokenResponse
from app.services import auth as auth_service
from app.services.auth import AuthenticationError, RefreshTokenError

router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"


def _set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=True,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=True,
        samesite="strict",
    )


def _token_response(tokens: auth_service.IssuedTokens) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        token_type="bearer",
        expires_in=tokens.expires_in,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> TokenResponse:
    """Exchange email and password for an access token and refresh cookie."""
    try:
        tokens = await auth_service.login(
            session,
            settings,
            email=str(payload.email),
            password=payload.password,
            user_agent=request.headers.get("user-agent"),
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc

    _set_refresh_cookie(response, tokens.refresh_token, settings)
    return _token_response(tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> TokenResponse | JSONResponse:
    """Rotate the refresh cookie and return a fresh access token."""
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_token:
        return _refresh_failure()

    try:
        tokens = await auth_service.rotate(
            session,
            settings,
            raw_token=raw_token,
            user_agent=request.headers.get("user-agent"),
        )
    except RefreshTokenError:
        return _refresh_failure()

    response = JSONResponse(content=_token_response(tokens).model_dump())
    _set_refresh_cookie(response, tokens.refresh_token, settings)
    return response


@router.post("/logout", response_model=StatusResponse)
async def logout(
    request: Request,
    session: SessionDep,
) -> Response:
    """Revoke the current refresh-token family and clear the cookie."""
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    await auth_service.logout(session, raw_token=raw_token)

    response = JSONResponse(content={"status": "ok"})
    _clear_refresh_cookie(response)
    return response


@router.get("/me", response_model=CurrentUser)
async def me(user: CurrentUserDep) -> CurrentUser:
    """Return the authenticated user with roles and flattened permissions."""
    return CurrentUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        roles=[RoleSummary.model_validate(role) for role in user.roles],
        permissions=sorted(user_permission_names(user)),
    )


def _refresh_failure() -> JSONResponse:
    response = JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Invalid refresh token"},
    )
    _clear_refresh_cookie(response)
    return response
