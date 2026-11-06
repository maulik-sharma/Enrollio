"""Campaign endpoints: create, preview, launch, and report (M3.5)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.deps import CurrentUserDep, SessionDep, SettingsDep, require_permission
from app.core.domain import MessageChannel
from app.core.permissions import PermissionName
from app.integrations.whatsapp.base import WhatsAppNotImplemented
from app.repositories import campaigns as campaigns_repo
from app.schemas.campaigns import (
    CampaignCreate,
    CampaignLaunchResult,
    CampaignPreview,
    CampaignPreviewItem,
    CampaignRead,
    CampaignReportItem,
)
from app.services import campaigns as campaigns_service
from app.services import segments as segments_service
from app.services.segments import SegmentFilterError
from app.services.templates import TemplateRenderError

if TYPE_CHECKING:
    from app.models.campaign import Campaign

router = APIRouter(
    prefix="/api/campaigns",
    tags=["campaigns"],
    dependencies=[Depends(require_permission(PermissionName.CAMPAIGNS_MANAGE))],
)


async def _load_campaign_or_404(
    session: SessionDep,
    campaign_id: uuid.UUID,
) -> Campaign:
    campaign = await campaigns_repo.get_campaign(session, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    return campaign


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreate,
    session: SessionDep,
    user: CurrentUserDep,
) -> CampaignRead:
    """Create a draft campaign from a template and a saved segment."""
    try:
        campaign = await campaigns_service.create_campaign(
            session,
            name=payload.name,
            channel=MessageChannel(payload.channel),
            template_id=payload.template_id,
            segment_id=payload.segment_id,
            created_by=user.id,
            scheduled_at=payload.scheduled_at,
        )
    except campaigns_service.CampaignError as exc:
        # Template/segment missing -> 404; invalid combinations -> 422.
        if isinstance(exc, campaigns_service.TemplateNotFound | campaigns_service.SegmentNotFound):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except WhatsAppNotImplemented as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    await session.commit()
    return CampaignRead.model_validate(campaign)


@router.post("/{campaign_id}/preview", response_model=CampaignPreview)
async def preview_campaign(
    campaign_id: uuid.UUID,
    session: SessionDep,
    settings: SettingsDep,
    sample_size: int = Query(default=3, ge=1, le=10),
) -> CampaignPreview:
    """Render the template against sampled segment leads.

    Every sampled lead must render fully; missing fields are a 422 that
    lists them (AC5.2), so a broken template cannot reach a launch unnoticed
    by the preview the wizard shows.
    """
    campaign = await _load_campaign_or_404(session, campaign_id)
    try:
        statement = segments_service.build_statement(
            campaign.segment.filter_definition,
        ).limit(sample_size)
        leads = [lead for lead in await session.scalars(statement)]
    except SegmentFilterError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc
    if not leads:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The campaign's segment matched no leads to preview",
        )
    items: list[CampaignPreviewItem] = []
    for lead in leads:
        try:
            subject, text_body, html_body = campaigns_service.render_for_lead(
                campaign.template,
                lead,
                unsubscribe_url=settings.UNSUBSCRIBE_URL,
            )
        except TemplateRenderError as exc:
            missing = ", ".join(sorted(exc.missing))
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Template cannot be rendered: missing values: {missing}",
            ) from exc
        items.append(
            CampaignPreviewItem(
                lead_id=lead.id,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            ),
        )
    return CampaignPreview(campaign_id=campaign.id, sample=items)


@router.post("/{campaign_id}/launch", response_model=CampaignLaunchResult)
async def launch_campaign(
    campaign_id: uuid.UUID,
    request: Request,
    settings: SettingsDep,
) -> CampaignLaunchResult:
    """Snapshot the segment and dispatch (or park for approval) the launch.

    Launches above ``CAMPAIGN_LAUNCH_APPROVAL_THRESHOLD`` without a prior
    approval return ``approval_status=pending`` and send nothing.
    """
    factory = request.app.state.db_session_factory
    try:
        outcome = await campaigns_service.launch_campaign(
            factory,
            settings,
            campaign_id=campaign_id,
        )
    except campaigns_service.CampaignNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        ) from exc
    except campaigns_service.InvalidCampaign as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return CampaignLaunchResult(
        status=outcome.status,
        approval_status=outcome.approval_status,
        recipients_created=outcome.recipients_created,
        dispatch=outcome.dispatch,
        approval_threshold=outcome.approval_threshold,
    )


@router.get("/{campaign_id}/report", response_model=CampaignReportItem)
async def campaign_report(
    campaign_id: uuid.UUID,
    session: SessionDep,
) -> CampaignReportItem:
    """Per-recipient status counts and a reason breakdown."""
    try:
        report = await campaigns_service.campaign_report(session, campaign_id)
    except campaigns_service.CampaignNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        ) from exc
    return CampaignReportItem(
        total=report.total,
        by_status=report.by_status,
        reasons=report.reasons,
    )
