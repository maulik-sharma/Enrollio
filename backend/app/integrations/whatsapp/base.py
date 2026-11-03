"""WhatsApp provider contract (M3 stub).

M3 defines the interface so later code can depend on it, but the Cloud API
implementation belongs to Phase 2. Every method raises until then.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


class WhatsAppError(RuntimeError):
    """Base class for WhatsApp provider failures."""


class WhatsAppNotImplemented(WhatsAppError):
    """Raised by the M3 stub; the real adapter arrives in Phase 2."""


@dataclass(frozen=True, slots=True)
class WhatsAppMessage:
    """An outbound WhatsApp message."""

    to_number: str
    text_body: str | None = None
    template_name: str | None = None
    template_parameters: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.text_body is None and self.template_name is None:
            raise ValueError("a text body or a template name is required")


@dataclass(frozen=True, slots=True)
class InboundWhatsAppMessage:
    """A normalised inbound WhatsApp message."""

    provider_message_id: str
    from_number: str
    to_number: str
    text_body: str | None = None
    received_at: datetime | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict)


class WhatsAppProvider(Protocol):
    """The WhatsApp surface business code may call from Phase 2 onward."""

    async def send(self, message: WhatsAppMessage) -> str: ...

    async def parse_inbound(self, webhook_payload: Mapping[str, Any]) -> InboundWhatsAppMessage: ...

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool: ...
