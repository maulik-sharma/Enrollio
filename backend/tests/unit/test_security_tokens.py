"""Access-token and refresh-token helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import Settings
from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
)


def _settings(secret: str = "unit-test-secret-key-at-least-32-chars") -> Settings:
    return Settings(JWT_SECRET=secret, ACCESS_TOKEN_EXPIRE_MINUTES=15, _env_file=None)


def test_access_token_round_trip() -> None:
    settings = _settings()
    user_id = uuid.uuid4()

    token = create_access_token(user_id, settings)

    assert decode_access_token(token, settings) == user_id


def test_access_token_rejects_a_different_secret() -> None:
    token = create_access_token(uuid.uuid4(), _settings("secret-one-that-is-at-least-32-bytes"))

    with pytest.raises(TokenError):
        decode_access_token(token, _settings("secret-two-that-is-at-least-32-bytes"))


def test_expired_access_token_is_rejected() -> None:
    settings = _settings()
    issued_at = datetime.now(UTC) - timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES + 5)

    token = create_access_token(uuid.uuid4(), settings, now=issued_at)

    with pytest.raises(TokenError):
        decode_access_token(token, settings)


def test_malformed_token_is_rejected() -> None:
    with pytest.raises(TokenError):
        decode_access_token("not-a-jwt", _settings())


def test_refresh_tokens_are_unique_and_hash_stably() -> None:
    first = generate_refresh_token()
    second = generate_refresh_token()

    assert first != second
    assert hash_refresh_token(first) == hash_refresh_token(first)
    assert hash_refresh_token(first) != hash_refresh_token(second)
    assert len(hash_refresh_token(first)) == 64
