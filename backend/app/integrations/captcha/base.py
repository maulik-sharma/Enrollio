"""CAPTCHA verification contract for public endpoints."""

from __future__ import annotations

from typing import Protocol


class CaptchaVerifier(Protocol):
    """Verify a browser-supplied CAPTCHA token for one client IP."""

    async def verify(self, token: str, *, remote_ip: str | None) -> bool:
        """Return True when the token is valid for this request."""
        ...
