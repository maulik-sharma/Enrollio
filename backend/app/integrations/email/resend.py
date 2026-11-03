"""Resend adapter.

Sending uses the Resend HTTP API through ``httpx``. Inbound email arrives as an
``email.received`` webhook that contains metadata only, so the adapter fetches
the full message from ``GET /emails/receiving/{id}`` before normalising it.
Webhooks are Svix-signed; verification uses the raw request body.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from app.integrations.email.base import (
    EmailDeliveryError,
    EmailMessage,
    InboundMessage,
    InvalidInboundEmail,
    coerce_headers,
    header_value,
    parse_address,
    parse_received_at,
)

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_RECEIVING_URL = "https://api.resend.com/emails/receiving"
DEFAULT_TIMEOUT_SECONDS = 10.0
SVIX_TOLERANCE_SECONDS = 300
SVIX_SECRET_PREFIX = "whsec_"


class ResendEmailProvider:
    """Resend sender and inbound-email adapter."""

    def __init__(
        self,
        api_key: str,
        *,
        from_address: str,
        from_name: str = "Enrollio",
        webhook_secret: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if api_key.strip() == "":
            raise EmailDeliveryError("Resend API key is empty")
        self._api_key = api_key
        self._from_address = from_address
        self._from_name = from_name
        self._webhook_secret = webhook_secret
        self._client = client
        self._timeout = timeout
        self._clock = clock or time.time

    async def send(self, message: EmailMessage) -> str:
        payload = self._build_payload(message)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = await self._request(
                "POST",
                RESEND_API_URL,
                json=payload,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise EmailDeliveryError("Resend could not be reached") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise EmailDeliveryError(f"Resend rejected the message with {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise EmailDeliveryError("Resend response was not JSON") from exc
        if not isinstance(body, Mapping):
            raise EmailDeliveryError("Resend response was not an object")
        provider_message_id = str(body.get("id") or "").strip()
        if provider_message_id == "":
            raise EmailDeliveryError("Resend response had no message id")
        return provider_message_id

    async def parse_inbound(self, webhook_payload: Mapping[str, Any]) -> InboundMessage:
        payload = await self._expand_inbound(webhook_payload)
        headers = coerce_headers(payload.get("headers"))
        from_address, from_name = parse_address(
            _first(payload.get("from") or payload.get("from_address"))
        )
        to_address, to_name = _first_address(payload.get("to") or payload.get("to_address"))
        provider_message_id = str(
            payload.get("message_id")
            or payload.get("provider_message_id")
            or payload.get("id")
            or header_value(headers, "Message-Id")
            or ""
        ).strip()
        if provider_message_id == "":
            raise InvalidInboundEmail("inbound payload has no provider message id")

        subject = payload.get("subject")
        text_body = payload.get("text") or payload.get("text_body")
        html_body = payload.get("html") or payload.get("html_body")
        in_reply_to = (
            str(payload.get("in_reply_to") or "").strip()
            or header_value(headers, "In-Reply-To")
            or None
        )
        return InboundMessage(
            provider_message_id=provider_message_id,
            from_address=from_address,
            from_name=from_name,
            to_address=to_address,
            to_name=to_name,
            subject=str(subject) if subject is not None else None,
            text_body=str(text_body) if text_body is not None else None,
            html_body=str(html_body) if html_body is not None else None,
            in_reply_to=in_reply_to,
            received_at=parse_received_at(payload.get("created_at") or payload.get("received_at")),
            headers=headers,
            raw=dict(webhook_payload),
        )

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        if not self._webhook_secret:
            return False
        svix_id = header_value(headers, "svix-id")
        svix_timestamp = header_value(headers, "svix-timestamp")
        svix_signature = header_value(headers, "svix-signature")
        if not svix_id or not svix_timestamp or not svix_signature:
            return False
        try:
            timestamp = int(svix_timestamp)
        except ValueError:
            return False
        if abs(self._clock() - timestamp) > SVIX_TOLERANCE_SECONDS:
            return False
        try:
            payload = body.decode("utf-8")
        except UnicodeDecodeError:
            return False

        key = _decode_svix_secret(self._webhook_secret)
        if key is None:
            return False
        signed = f"{svix_id}.{svix_timestamp}.{payload}".encode()
        expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest())
        for candidate in svix_signature.split():
            version, separator, signature = candidate.partition(",")
            if not separator or version != "v1":
                continue
            if hmac.compare_digest(signature, expected.decode("ascii")):
                return True
        return False

    async def _expand_inbound(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Fetch the full received email when the webhook only has metadata."""
        data = payload.get("data")
        event_data = data if isinstance(data, Mapping) else {}
        email_id = str(event_data.get("email_id") or "").strip()
        if payload.get("type") != "email.received" or email_id == "":
            return payload

        fetched = await self._fetch_received_email(email_id)
        merged: dict[str, Any] = {**event_data, **fetched}
        if not merged.get("message_id"):
            merged["message_id"] = event_data.get("message_id") or fetched.get("id")
        return merged

    async def _fetch_received_email(self, email_id: str) -> Mapping[str, Any]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            response = await self._request(
                "GET",
                f"{RESEND_RECEIVING_URL}/{email_id}",
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise EmailDeliveryError("Resend received email could not be fetched") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise EmailDeliveryError(
                f"Resend received email fetch failed with {response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise EmailDeliveryError("Resend received email response was not JSON") from exc
        if not isinstance(body, Mapping):
            raise EmailDeliveryError("Resend received email response was not an object")
        return body

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: Mapping[str, Any] | None = None,
        headers: Mapping[str, str],
    ) -> httpx.Response:
        if self._client is not None:
            return await self._client.request(method, url, json=json, headers=dict(headers))
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.request(method, url, json=json, headers=dict(headers))

    def _build_payload(self, message: EmailMessage) -> dict[str, Any]:
        recipient = message.to_address
        if message.to_name:
            recipient = f"{message.to_name} <{message.to_address}>"
        payload: dict[str, Any] = {
            "from": f"{message.from_name or self._from_name} "
            f"<{message.from_address or self._from_address}>",
            "to": [recipient],
            "subject": message.subject,
        }
        if message.text_body:
            payload["text"] = message.text_body
        if message.html_body:
            payload["html"] = message.html_body
        if message.reply_to:
            payload["reply_to"] = [message.reply_to]
        if message.headers:
            payload["headers"] = dict(message.headers)
        tags = _metadata_tags(message.metadata)
        if tags:
            payload["tags"] = tags
        return payload


def _metadata_tags(metadata: Mapping[str, Any]) -> list[dict[str, str]]:
    tags: list[dict[str, str]] = []
    for key, value in metadata.items():
        name = str(key)
        item = str(value)
        if _valid_tag(name) and _valid_tag(item):
            tags.append({"name": name, "value": item})
    return tags


def _valid_tag(value: str) -> bool:
    return 1 <= len(value) <= 256 and all(
        character.isascii() and (character.isalnum() or character in {"_", "-"})
        for character in value
    )


def _first(value: object) -> object:
    if isinstance(value, list | tuple):
        for item in value:
            if str(item).strip():
                return item
        raise InvalidInboundEmail("address list is empty")
    return value


def _first_address(value: object) -> tuple[str, str | None]:
    first = _first(value)
    try:
        return parse_address(first)
    except InvalidInboundEmail as exc:
        raise InvalidInboundEmail("recipient address is missing") from exc


def _decode_svix_secret(secret: str) -> bytes | None:
    encoded = secret.removeprefix(SVIX_SECRET_PREFIX).strip()
    if encoded == "":
        return None
    padded = encoded + "=" * (-len(encoded) % 4)
    try:
        return base64.b64decode(padded, validate=True)
    except (binascii.Error, ValueError):
        return None


def build_svix_signature(secret: str, svix_id: str, timestamp: int, body: bytes) -> str:
    """Return the ``svix-signature`` header for a payload, for tests and mocks."""
    key = _decode_svix_secret(secret)
    if key is None:
        raise ValueError("invalid Svix secret")
    signed = f"{svix_id}.{timestamp}.{body.decode('utf-8')}".encode()
    digest = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode("ascii")
    return f"v1,{digest}"


def svix_headers(
    secret: str, svix_id: str, body: bytes, *, timestamp: int | None = None
) -> dict[str, str]:
    """Build the three headers Resend/Svix sends for ``body``."""
    stamp = int(time.time()) if timestamp is None else timestamp
    return {
        "svix-id": svix_id,
        "svix-timestamp": str(stamp),
        "svix-signature": build_svix_signature(secret, svix_id, stamp, body),
    }


__all__ = [
    "RESEND_API_URL",
    "RESEND_RECEIVING_URL",
    "ResendEmailProvider",
    "build_svix_signature",
    "svix_headers",
]
