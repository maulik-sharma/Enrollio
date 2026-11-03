"""Select the configured WhatsApp provider."""

from __future__ import annotations

from app.integrations.whatsapp.base import WhatsAppProvider
from app.integrations.whatsapp.stub import StubWhatsAppProvider


def build_whatsapp_provider() -> WhatsAppProvider:
    """Return the M3 stub; the Cloud API adapter arrives in Phase 2."""
    return StubWhatsAppProvider()
