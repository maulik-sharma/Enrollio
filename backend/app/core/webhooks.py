"""HMAC-SHA256 helpers for inbound provider webhooks."""

from __future__ import annotations

import hashlib
import hmac
import time

DEFAULT_TOLERANCE_SECONDS = 300


def sign_webhook(
    payload: bytes | str,
    secret: str,
    *,
    timestamp: int | None = None,
) -> str:
    """Return a ``t=<unix>,v1=<hex digest>`` signature header value."""
    sent_at = int(time.time()) if timestamp is None else int(timestamp)
    body = payload.encode("utf-8") if isinstance(payload, str) else payload
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{sent_at}.".encode("ascii") + body,
        hashlib.sha256,
    ).hexdigest()
    return f"t={sent_at},v1={digest}"


def verify_webhook_signature(
    payload: bytes | str,
    signature: str,
    secret: str,
    *,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: int | None = None,
) -> bool:
    """Return True when the timestamp is fresh and the HMAC matches."""
    timestamp, digest = _parse_signature(signature)
    if timestamp is None or digest is None:
        return False

    current = int(time.time()) if now is None else int(now)
    if abs(current - timestamp) > tolerance_seconds:
        return False

    body = payload.encode("utf-8") if isinstance(payload, str) else payload
    expected = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("ascii") + body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, digest)


def _parse_signature(signature: str) -> tuple[int | None, str | None]:
    timestamp: int | None = None
    digest: str | None = None
    for part in signature.split(","):
        key, separator, value = part.strip().partition("=")
        if not separator:
            continue
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                return None, None
        elif key == "v1":
            digest = value
    if timestamp is None or digest is None or len(digest) != 64:
        return None, None
    return timestamp, digest
