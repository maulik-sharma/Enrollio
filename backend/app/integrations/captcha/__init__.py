"""CAPTCHA provider interface and adapters."""

from app.integrations.captcha.base import CaptchaVerifier
from app.integrations.captcha.factory import build_captcha_verifier

__all__ = ["CaptchaVerifier", "build_captcha_verifier"]
