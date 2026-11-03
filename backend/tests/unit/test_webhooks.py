"""Webhook HMAC signature helpers."""

from __future__ import annotations

from app.core.webhooks import sign_webhook, verify_webhook_signature

SECRET = "test-webhook-secret"


def test_valid_signature_for_bytes_and_text() -> None:
    payload = b'{"event":"lead.created"}'
    signature = sign_webhook(payload, SECRET, timestamp=1_800_000_000)

    assert verify_webhook_signature(
        payload,
        signature,
        SECRET,
        now=1_800_000_010,
    )
    assert verify_webhook_signature(
        payload.decode(),
        signature,
        SECRET,
        now=1_800_000_010,
    )


def test_tampering_wrong_secret_and_stale_timestamp_fail() -> None:
    payload = b'{"event":"lead.created"}'
    signature = sign_webhook(payload, SECRET, timestamp=1_800_000_000)

    assert not verify_webhook_signature(
        b'{"event":"lead.deleted"}',
        signature,
        SECRET,
        now=1_800_000_010,
    )
    assert not verify_webhook_signature(
        payload,
        signature,
        "wrong-secret",
        now=1_800_000_010,
    )
    assert not verify_webhook_signature(
        payload,
        signature,
        SECRET,
        now=1_800_000_000 + 301,
    )


def test_malformed_signatures_are_rejected() -> None:
    payload = b"{}"

    assert not verify_webhook_signature(payload, "", SECRET, now=1_800_000_000)
    assert not verify_webhook_signature(payload, "t=no,v1=bad", SECRET, now=1_800_000_000)
    assert not verify_webhook_signature(payload, "v1=" + "a" * 64, SECRET)
