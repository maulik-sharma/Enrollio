"""Typed application configuration loaded from environment variables and `.env`."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
# One .env at the repository root, shared by the backend and Docker Compose.
ENV_FILE = BACKEND_DIR.parent / ".env"

# Values shipped in `.env.example`. They are safe for local development but must
# never reach a production deployment.
PLACEHOLDER_SECRETS = {
    "",
    "change-me",
    "changeme",
    "replace-me",
    "replace-with-a-long-random-string",
    "your-secret-here",
}


class Environment(StrEnum):
    development = "development"
    test = "test"
    production = "production"


class LLMProvider(StrEnum):
    mock = "mock"
    openai = "openai"
    anthropic = "anthropic"


class EmailProvider(StrEnum):
    mock = "mock"
    ses = "ses"
    sendgrid = "sendgrid"


class WhatsAppProvider(StrEnum):
    mock = "mock"
    cloud_api = "cloud_api"


class CalendarProvider(StrEnum):
    mock = "mock"
    google = "google"


class SpeechProvider(StrEnum):
    mock = "mock"
    whisper_local = "whisper_local"
    whisper_api = "whisper_api"


class StorageProvider(StrEnum):
    local = "local"
    s3 = "s3"


class Settings(BaseSettings):
    """Runtime configuration.

    The `USE_MOCK_*` flags are authoritative: when true, the corresponding
    provider adapter is replaced by its in-process mock. When false, the adapter
    selected by `*_PROVIDER` is used and its credentials become mandatory in
    production.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ENV: Environment = Environment.development
    APP_NAME: str = "Enrollio"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+asyncpg://enrollio:enrollio@localhost:5432/enrollio"
    # Integration tests must never run against DATABASE_URL: the migration test
    # downgrades to base. This database name must end with `_test`.
    TEST_DATABASE_URL: str = "postgresql+asyncpg://enrollio:enrollio@localhost:5432/enrollio_test"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: SecretStr = SecretStr("")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_FAILURE_WINDOW_MINUTES: int = 15
    LOGIN_LOCKOUT_MINUTES: int = 15

    # Password hashing. Tests lower these values to keep the suite fast.
    ARGON2_TIME_COST: int = 3
    ARGON2_MEMORY_COST: int = 65536
    ARGON2_PARALLELISM: int = 4

    # Browser origins allowed to call the API with credentials.
    CORS_ORIGINS: str = "http://localhost:3000"

    # Development-only demo accounts. Never enabled in production.
    # `.env.example` turns this on for local development.
    SEED_DEMO_USERS: bool = False
    SEED_DEMO_PASSWORD: SecretStr = SecretStr("dev-only-password")

    LLM_PROVIDER: LLMProvider = LLMProvider.mock
    LLM_API_KEY: SecretStr | None = None
    LLM_MODEL: str = "mock"
    LLM_BASE_URL: str | None = None

    EMAIL_PROVIDER: EmailProvider = EmailProvider.mock
    EMAIL_API_KEY: SecretStr | None = None
    EMAIL_FROM_ADDRESS: str = "no-reply@example.test"
    EMAIL_FROM_NAME: str = "Enrollio"
    EMAIL_REPLY_DOMAIN: str = "reply.example.test"
    EMAIL_WEBHOOK_SECRET: SecretStr | None = None

    WHATSAPP_PROVIDER: WhatsAppProvider = WhatsAppProvider.mock
    WHATSAPP_ACCESS_TOKEN: SecretStr | None = None
    WHATSAPP_PHONE_NUMBER_ID: str | None = None

    CALENDAR_PROVIDER: CalendarProvider = CalendarProvider.mock
    CALENDAR_API_KEY: SecretStr | None = None

    SPEECH_PROVIDER: SpeechProvider = SpeechProvider.mock
    SPEECH_API_KEY: SecretStr | None = None

    STORAGE_PROVIDER: StorageProvider = StorageProvider.local
    LOCAL_STORAGE_PATH: str = "./storage"
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET: str = "enrollio"
    S3_ACCESS_KEY: SecretStr | None = None
    S3_SECRET_KEY: SecretStr | None = None
    S3_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False

    USE_MOCK_EMAIL: bool = True
    USE_MOCK_WHATSAPP: bool = True
    USE_MOCK_CALENDAR: bool = True
    USE_MOCK_LLM: bool = True
    USE_MOCK_SPEECH: bool = True
    USE_MOCK_STORAGE: bool = True

    @model_validator(mode="after")
    def _fail_fast_in_production(self) -> Settings:
        if self.ENV is not Environment.production:
            return self

        missing: list[str] = []

        if self.SEED_DEMO_USERS:
            raise ValueError("SEED_DEMO_USERS must be false in production")

        if self._is_placeholder(self.JWT_SECRET):
            missing.append("JWT_SECRET")

        if (
            not self.USE_MOCK_LLM
            and self.LLM_PROVIDER is not LLMProvider.mock
            and self._is_placeholder(self.LLM_API_KEY)
        ):
            missing.append("LLM_API_KEY")

        if (
            not self.USE_MOCK_EMAIL
            and self.EMAIL_PROVIDER is not EmailProvider.mock
            and self._is_placeholder(self.EMAIL_API_KEY)
        ):
            missing.append("EMAIL_API_KEY")

        if (
            not self.USE_MOCK_SPEECH
            and self.SPEECH_PROVIDER is not SpeechProvider.mock
            and self._is_placeholder(self.SPEECH_API_KEY)
        ):
            missing.append("SPEECH_API_KEY")

        if (
            not self.USE_MOCK_STORAGE
            and self.STORAGE_PROVIDER is not StorageProvider.local
            and (
                self._is_placeholder(self.S3_ACCESS_KEY) or self._is_placeholder(self.S3_SECRET_KEY)
            )
        ):
            missing.append("S3_ACCESS_KEY/S3_SECRET_KEY")

        if missing:
            raise ValueError(
                "Missing required production configuration: " + ", ".join(sorted(set(missing)))
            )

        return self

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list, split on commas."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @staticmethod
    def _is_placeholder(value: SecretStr | str | None) -> bool:
        if value is None:
            return True
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        return raw.strip().lower() in PLACEHOLDER_SECRETS


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
