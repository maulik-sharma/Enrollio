"""Password hashing behaviour."""

from __future__ import annotations

from app.core.config import Environment, Settings
from app.core.security import hash_password, needs_rehash, verify_password


def _settings() -> Settings:
    return Settings(
        ENV=Environment.test,
        JWT_SECRET="test-secret",
        ARGON2_TIME_COST=1,
        ARGON2_MEMORY_COST=8192,
        ARGON2_PARALLELISM=1,
        _env_file=None,
    )


def test_hash_is_salted_and_verifiable() -> None:
    settings = _settings()

    first = hash_password("correct horse battery", settings)
    second = hash_password("correct horse battery", settings)

    assert first != second
    assert "correct horse battery" not in first
    assert verify_password("correct horse battery", first, settings)
    assert not verify_password("wrong password", first, settings)
    assert not needs_rehash(first, settings)


def test_malformed_hash_is_rejected() -> None:
    settings = _settings()

    assert not verify_password("anything", "not-a-hash", settings)
    assert needs_rehash("not-a-hash", settings)
