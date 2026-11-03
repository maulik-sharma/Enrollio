"""Contract tests for the email provider surface and mock helpers."""

from __future__ import annotations

import base64
import json
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.domain import EmailDirection
from app.integrations.email.base import (
    EmailDeliveryError,
    EmailMessage,
    EmailProvider,
    InboundMessage,
    InvalidInboundEmail,
)
from app.integrations.email.mock import (
    MockEmailProvider,
    UnknownMockEmailMessage,
    sign_mock_webhook,
)
from app.integrations.email.sendgrid import (
    SENDGRID_API_URL,
    SendGridEmailProvider,
)
from app.models.mock_email_message import MockEmailMessage
from tests.conftest import requires_postgres

pytestmark = [requires_postgres]

RECIPIENT = "contract.student@example.com"
SUBJECT = "Your admission enquiry"
TEXT_BODY = "Hello from the contract suite."
WEBHOOK_SECRET = "webhook-contract-secret"


@dataclass
class ContractHarness:
    provider: EmailProvider
    sign: Callable[[bytes], dict[str, str]]
    sent_ids: Callable[[], Awaitable[list[str]]]
    requests: list[httpx.Request] = field(default_factory=list)


def _basic_auth(secret: str) -> dict[str, str]:
    token = base64.b64encode(f"sendgrid:{secret}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _inbound_payload(
    *,
    message_id: str = "<inbound-1@example.com>",
    in_reply_to: str = "<sent-1@example.com>",
) -> dict[str, object]:
    return {
        "from": "Asha Rao <asha@example.com>",
        "to": "reply+token@example.com",
        "subject": "Re: Your admission enquiry",
        "text": "I would like to book a counselling call.",
        "html": "<p>I would like to book a counselling call.</p>",
        "headers": json.dumps({"Message-Id": message_id, "In-Reply-To": in_reply_to}),
        "received_at": "2026-11-03T10:00:00Z",
    }


