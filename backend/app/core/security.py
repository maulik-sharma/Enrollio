"""Password hashing and access-token helpers.

Access tokens are short-lived JWTs. Refresh tokens are opaque random strings
whose SHA-256 hash is persisted, so a database leak does not expose usable
tokens.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings


class TokenError(Exception):
    """Raised when an access token cannot be trusted."""


def build_password_hasher(settings: Settings) -> PasswordHasher:
    """Build a hasher from the configured Argon2id parameters."""
    return PasswordHasher(
        time_cost=settings.ARGON2_TIME_COST,
        memory_cost=settings.ARGON2_MEMORY_COST,
        parallelism=settings.ARGON2_PARALLELISM,
        hash_len=32,
        salt_len=16,
    )


def hash_password(password: str, settings: Settings) -> str:
    """Return an Argon2id hash for ``password``."""
    return build_password_hasher(settings).hash(password)


def verify_password(password: str, password_hash: str, settings: Settings) -> bool:
    """Return True when ``password`` matches ``password_hash``."""
    try:
        return build_password_hasher(settings).verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str, settings: Settings) -> bool:
    """Return True when the hash was produced with weaker parameters."""
    try:
        return build_password_hasher(settings).check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


@lru_cache(maxsize=8)
def _dummy_hash(time_cost: int, memory_cost: int, parallelism: int) -> str:
    hasher = PasswordHasher(
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        hash_len=32,
        salt_len=16,
    )
    return hasher.hash("enrollio-dummy-password")


def verify_dummy_password(password: str, settings: Settings) -> None:
    """Spend the same work as a real verification for unknown accounts.

    This keeps login timing from revealing whether an email exists. The result
    is intentionally discarded.
    """
    verify_password(
        password,
        _dummy_hash(
            settings.ARGON2_TIME_COST,
            settings.ARGON2_MEMORY_COST,
            settings.ARGON2_PARALLELISM,
        ),
        settings,
    )


def create_access_token(
    user_id: uuid.UUID,
    settings: Settings,
    now: datetime | None = None,
) -> str:
    """Issue a signed access token for ``user_id``."""
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": "enrollio",
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str, settings: Settings) -> uuid.UUID:
    """Validate ``token`` and return its user id."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            issuer="enrollio",
            options={"require": ["sub", "type", "iat", "exp"]},
        )
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid access token") from exc

    if payload.get("type") != "access":
        raise TokenError("Not an access token")

    try:
        return uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError) as exc:
        raise TokenError("Invalid subject") from exc


def generate_refresh_token() -> str:
    """Return a high-entropy opaque refresh token."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Return the stable SHA-256 hash stored in the database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
