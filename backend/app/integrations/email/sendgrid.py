"""SendGrid adapter (M3.1).

Sending uses the v3 HTTP API through ``httpx``; no SDK is imported here and no
other module may construct this class directly. Inbound Parse webhooks are
expected to use HTTP Basic auth with username ``sendgrid`` and
``EMAIL_WEBHOOK_SECRET`` as the password, which SendGrid supports in the Inbound
Parse configuration.
"""

from __future__ import annotations

import base64
import binascii
import hmac
from collections.abc import Mapping
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

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"
SENDGRID_INBOUND_USERNAME = "sendgrid"
DEFAULT_TIMEOUT_SECONDS = 10.0


class SendGridEmailProvider:
    """Minimal SendGrid v3 sender and Inbound Parse adapter."""

    def __init__(
        self,
        api_key: str,
        *,
        from_address: str,
        from_name: str = "Enrollio",
        webhook_secret: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if api_key.strip() == "":
            raise EmailDeliveryError("SendGrid API key is empty")
        self._api_key = api_key
        self._from_address = from_address
        self._from_name = from_name
        self._webhook_secret = webhook_secret
        self._client = client
        self._timeout = timeout

    async def send(self, message: EmailMessage) -> str:
        payload = self._build_payload(message)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = await self._post(payload, headers)
        except httpx.HTTPError as exc:
            raise EmailDeliveryError("SendGrid could not be reached") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise EmailDeliveryError(f"SendGrid rejected the message with {response.status_code}")
        provider_message_id = header_value(response.headers, "X-Message-Id")
        if provider_message_id is None:
            raise EmailDeliveryError("SendGrid response had no X-Message-Id")
        return provider_message_id

    async def _post(self, payload: Mapping[str, Any], headers: Mapping[str, str]) -> httpx.Response:
        if self._client is not None:
            return await self._client.post(
                SENDGRID_API_URL, json=dict(payload), headers=dict(headers)
            )
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.post(SENDGRID_API_URL, json=dict(payload), headers=dict(headers))

    def _build_payload(self, message: EmailMessage) -> dict[str, Any]:
        recipient: dict[str, str] = {"email": message.to_address}
        if message.to_name:
            recipient["name"] = message.to_name
        payload: dict[str, Any] = {
            "personalizations": [{"to": [recipient]}],
            "from": {
                "email": message.from_address or self._from_address,
                "name": message.from_name or self._from_name,
            },
            "subject": message.subject,
            "content": [],
        }
        if message.text_body:
            payload["content"].append({"type": "text/plain", "value": message.text_body})
        if message.html_body:
            payload["content"].append({"type": "text/html", "value": message.html_body})
        if message.reply_to:
            payload["reply_to"] = {"email": message.reply_to}
        if message.headers:
            payload["headers"] = dict(message.headers)
        if message.metadata:
            payload["custom_args"] = {
                str(key): str(value) for key, value in message.metadata.items()
            }
        return payload

    async def parse_inbound(self, webhook_payload: Mapping[str, Any]) -> InboundMessage:
        headers = coerce_headers(webhook_payload.get("headers"))
        from_address, from_name = parse_address(
            webhook_payload.get("from") or webhook_payload.get("from_address")
        )
        to_address, to_name = parse_address(
            webhook_payload.get("to") or webhook_payload.get("to_address")
        )
        provider_message_id = str(
            webhook_payload.get("provider_message_id")
            or webhook_payload.get("message_id")
            or header_value(headers, "Message-Id")
            or ""
        ).strip()
        if provider_message_id == "":
            raise InvalidInboundEmail("inbound payload has no provider message id")

        subject = webhook_payload.get("subject")
        text_body = webhook_payload.get("text") or webhook_payload.get("text_body")
        html_body = webhook_payload.get("html") or webhook_payload.get("html_body")
        in_reply_to = (
            str(webhook_payload.get("in_reply_to") or "").strip()
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
            received_at=parse_received_at(webhook_payload.get("received_at")),
            headers=headers,
            raw=dict(webhook_payload),
        )

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        del body  # Inbound Parse authenticates the request, not the payload.
        if not self._webhook_secret:
            return False
        authorization = header_value(headers, "Authorization")
        if authorization is None:
            return False
        scheme, separator, token = authorization.partition(" ")
        if not separator or scheme.casefold() != "basic":
            return False
        try:
            decoded = base64.b64decode(token, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return False
        expected = f"{SENDGRID_INBOUND_USERNAME}:{self._webhook_secret}"
        return hmac.compare_digest(decoded, expected)
