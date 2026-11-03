"""Select the configured email provider."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import EmailProvider, Settings
from app.integrations.email.base import EmailNotConfigured
from app.integrations.email.base import EmailProvider as EmailProviderContract
from app.integrations.email.mock import MockEmailProvider
from app.integrations.email.resend import ResendEmailProvider
from app.integrations.email.sendgrid import SendGridEmailProvider


def build_email_provider(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> EmailProviderContract:
    """Return the mock by default and a real adapter only when configured."""
    if settings.USE_MOCK_EMAIL or settings.EMAIL_PROVIDER is EmailProvider.mock:
        secret = (
            settings.EMAIL_WEBHOOK_SECRET.get_secret_value()
            if settings.EMAIL_WEBHOOK_SECRET is not None
            else None
        )
        return MockEmailProvider(
            session_factory,
            from_address=settings.EMAIL_FROM_ADDRESS,
            from_name=settings.EMAIL_FROM_NAME,
            webhook_secret=secret,
        )

    if settings.EMAIL_PROVIDER is EmailProvider.sendgrid:
        if settings.EMAIL_API_KEY is None:
            raise EmailNotConfigured("EMAIL_API_KEY is required for SendGrid")
        secret = (
            settings.EMAIL_WEBHOOK_SECRET.get_secret_value()
            if settings.EMAIL_WEBHOOK_SECRET is not None
            else None
        )
        return SendGridEmailProvider(
            settings.EMAIL_API_KEY.get_secret_value(),
            from_address=settings.EMAIL_FROM_ADDRESS,
            from_name=settings.EMAIL_FROM_NAME,
            webhook_secret=secret,
        )

    if settings.EMAIL_PROVIDER is EmailProvider.resend:
        if settings.EMAIL_API_KEY is None:
            raise EmailNotConfigured("EMAIL_API_KEY is required for Resend")
        secret = (
            settings.EMAIL_WEBHOOK_SECRET.get_secret_value()
            if settings.EMAIL_WEBHOOK_SECRET is not None
            else None
        )
        return ResendEmailProvider(
            settings.EMAIL_API_KEY.get_secret_value(),
            from_address=settings.EMAIL_FROM_ADDRESS,
            from_name=settings.EMAIL_FROM_NAME,
            webhook_secret=secret,
        )

    raise EmailNotConfigured(f"No email adapter is implemented for {settings.EMAIL_PROVIDER.value}")
