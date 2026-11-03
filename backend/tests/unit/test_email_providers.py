"""Email and WhatsApp provider contracts, factory defaults, and mocks."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import EmailProvider, Environment, Settings
from app.integrations.email.base import EmailMessage, EmailNotConfigured
from app.integrations.email.factory import build_email_provider
from app.integrations.email.mock import MockEmailProvider
from app.integrations.email.sendgrid import SendGridEmailProvider
from app.integrations.whatsapp.base import (
    InboundWhatsAppMessage,
    WhatsAppMessage,
    WhatsAppNotImplemented,
)
from app.integrations.whatsapp.factory import build_whatsapp_provider


def _settings(**overrides: Any) -> Settings:
    return Settings(
        ENV=Environment.test,
        JWT_SECRET="test-secret",
        _env_file=None,
        **overrides,
    )


def _unused_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker[AsyncSession]()


def test_default_factory_returns_the_mock_provider() -> None:
    provider = build_email_provider(_settings(), _unused_session_factory())
    assert isinstance(provider, MockEmailProvider)


def test_mock_flag_wins_over_a_real_provider_name() -> None:
    provider = build_email_provider(
        _settings(EMAIL_PROVIDER=EmailProvider.sendgrid, EMAIL_API_KEY="SG.test"),
        _unused_session_factory(),
    )
    assert isinstance(provider, MockEmailProvider)


def test_sendgrid_is_selected_when_configured() -> None:
    provider = build_email_provider(
        _settings(
            USE_MOCK_EMAIL=False,
            EMAIL_PROVIDER=EmailProvider.sendgrid,
            EMAIL_API_KEY="SG.test",
        ),
        _unused_session_factory(),
    )
    assert isinstance(provider, SendGridEmailProvider)


def test_sendgrid_requires_an_api_key() -> None:
    with pytest.raises(EmailNotConfigured):
        build_email_provider(
            _settings(USE_MOCK_EMAIL=False, EMAIL_PROVIDER=EmailProvider.sendgrid),
            _unused_session_factory(),
        )


def test_ses_is_not_implemented_yet() -> None:
    with pytest.raises(EmailNotConfigured):
        build_email_provider(
            _settings(
                USE_MOCK_EMAIL=False,
                EMAIL_PROVIDER=EmailProvider.ses,
                EMAIL_API_KEY="unused",
            ),
            _unused_session_factory(),
        )


async def test_whatsapp_stub_fails_loudly() -> None:
    provider = build_whatsapp_provider()
    with pytest.raises(WhatsAppNotImplemented):
        await provider.send(WhatsAppMessage(to_number="+919876500001", text_body="hi"))
    with pytest.raises(WhatsAppNotImplemented):
        await provider.parse_inbound({})
    with pytest.raises(WhatsAppNotImplemented):
        provider.verify_webhook({}, b"{}")


def test_email_message_requires_a_body() -> None:
    with pytest.raises(ValueError):
        EmailMessage(to_address="student@example.com", subject="Empty")


def test_inbound_whatsapp_message_shape_is_available() -> None:
    message = InboundWhatsAppMessage(
        provider_message_id="wamid.1",
        from_number="+919876500001",
        to_number="+919876500002",
        text_body="hello",
    )
    assert message.text_body == "hello"
