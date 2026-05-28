from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_db
from app.models.ad_campaign import AdCampaign, AdCampaignStatus
from app.models.admin_account import AdminAccount
from app.services.ad_broadcast import AdBroadcastService

router = APIRouter(prefix="/api/admin/ad-broadcasts", tags=["admin-ad-broadcasts"])


class AdCampaignCreate(BaseModel):
    title: str
    body: str | None = None
    image_path: str | None = None
    send_now: bool = False
    send_at: datetime | None = None


class AdCampaignResponse(BaseModel):
    id: UUID
    title: str
    body: str | None
    image_path: str | None
    status: AdCampaignStatus
    send_at: datetime | None
    sent_at: datetime | None
    recipients_total: int
    delivered: int
    errors: int
    created_at: datetime


def _to_response(c: AdCampaign) -> AdCampaignResponse:
    return AdCampaignResponse(
        id=c.id,
        title=c.title,
        body=c.body,
        image_path=c.image_path,
        status=c.status,
        send_at=c.send_at,
        sent_at=c.sent_at,
        recipients_total=c.recipients_total,
        delivered=c.delivered,
        errors=c.errors,
        created_at=c.created_at,
    )


@router.post("", response_model=AdCampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_ad_campaign(
    payload: AdCampaignCreate,
    request: Request,
    admin: AdminAccount = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Создать рекламную рассылку. send_now → отправить сразу всем;
    send_at → запланировать (отправит планировщик); иначе — черновик."""
    title = payload.title.strip()
    if not title:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "title required")

    campaign = AdCampaign(
        title=title,
        body=(payload.body or "").strip() or None,
        image_path=(payload.image_path or "").strip() or None,
        status=AdCampaignStatus.DRAFT,
        created_by=admin.id,
    )
    db.add(campaign)
    await db.flush()

    if payload.send_now:
        client = getattr(request.app.state, "bot_client", None)
        if client is not None:
            await AdBroadcastService(db, client).send(campaign)
        else:
            campaign.status = AdCampaignStatus.SCHEDULED
            campaign.send_at = datetime.now(UTC)
    elif payload.send_at is not None:
        campaign.status = AdCampaignStatus.SCHEDULED
        campaign.send_at = payload.send_at

    await db.commit()
    await db.refresh(campaign)
    return _to_response(campaign)


@router.get("", response_model=list[AdCampaignResponse])
async def list_ad_campaigns(
    admin: AdminAccount = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(select(AdCampaign).order_by(AdCampaign.created_at.desc()))
    ).scalars().all()
    return [_to_response(c) for c in rows]