@pytest.fixture(params=["mock", "sendgrid"])
async def contract(
    request: pytest.FixtureRequest,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[ContractHarness]:
    if request.param == "mock":
        mock_provider = MockEmailProvider(
            db_session_factory,
            from_address="no-reply@enrollio.dev",
            from_name="Enrollio",
            webhook_secret=WEBHOOK_SECRET,
        )

        async def mock_sent_ids() -> list[str]:
            async with db_session_factory() as session:
                rows = await session.execute(
                    select(MockEmailMessage).where(MockEmailMessage.to_address == RECIPIENT)
                )
                return [
                    row.provider_message_id
                    for row in rows.scalars()
                    if row.direction is EmailDirection.OUTBOUND
                ]

        yield ContractHarness(
            provider=mock_provider,
            sign=lambda body: sign_mock_webhook(WEBHOOK_SECRET, body),
            sent_ids=mock_sent_ids,
        )
        return

    issued: list[str] = []
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        message_id = f"sendgrid-{len(issued) + 1}@example.com"
        issued.append(message_id)
        return httpx.Response(202, headers={"X-Message-Id": message_id})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    sendgrid_provider = SendGridEmailProvider(
        "SG.contract-test",
        from_address="no-reply@enrollio.dev",
        from_name="Enrollio",
        webhook_secret=WEBHOOK_SECRET,
        client=client,
    )

    async def sendgrid_sent_ids() -> list[str]:
        return list(issued)

    try:
        yield ContractHarness(
            provider=sendgrid_provider,
            sign=lambda _body: _basic_auth(WEBHOOK_SECRET),
            sent_ids=sendgrid_sent_ids,
            requests=requests,
        )
    finally:
        await client.aclose()


async def test_send_returns_a_provider_message_id_and_records_it(
    contract: ContractHarness,
) -> None:
    message_id = await contract.provider.send(
        EmailMessage(
            to_address=RECIPIENT,
            to_name="Contract Student",
            subject=SUBJECT,
            text_body=TEXT_BODY,
            metadata={"lead_id": "lead-1"},
        )
    )
    assert message_id
    assert message_id in await contract.sent_ids()


async def test_parse_inbound_normalises_the_shared_payload(
    contract: ContractHarness,
) -> None:
    inbound = await contract.provider.parse_inbound(_inbound_payload())
    assert isinstance(inbound, InboundMessage)
    assert inbound.provider_message_id == "<inbound-1@example.com>"
    assert inbound.from_address == "asha@example.com"
    assert inbound.from_name == "Asha Rao"
    assert inbound.to_address == "reply+token@example.com"
    assert inbound.subject == "Re: Your admission enquiry"
    assert inbound.text_body is not None
    assert inbound.in_reply_to == "<sent-1@example.com>"
    assert inbound.received_at is not None
    assert inbound.received_at.tzinfo is not None


async def test_verify_webhook_rejects_unsigned_and_accepts_signed(
    contract: ContractHarness,
) -> None:
    body = b'{"event":"inbound"}'
    assert not contract.provider.verify_webhook({}, body)
    assert contract.provider.verify_webhook(contract.sign(body), body)


def test_mock_signature_is_bound_to_the_body() -> None:
    provider = MockEmailProvider(_never_used_session_factory(), webhook_secret="secret")
    headers = sign_mock_webhook("secret", b"one")
    assert provider.verify_webhook(headers, b"one")
    assert not provider.verify_webhook(headers, b"two")


def test_sendgrid_rejects_a_tampered_basic_auth_header() -> None:
    provider = SendGridEmailProvider(
        "SG.test",
        from_address="no-reply@enrollio.dev",
        webhook_secret="secret",
    )
    assert provider.verify_webhook(_basic_auth("wrong"), b"{}") is False
    assert provider.verify_webhook(_basic_auth("secret"), b"{}") is True


async def test_mock_helpers_capture_inbound_and_delivery_events(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = MockEmailProvider(db_session_factory, webhook_secret="secret")
    sent_id = await provider.send(
        EmailMessage(
            to_address=RECIPIENT,
            subject=SUBJECT,
            text_body=TEXT_BODY,
        )
    )
    await provider.simulate_delivery_event(sent_id, "delivered")
    inbound = await provider.simulate_inbound_reply(
        _inbound_payload(
            message_id=f"<reply-{uuid.uuid4()}@example.com>",
            in_reply_to=sent_id,
        )
    )
    assert inbound.in_reply_to == sent_id

    async with db_session_factory() as session:
        original = await session.scalar(
            select(MockEmailMessage).where(MockEmailMessage.provider_message_id == sent_id)
        )
        reply = await session.scalar(
            select(MockEmailMessage).where(
                MockEmailMessage.provider_message_id == inbound.provider_message_id
            )
        )
    assert original is not None
    assert original.status == "replied"
    assert reply is not None
    assert reply.direction is EmailDirection.INBOUND
    assert reply.status == "received"

    with pytest.raises(UnknownMockEmailMessage):
        await provider.simulate_delivery_event("mock-missing", "delivered")
    with pytest.raises(ValueError):
        await provider.simulate_delivery_event(sent_id, "not-a-real-event")


async def test_mock_rejects_a_second_capture_of_the_same_inbound_id(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider = MockEmailProvider(db_session_factory, webhook_secret="secret")
    payload = _inbound_payload(message_id=f"<duplicate-{uuid.uuid4()}@example.com>")
    await provider.simulate_inbound_reply(payload)
    with pytest.raises(InvalidInboundEmail):
        await provider.simulate_inbound_reply(payload)


async def test_sendgrid_posts_the_v3_payload_and_rejects_errors() -> None:
    sent: list[httpx.Request] = []

    def accepted(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(202, headers={"X-Message-Id": "sg-accepted@example.com"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(accepted))
    provider = SendGridEmailProvider(
        "SG.test",
        from_address="no-reply@enrollio.dev",
        from_name="Enrollio",
        client=client,
    )
    try:
        message_id = await provider.send(
            EmailMessage(
                to_address=RECIPIENT,
                to_name="Contract Student",
                subject=SUBJECT,
                text_body=TEXT_BODY,
                html_body="<p>Hello</p>",
                reply_to="reply@enrollio.dev",
                metadata={"lead_id": "lead-1"},
            )
        )
    finally:
        await client.aclose()

    assert message_id == "sg-accepted@example.com"
    request = sent[0]
    assert request.url == httpx.URL(SENDGRID_API_URL)
    assert request.headers["Authorization"] == "Bearer SG.test"
    raw = request.read().decode()
    body = json.loads(raw)
    assert RECIPIENT in raw
    assert body["custom_args"] == {"lead_id": "lead-1"}
    assert body["content"][0]["type"] == "text/plain"
    assert body["content"][1]["type"] == "text/html"

    def rejected(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"errors": [{"message": "bad"}]})

    failing_client = httpx.AsyncClient(transport=httpx.MockTransport(rejected))
    failing_provider = SendGridEmailProvider(
        "SG.test", from_address="no-reply@enrollio.dev", client=failing_client
    )
    try:
        with pytest.raises(EmailDeliveryError):
            await failing_provider.send(
                EmailMessage(to_address=RECIPIENT, subject=SUBJECT, text_body=TEXT_BODY)
            )
    finally:
        await failing_client.aclose()


@pytest.mark.skipif(
    not os.getenv("EMAIL_API_KEY") or not os.getenv("EMAIL_CONTRACT_TO"),
    reason="Set EMAIL_API_KEY and EMAIL_CONTRACT_TO to run the live SendGrid check",
)
async def test_live_sendgrid_send() -> None:
    provider = SendGridEmailProvider(
        os.environ["EMAIL_API_KEY"],
        from_address=os.getenv("EMAIL_FROM_ADDRESS", "no-reply@enrollio.dev"),
        from_name=os.getenv("EMAIL_FROM_NAME", "Enrollio"),
    )
    message_id = await provider.send(
        EmailMessage(
            to_address=os.environ["EMAIL_CONTRACT_TO"],
            subject="Enrollio provider contract",
            text_body="This is an opt-in SendGrid contract test.",
        )
    )
    assert message_id


def _never_used_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker[AsyncSession]()
