"""Deterministic, database-backed email provider for development and tests."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.domain import EmailDirection
from app.integrations.email.base import (
    EmailDeliveryError,
    EmailError,
    EmailMessage,
    InboundMessage,
    InvalidInboundEmail,
    coerce_headers,
    header_value,
    parse_address,
    parse_received_at,
)
from app.models.mock_email_message import MockEmailMessage
from app.repositories import email_mock as email_mock_repo

MOCK_SIGNATURE_HEADER = "X-Mock-Signature"
MOCK_DELIVERY_EVENTS: frozenset[str] = frozenset(
    {"delivered", "opened", "clicked", "bounced", "complained", "deferred"}
)


class UnknownMockEmailMessage(EmailError):
    """A delivery event referenced a message the mock never sent."""


def sign_mock_webhook(secret: str, body: bytes) -> dict[str, str]:
    """Return the header a mock webhook caller must send for ``body``."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return {MOCK_SIGNATURE_HEADER: f"sha256={digest}"}


class MockEmailProvider:
    """Store sends and inbound replies in Postgres instead of calling a vendor.

    The provider is deliberately deterministic: message ids are random UUIDs,
    sends always succeed, and inbound/delivery helpers can be driven directly by
    tests. Downstream services depend on the ``EmailProvider`` protocol, not on
    this class.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        from_address: str = "no-reply@enrollio.dev",
        from_name: str = "Enrollio",
        webhook_secret: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._from_address = from_address
        self._from_name = from_name
        self._webhook_secret = webhook_secret

    async def send(self, message: EmailMessage) -> str:
        provider_message_id = f"mock-{uuid.uuid4()}"
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            session.add(
                MockEmailMessage(
                    direction=EmailDirection.OUTBOUND,
                    provider_message_id=provider_message_id,
                    from_address=message.from_address or self._from_address,
                    from_name=message.from_name or self._from_name,
                    to_address=message.to_address,
                    to_name=message.to_name,
                    subject=message.subject,
                    text_body=message.text_body,
                    html_body=message.html_body,
                    status="sent",
                    last_event_at=now,
                )
            )
            await session.commit()
        return provider_message_id

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
        if not self._webhook_secret:
            return False
        signature = header_value(headers, MOCK_SIGNATURE_HEADER)
        if signature is None:
            return False
        expected = sign_mock_webhook(self._webhook_secret, body)[MOCK_SIGNATURE_HEADER]
        return hmac.compare_digest(signature, expected)

    async def simulate_inbound_reply(self, webhook_payload: Mapping[str, Any]) -> InboundMessage:
        """Parse, validate, and store an inbound reply for the next test step."""
        inbound = await self.parse_inbound(webhook_payload)
        occurred_at = inbound.received_at or datetime.now(UTC)
        async with self._session_factory() as session:
            if (
                await email_mock_repo.get_by_provider_id(session, inbound.provider_message_id)
                is not None
            ):
                raise InvalidInboundEmail("inbound message was already captured")
            session.add(
                MockEmailMessage(
                    direction=EmailDirection.INBOUND,
                    provider_message_id=inbound.provider_message_id,
                    from_address=inbound.from_address,
                    from_name=inbound.from_name,
                    to_address=inbound.to_address,
                    to_name=inbound.to_name,
                    subject=inbound.subject,
                    text_body=inbound.text_body,
                    html_body=inbound.html_body,
                    status="received",
                    in_reply_to=inbound.in_reply_to,
                    last_event_at=occurred_at,
                )
            )
            if inbound.in_reply_to is not None:
                original = await email_mock_repo.get_by_provider_id(session, inbound.in_reply_to)
                if original is not None and original.direction is EmailDirection.OUTBOUND:
                    original.status = "replied"
                    original.last_event_at = occurred_at
            await session.commit()
        return inbound

    async def simulate_delivery_event(
        self,
        provider_message_id: str,
        event_type: str,
        *,
        occurred_at: datetime | None = None,
    ) -> MockEmailMessage:
        """Mark one outbound message with a provider delivery event."""
        event = event_type.strip().lower()
        if event not in MOCK_DELIVERY_EVENTS:
            raise ValueError(f"unsupported mock delivery event: {event_type}")
        async with self._session_factory() as session:
            message = await email_mock_repo.get_by_provider_id(session, provider_message_id)
            if message is None or message.direction is not EmailDirection.OUTBOUND:
                raise UnknownMockEmailMessage(
                    "delivery event references an unknown outbound message"
                )
            message.status = event
            message.last_event_at = occurred_at or datetime.now(UTC)
            await session.commit()
            await session.refresh(message)
        return message


__all__ = [
    "MOCK_DELIVERY_EVENTS",
    "MOCK_SIGNATURE_HEADER",
    "EmailDeliveryError",
    "MockEmailProvider",
    "UnknownMockEmailMessage",
    "sign_mock_webhook",
]
