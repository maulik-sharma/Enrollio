"""Password hashing and token helpers built on Argon2id.

Only password hashing lives here in M1.1; JWT helpers arrive with M1.2.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings


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
