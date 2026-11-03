"""Select the configured CAPTCHA verifier."""

from __future__ import annotations

from app.core.config import Settings
from app.integrations.captcha.base import CaptchaVerifier
from app.integrations.captcha.mock import MockCaptchaVerifier


class CaptchaNotConfigured(RuntimeError):
    """A real CAPTCHA verifier is required but no adapter exists yet."""


def build_captcha_verifier(settings: Settings) -> CaptchaVerifier:
    """Return the mock verifier until a real provider is selected."""
    if settings.USE_MOCK_CAPTCHA:
        return MockCaptchaVerifier()
    raise CaptchaNotConfigured("No real CAPTCHA verifier is implemented yet")
