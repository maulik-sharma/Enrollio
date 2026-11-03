"""Deterministic CAPTCHA verifier for development and tests."""

from __future__ import annotations


class MockCaptchaVerifier:
    """Accept any non-empty token except the sentinel ``invalid``.

    Tests can exercise both the success and rejection paths without calling a
    vendor. The mock never inspects the remote IP.
    """

    async def verify(self, token: str, *, remote_ip: str | None) -> bool:
        del remote_ip
        cleaned = token.strip()
        return bool(cleaned) and cleaned.lower() != "invalid"
