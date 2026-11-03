"""Provider-neutral email contracts (M3.1).

Business code depends on this module, never on a vendor SDK or HTTP shape. The
mock adapter is the default; real adapters live beside it and are selected only
when their settings are present.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parseaddr
from typing import Any, Protocol


class EmailError(RuntimeError):
    """Base class for email provider failures."""


class EmailNotConfigured(EmailError):
    """The selected provider has no usable adapter or credentials."""


class InvalidInboundEmail(EmailError):
    """A webhook payload does not contain the fields an inbound message needs."""


class EmailDeliveryError(EmailError):
    """A provider rejected or failed to accept a message."""


@dataclass(frozen=True, slots=True)
class EmailMessage:
    """An outbound message, independent of the provider that sends it."""

    to_address: str
    subject: str
    text_body: str | None = None
    to_name: str | None = None
    from_address: str | None = None
    from_name: str | None = None
    html_body: str | None = None
    reply_to: str | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.to_address.strip():
            raise ValueError("to_address is required")
        if not self.text_body and not self.html_body:
            raise ValueError("a text or HTML body is required")


@dataclass(frozen=True, slots=True)
class InboundMessage:
    """A normalised inbound email parsed from a provider webhook."""

    provider_message_id: str
    from_address: str
    to_address: str
    subject: str | None = None
    text_body: str | None = None
    html_body: str | None = None
    from_name: str | None = None
    to_name: str | None = None
    in_reply_to: str | None = None
    received_at: datetime | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict)


class EmailProvider(Protocol):
    """The only email surface business code may call."""

    async def send(self, message: EmailMessage) -> str:
        """Send a message and return the provider's message id."""
        ...

    async def parse_inbound(self, webhook_payload: Mapping[str, Any]) -> InboundMessage:
        """Normalise a provider webhook payload into an inbound message."""
        ...

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        """Return True when the webhook signature/authenticity check passes."""
        ...


def parse_address(value: object) -> tuple[str, str | None]:
    """Return ``(address, display_name)`` from a string or mapping value."""
    if isinstance(value, Mapping):
        address = str(value.get("email") or value.get("address") or "").strip()
        name = value.get("name")
        if address == "":
            raise InvalidInboundEmail("address is missing an email")
        display = str(name).strip() if name is not None else ""
        return address, display or None

    text = str(value or "").strip()
    if text == "":
        raise InvalidInboundEmail("address is missing an email")
    name, address = parseaddr(text)
    if address == "":
        # Some providers send a bare address that parseaddr still understands.
        address = text
    if "@" not in address:
        raise InvalidInboundEmail("address is not an email")
    return address, name.strip() or None


def coerce_headers(value: object) -> dict[str, str]:
    """Normalise provider headers that arrive as a mapping or a JSON string."""
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return {str(key): str(item) for key, item in value.items()}
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return {}
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, Mapping):
            return {str(key): str(item) for key, item in parsed.items()}
        headers: dict[str, str] = {}
        for line in stripped.splitlines():
            key, separator, item = line.partition(":")
            if separator:
                headers[key.strip()] = item.strip()
        return headers
    return {}


def header_value(headers: Mapping[str, str], name: str) -> str | None:
    """Read a header case-insensitively."""
    wanted = name.casefold()
    for key, value in headers.items():
        if key.casefold() == wanted:
            return value
    return None


def parse_received_at(value: object) -> datetime | None:
    """Parse an ISO timestamp, treating naive values as UTC."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise InvalidInboundEmail("received_at is not an ISO timestamp") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
