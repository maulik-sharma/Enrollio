"""M3 placeholder WhatsApp adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.integrations.whatsapp.base import (
    InboundWhatsAppMessage,
    WhatsAppMessage,
    WhatsAppNotImplemented,
)


class StubWhatsAppProvider:
    """Fail loudly until the Cloud API adapter lands in Phase 2."""

    async def send(self, message: WhatsAppMessage) -> str:
        del message
        raise WhatsAppNotImplemented("WhatsApp sending is implemented in Phase 2")

    async def parse_inbound(self, webhook_payload: Mapping[str, Any]) -> InboundWhatsAppMessage:
        del webhook_payload
        raise WhatsAppNotImplemented("WhatsApp inbound parsing is implemented in Phase 2")

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        del headers, body
        raise WhatsAppNotImplemented("WhatsApp webhooks are implemented in Phase 2")
