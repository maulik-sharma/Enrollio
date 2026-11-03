"""Create and authenticate source-scoped partner API keys."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.repositories import api_keys as api_keys_repo
from app.repositories import catalogues as catalogues_repo

KEY_PREFIX = "enr_"


class ApiKeySourceNotFound(Exception):
    """The requested lead source does not exist."""


@dataclass(frozen=True)
class CreatedApiKey:
    api_key: ApiKey
    plaintext: str


def generate_api_key() -> str:
    """Return a new high-entropy API key with a recognisable prefix."""
    return f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_key(value: str) -> str:
    """Return the SHA-256 hash persisted for an API key."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def create_api_key(
    session: AsyncSession,
    *,
    name: str,
    source_id: uuid.UUID,
    created_by_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
) -> CreatedApiKey:
    """Create a key and return its plaintext exactly once."""
    source = await catalogues_repo.get_source_by_id(session, source_id)
    if source is None:
        raise ApiKeySourceNotFound

    plaintext = generate_api_key()
    api_key = ApiKey(
        name=name.strip(),
        key_prefix=plaintext[:12],
        key_hash=hash_api_key(plaintext),
        source_id=source_id,
        expires_at=expires_at,
        created_by_id=created_by_id,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return CreatedApiKey(api_key=api_key, plaintext=plaintext)


async def authenticate_api_key(session: AsyncSession, presented: str) -> ApiKey | None:
    """Return the active key matching ``presented``, or None."""
    cleaned = presented.strip()
    if not cleaned:
        return None
    return await api_keys_repo.get_active_by_hash(session, hash_api_key(cleaned))
