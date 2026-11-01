"""Configuration tests: defaults, production fail-fast, and .env.example parity."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import (
    ENV_FILE,
    EmailProvider,
    Environment,
    LLMProvider,
    Settings,
)

ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_EXAMPLE = ROOT_DIR / ".env.example"

MOCK_FLAGS = (
    "USE_MOCK_EMAIL",
    "USE_MOCK_WHATSAPP",
    "USE_MOCK_CALENDAR",
    "USE_MOCK_LLM",
    "USE_MOCK_SPEECH",
    "USE_MOCK_STORAGE",
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (*MOCK_FLAGS, "JWT_SECRET", "ENV"):
        monkeypatch.delenv(name, raising=False)


def test_missing_jwt_secret_in_production_raises(clean_env: None) -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(ENV="production", JWT_SECRET="", _env_file=None)

    assert "JWT_SECRET" in str(exc_info.value)


def test_placeholder_jwt_secret_in_production_raises(clean_env: None) -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENV="production",
            JWT_SECRET="replace-with-a-long-random-string",
            _env_file=None,
        )

    assert "JWT_SECRET" in str(exc_info.value)


def test_production_settings_accept_a_real_secret(clean_env: None) -> None:
    settings = Settings(
        ENV="production",
        JWT_SECRET="a" * 64,
        _env_file=None,
    )

    assert settings.ENV is Environment.production


def test_real_provider_requires_credentials_in_production(clean_env: None) -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENV="production",
            JWT_SECRET="a" * 64,
            USE_MOCK_LLM=False,
            LLM_PROVIDER=LLMProvider.openai,
            LLM_API_KEY=None,
            _env_file=None,
        )

    assert "LLM_API_KEY" in str(exc_info.value)

    settings = Settings(
        ENV="production",
        JWT_SECRET="a" * 64,
        USE_MOCK_LLM=False,
        LLM_PROVIDER=LLMProvider.openai,
        LLM_API_KEY="sk-test",
        _env_file=None,
    )
    assert settings.LLM_API_KEY is not None


def test_messages_are_ignored_in_development(clean_env: None) -> None:
    settings = Settings(ENV="development", JWT_SECRET="", _env_file=None)

    assert settings.ENV is Environment.development


def test_mock_flags_and_providers_default_to_mock(clean_env: None) -> None:
    settings = Settings(_env_file=None)

    assert all(getattr(settings, flag) is True for flag in MOCK_FLAGS)
    assert settings.LLM_PROVIDER is LLMProvider.mock
    assert settings.EMAIL_PROVIDER is EmailProvider.mock


def test_env_file_points_at_the_repository_root() -> None:
    assert ENV_FILE == ROOT_DIR / ".env"


def test_env_example_is_loadable_and_complete() -> None:
    keys = {
        line.split("=", 1)[0].strip()
        for line in ENV_EXAMPLE.read_text().splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }

    assert keys == set(Settings.model_fields)

    settings = Settings(_env_file=ENV_EXAMPLE)
    assert settings.APP_NAME == "Enrollio"
    assert settings.USE_MOCK_EMAIL is True
