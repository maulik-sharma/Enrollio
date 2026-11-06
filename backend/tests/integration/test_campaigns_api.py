"""Integration tests for segments, campaigns, and campaign APIs (M3.5)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Environment, Settings
from app.core.domain import (
    ApprovalStatus,
    EmailDirection,
    LifecycleStatus,
    MessageCategory,
    MessageChannel,
    TemplateStatus,
)
from app.main import create_app
from app.models.approval_item import ApprovalItem
from app.models.campaign import Campaign, CampaignRecipient
from app.models.campus import Campus
from app.models.lead import Lead
from app.models.lead_source import LeadSource
from app.models.message_template import MessageTemplate
from app.models.mock_email_message import MockEmailMessage
from app.models.programme import Programme
from app.models.student import Student
from app.repositories import users as users_repo
from tests.conftest import requires_postgres

pytestmark = [requires_postgres]

PASSWORD = "demo-password-123"
MANAGER = "manager@enrollio.dev"
COUNSELLOR = "counsellor@enrollio.dev"


def _api_settings(test_settings: Settings, **overrides: Any) -> Settings:
    """The shared API settings with M3.5-specific overrides."""
    data = test_settings.model_dump()
    data.update(
        {
            # Deterministic sends: quiet window disabled.
            "QUIET_HOURS_START_HOUR": 9,
            "QUIET_HOURS_END_HOUR": 9,
            "CAMPAIGN_SEND_MODE": "inline",
            "ENV": Environment.test,
            **overrides,
        },
    )
    return Settings(**data, _env_file=None)


@asynccontextmanager
async def api_client(
    app_settings: Settings,
) -> AsyncIterator[tuple[Settings, AsyncClient]]:
    app = create_app(app_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client,
    ):
        yield app_settings, client


async def _token(client: AsyncClient, email: str) -> str:
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_leads(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    count: int,
    assigned_to: uuid.UUID | None = None,
) -> list[uuid.UUID]:
    """Leads on the BTECH-CSE programme, Main Campus, Website source."""
    async with session_factory() as session:
        programme = await session.scalar(select(Programme).where(Programme.code == "BTECH-CSE"))
        campus = await session.scalar(select(Campus).where(Campus.name == "Main Campus"))
        source = await session.scalar(select(LeadSource).where(LeadSource.name == "Website"))
        assert programme is not None and campus is not None and source is not None

        ids: list[uuid.UUID] = []
        for index in range(count):
            student = Student(
                first_name=f"Lead{index}",
                last_name="Tester",
                email_normalised=f"lead{index}@example.com",
            )
            session.add(student)
            await session.flush()
            lead = Lead(
                student_id=student.id,
                programme_id=programme.id,
                campus_id=campus.id,
                source_id=source.id,
                admission_cycle="2026-fall",
                lifecycle_status=LifecycleStatus.NEW_ENQUIRY,
                assigned_counsellor_id=assigned_to,
            )
            session.add(lead)
            await session.flush()
            ids.append(lead.id)
        await session.commit()
        return ids


async def _seed_template(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str,
    subject: str,
    body: str,
    category: MessageCategory = MessageCategory.TRANSACTIONAL,
    approved: bool = True,
) -> uuid.UUID:
    async with session_factory() as session:
        template = MessageTemplate(
            name=name,
            channel=MessageChannel.EMAIL,
            category=category,
            subject=subject,
            body=body,
            status=TemplateStatus.APPROVED if approved else TemplateStatus.DRAFT,
        )
        session.add(template)
        await session.commit()
        return template.id


async def _counsellor_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> uuid.UUID:
    async with session_factory() as session:
        counsellor = await users_repo.get_by_email(session, COUNSELLOR)
        assert counsellor is not None
        return counsellor.id


async def _approval_items(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[ApprovalItem]:
    async with session_factory() as session:
        return list((await session.execute(select(ApprovalItem))).scalars())


async def test_segment_create_and_preview(
    clean_database: None,
    seeded_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    lead_ids = await _seed_leads(db_session_factory, count=3)
    async with api_client(_api_settings(test_settings)) as (_, client):
        token = await _token(client, MANAGER)
        response = await client.post(
            "/api/segments",
            headers=_auth(token),
            json={
                "name": "New enquiries",
                "filter_definition": {
                    "all": [{"field": "lifecycle_status", "op": "eq", "value": "new_enquiry"}],
                },
            },
        )
        assert response.status_code == 201, response.text
        segment = response.json()

        preview = await client.post(
            f"/api/segments/{segment['id']}/preview",
            headers=_auth(token),
        )
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body["total"] == 3
        assert {item["lead_id"] for item in body["sample"]} == {
            str(lead_id) for lead_id in lead_ids
        }
        assert body["sample"][0]["lifecycle_status"] == "new_enquiry"


async def test_segment_invalid_field_and_op_are_400(
    clean_database: None,
    seeded_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    async with api_client(_api_settings(test_settings)) as (_, client):
        token = await _token(client, MANAGER)

        bad_field = await client.post(
            "/api/segments",
            headers=_auth(token),
            json={
                "name": "Injection attempt",
                "filter_definition": {
                    "all": [{"field": "first_name; DROP TABLE leads", "op": "eq", "value": "x"}],
                },
            },
        )
        assert bad_field.status_code == 400
        assert "not filterable" in bad_field.json()["detail"]

        bad_op = await client.post(
            "/api/segments",
            headers=_auth(token),
            json={
                "name": "Bad operator",
                "filter_definition": {
                    "all": [{"field": "first_name", "op": "raw_sql", "value": "x"}],
                },
            },
        )
        assert bad_op.status_code == 400
        assert "not supported" in bad_op.json()["detail"]


async def test_counsellor_is_forbidden(
    clean_database: None,
    seeded_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    async with api_client(_api_settings(test_settings)) as (_, client):
        counsellor_token = await _token(client, COUNSELLOR)
        forbidden = await client.post(
            "/api/segments",
            headers=_auth(counsellor_token),
            json={"name": "Nope", "filter_definition": {"all": []}},
        )
        assert forbidden.status_code == 403

        manager_token = await _token(client, MANAGER)
        ok = await client.post(
            "/api/segments",
            headers=_auth(manager_token),
            json={"name": "Fine", "filter_definition": {"all": []}},
        )
        assert ok.status_code == 201


async def test_campaign_create_launch_inline_and_report(
    clean_database: None,
    seeded_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    await _seed_leads(db_session_factory, count=3)
    template_id = await _seed_template(
        db_session_factory,
        name="Welcome",
        subject="Welcome, {{first_name}}!",
        body="Hello {{first_name}}, you applied to {{programme}} at {{campus}}.",
    )
    async with api_client(_api_settings(test_settings)) as (settings, client):
        token = await _token(client, MANAGER)

        segment = (
            await client.post(
                "/api/segments",
                headers=_auth(token),
                json={
                    "name": "Everyone",
                    "filter_definition": {
                        "all": [
                            {"field": "lifecycle_status", "op": "eq", "value": "new_enquiry"},
                        ],
                    },
                },
            )
        ).json()
        response = await client.post(
            "/api/campaigns",
            headers=_auth(token),
            json={
                "name": "November welcome",
                "channel": "email",
                "template_id": str(template_id),
                "segment_id": segment["id"],
            },
        )
        assert response.status_code == 201, response.text
        campaign = response.json()
        assert campaign["status"] == "draft"

        launch = await client.post(
            f"/api/campaigns/{campaign['id']}/launch",
            headers=_auth(token),
        )
        assert launch.status_code == 200, launch.text
        result = launch.json()
        assert result["recipients_created"] == 3
        assert result["dispatch"] == "inline"
        assert result["status"] == "completed"
        assert result["approval_status"] is None

        report = await client.get(
            f"/api/campaigns/{campaign['id']}/report",
            headers=_auth(token),
        )
        assert report.status_code == 200
        body = report.json()
        assert body["total"] == 3
        assert body["by_status"] == {"sent": 3}
        assert body["reasons"] == {}

        # Every recipient produced one outbound message in the mock provider.
        async with db_session_factory() as session:
            outbound = (
                await session.execute(
                    select(func.count())
                    .select_from(MockEmailMessage)
                    .where(MockEmailMessage.direction == EmailDirection.OUTBOUND),
                )
            ).scalar_one()
            assert outbound == 3
            recipient_rows = list(
                (await session.execute(select(CampaignRecipient))).scalars(),
            )
            assert all(recipient.status.value == "sent" for recipient in recipient_rows)
            assert all(recipient.provider_message_id for recipient in recipient_rows)

        # Launching again is refused: a campaign is one-shot once launched.
        relaunch = await client.post(
            f"/api/campaigns/{campaign['id']}/launch",
            headers=_auth(token),
        )
        assert relaunch.status_code == 409


async def test_render_failure_marks_failed_others_sent(
    clean_database: None,
    seeded_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    counsellor = await _counsellor_id(db_session_factory)
    all_ids = await _seed_leads(db_session_factory, count=3)
    # Re-assign the first two leads to the counsellor so their context has a
    # counsellor name; the third stays unassigned and must fail rendering.
    async with db_session_factory() as session:
        for lead_id in all_ids[:2]:
            lead = await session.get(Lead, lead_id)
            assert lead is not None
            lead.assigned_counsellor_id = counsellor
        await session.commit()

    template_id = await _seed_template(
        db_session_factory,
        name="Counsellor intro",
        subject="Hi {{first_name}}",
        body="Your counsellor is {{counsellor_name}}.",
    )
    async with api_client(_api_settings(test_settings)) as (_, client):
        token = await _token(client, MANAGER)
        segment = (
            await client.post(
                "/api/segments",
                headers=_auth(token),
                json={
                    "name": "Assigned-or-not",
                    "filter_definition": {
                        "all": [
                            {"field": "lifecycle_status", "op": "eq", "value": "new_enquiry"},
                        ],
                    },
                },
            )
        ).json()
        campaign = (
            await client.post(
                "/api/campaigns",
                headers=_auth(token),
                json={
                    "name": "Counsellor intros",
                    "channel": "email",
                    "template_id": str(template_id),
                    "segment_id": segment["id"],
                },
            )
        ).json()
        launch = await client.post(
            f"/api/campaigns/{campaign['id']}/launch",
            headers=_auth(token),
        )
        assert launch.status_code == 200, launch.text
        assert launch.json()["recipients_created"] == 3

        report = (
            await client.get(
                f"/api/campaigns/{campaign['id']}/report",
                headers=_auth(token),
            )
        ).json()
        assert report["by_status"] == {"sent": 2, "failed": 1}
        assert report["reasons"] == {"missing_field: counsellor_name": 1}


async def test_threshold_requires_approval_then_allows_approved_launch(
    clean_database: None,
    seeded_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    await _seed_leads(db_session_factory, count=3)
    template_id = await _seed_template(
        db_session_factory,
        name="Bulk",
        subject="Hi {{first_name}}",
        body="A quick update for {{programme}}.",
    )
    settings = _api_settings(test_settings, CAMPAIGN_LAUNCH_APPROVAL_THRESHOLD=2)
    async with api_client(settings) as (_, client):
        token = await _token(client, MANAGER)
        segment = (
            await client.post(
                "/api/segments",
                headers=_auth(token),
                json={
                    "name": "Bulk audience",
                    "filter_definition": {
                        "all": [
                            {"field": "lifecycle_status", "op": "eq", "value": "new_enquiry"},
                        ],
                    },
                },
            )
        ).json()
        campaign = (
            await client.post(
                "/api/campaigns",
                headers=_auth(token),
                json={
                    "name": "Threshold campaign",
                    "channel": "email",
                    "template_id": str(template_id),
                    "segment_id": segment["id"],
                },
            )
        ).json()
        launch = await client.post(
            f"/api/campaigns/{campaign['id']}/launch",
            headers=_auth(token),
        )
        assert launch.status_code == 200, launch.text
        result = launch.json()
        assert result["approval_status"] == "pending"
        assert result["recipients_created"] == 0
        assert result["dispatch"] is None

        report = (
            await client.get(
                f"/api/campaigns/{campaign['id']}/report",
                headers=_auth(token),
            )
        ).json()
        assert report["total"] == 0

        items = await _approval_items(db_session_factory)
        assert len(items) == 1
        assert items[0].item_type == "campaign_launch"
        assert items[0].payload["campaign_id"] == campaign["id"]

        # An approved campaign may launch through the same endpoint.
        from sqlalchemy import update

        async with db_session_factory() as session:
            await session.execute(
                update(Campaign)
                .where(Campaign.id == uuid.UUID(campaign["id"]))
                .values(approval_status=ApprovalStatus.APPROVED),
            )
            await session.commit()

        second = await client.post(
            f"/api/campaigns/{campaign['id']}/launch",
            headers=_auth(token),
        )
        assert second.status_code == 200, second.text
        approved_result = second.json()
        assert approved_result["recipients_created"] == 3
        assert approved_result["status"] == "completed"

        final_report = (
            await client.get(
                f"/api/campaigns/{campaign['id']}/report",
                headers=_auth(token),
            )
        ).json()
        assert final_report["by_status"] == {"sent": 3}


async def test_launch_invalid_template_and_unknown_campaign(
    clean_database: None,
    seeded_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    await _seed_leads(db_session_factory, count=1)
    draft_template = await _seed_template(
        db_session_factory,
        name="Draft",
        subject="{{first_name}}",
        body="hi",
        approved=False,
    )
    async with api_client(_api_settings(test_settings)) as (_, client):
        token = await _token(client, MANAGER)
        segment = (
            await client.post(
                "/api/segments",
                headers=_auth(token),
                json={"name": "S", "filter_definition": {"all": []}},
            )
        ).json()
        campaign = (
            await client.post(
                "/api/campaigns",
                headers=_auth(token),
                json={
                    "name": "Draft template campaign",
                    "channel": "email",
                    "template_id": str(draft_template),
                    "segment_id": segment["id"],
                },
            )
        ).json()
        response = await client.post(
            f"/api/campaigns/{campaign['id']}/launch",
            headers=_auth(token),
        )
        assert response.status_code == 409
        assert "not approved" in response.json()["detail"]

        missing = await client.post(
            f"/api/campaigns/{uuid.uuid4()!s}/launch",
            headers=_auth(token),
        )
        assert missing.status_code == 404


async def test_campaign_preview_renders_and_reports_missing_fields(
    clean_database: None,
    seeded_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    await _seed_leads(db_session_factory, count=2)
    ok_template = await _seed_template(
        db_session_factory,
        name="Preview ok",
        subject="Hi {{first_name}}",
        body="Programme: {{programme}}",
    )
    missing_template = await _seed_template(
        db_session_factory,
        name="Preview broken",
        subject="Deadline",
        body="Deadline: {{deadline}}",
    )
    async with api_client(_api_settings(test_settings)) as (settings, client):
        token = await _token(client, MANAGER)
        segment = (
            await client.post(
                "/api/segments",
                headers=_auth(token),
                json={"name": "Preview", "filter_definition": {"all": []}},
            )
        ).json()

        good = await client.post(
            "/api/campaigns",
            headers=_auth(token),
            json={
                "name": "Good campaign",
                "channel": "email",
                "template_id": str(ok_template),
                "segment_id": segment["id"],
            },
        )
        assert good.status_code == 201
        preview = await client.post(
            f"/api/campaigns/{good.json()['id']}/preview",
            headers=_auth(token),
        )
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert len(body["sample"]) == 2
        assert {item["subject"] for item in body["sample"]} == {"Hi Lead0", "Hi Lead1"}
        for item in body["sample"]:
            assert "B.Tech Computer Science" in item["text_body"]
            assert item["html_body"].startswith("<html><body>")

        broken = await client.post(
            "/api/campaigns",
            headers=_auth(token),
            json={
                "name": "Broken campaign",
                "channel": "email",
                "template_id": str(missing_template),
                "segment_id": segment["id"],
            },
        )
        assert broken.status_code == 201
        broken_preview = await client.post(
            f"/api/campaigns/{broken.json()['id']}/preview",
            headers=_auth(token),
        )
        assert broken_preview.status_code == 422
        assert "missing values: deadline" in broken_preview.json()["detail"]

        unknown = await client.post(
            f"/api/campaigns/{uuid.uuid4()!s}/preview",
            headers=_auth(token),
        )
        assert unknown.status_code == 404


async def test_campaign_channel_mismatch_is_422(
    clean_database: None,
    seeded_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    async with api_client(_api_settings(test_settings)) as (_, client):
        token = await _token(client, MANAGER)
        template_id = await _seed_template(
            db_session_factory,
            name="Email only",
            subject="{{first_name}}",
            body="hi",
        )
        segment = (
            await client.post(
                "/api/segments",
                headers=_auth(token),
                json={"name": "Chan", "filter_definition": {"all": []}},
            )
        ).json()
        whatsapp = await client.post(
            "/api/campaigns",
            headers=_auth(token),
            json={
                "name": "Not yet",
                "channel": "whatsapp",
                "template_id": str(template_id),
                "segment_id": segment["id"],
            },
        )
        assert whatsapp.status_code == 422
        assert "Phase 2" in whatsapp.json()["detail"]


async def test_report_unknown_campaign_is_404(
    clean_database: None,
    seeded_database: None,
    db_session_factory: async_sessionmaker[AsyncSession],
    test_settings: Settings,
) -> None:
    async with api_client(_api_settings(test_settings)) as (_, client):
        token = await _token(client, MANAGER)
        report = await client.get(
            f"/api/campaigns/{uuid.uuid4()!s}/report",
            headers=_auth(token),
        )
        assert report.status_code == 404
