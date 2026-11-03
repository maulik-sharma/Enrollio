"""CAPTCHA provider defaults and mock behaviour."""

from __future__ import annotations

import pytest

from app.core.config import Environment, Settings
from app.integrations.captcha.factory import CaptchaNotConfigured, build_captcha_verifier
from app.integrations.captcha.mock import MockCaptchaVerifier


async def test_mock_accepts_a_non_empty_token() -> None:
    verifier = MockCaptchaVerifier()
    assert await verifier.verify("test-captcha", remote_ip="127.0.0.1")


async def test_mock_rejects_empty_and_sentinel_tokens() -> None:
    verifier = MockCaptchaVerifier()
    assert not await verifier.verify("   ", remote_ip="127.0.0.1")
    assert not await verifier.verify("invalid", remote_ip="127.0.0.1")


def test_default_factory_returns_mock() -> None:
    settings = Settings(ENV=Environment.test, JWT_SECRET="test-secret", _env_file=None)
    assert isinstance(build_captcha_verifier(settings), MockCaptchaVerifier)


def test_factory_fails_when_mock_is_disabled() -> None:
    settings = Settings(
        ENV=Environment.test,
        JWT_SECRET="test-secret",
        USE_MOCK_CAPTCHA=False,
        _env_file=None,
    )
    with pytest.raises(CaptchaNotConfigured):
        build_captcha_verifier(settings)
