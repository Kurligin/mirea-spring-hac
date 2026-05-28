from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_db
from app.models.admin_account import AdminAccount
from app.models.broadcast import (
    Broadcast,
    BroadcastAudience,
    BroadcastDelivery,
    BroadcastKind,
    BroadcastStatus,
    DeliveryStatus,
)
from app.models.event import Event
from app.services.notification import NotificationService

router = APIRouter(prefix="/api/admin/events", tags=["admin-broadcasts"])


class BroadcastCreateRequest(BaseModel):
    kind: BroadcastKind
    audience: BroadcastAudience = BroadcastAudience.CONFIRMED
    extra_text: str | None = None
    custom_topic_label: str | None = None
    send_now: bool = False
    send_at: datetime | None = None


class BroadcastResponse(BaseModel):
    id: UUID
    event_id: UUID
    kind: BroadcastKind
    audience: BroadcastAudience
    status: BroadcastStatus
    extra_text: str | None
    custom_topic_label: str | None
    send_at: datetime | None
    sent_at: datetime | None
    created_at: datetime
    delivered: int
    muted: int
    errors: int


async def _delivery_counts(db: AsyncSession, broadcast_id: UUID) -> dict[str, int]:
    rows = (
        await db.execute(
            select(BroadcastDelivery.status, func.count())
            .where(BroadcastDelivery.broadcast_id == broadcast_id)
            .group_by(BroadcastDelivery.status)
        )
    ).all()
    by_status = {s: c for s, c in rows}
    return {
        "delivered": by_status.get(DeliveryStatus.DELIVERED, 0),
        "muted": by_status.get(DeliveryStatus.MUTED, 0),
        "errors": by_status.get(DeliveryStatus.ERROR, 0),
    }


def _to_response(broadcast: Broadcast, counts: dict[str, int]) -> BroadcastResponse:
    return BroadcastResponse(
        id=broadcast.id,
        event_id=broadcast.event_id,
        kind=broadcast.kind,
        audience=broadcast.audience,
        status=broadcast.status,
        extra_text=broadcast.extra_text,
        custom_topic_label=broadcast.custom_topic_label,
        send_at=broadcast.send_at,
        sent_at=broadcast.sent_at,
        created_at=broadcast.created_at,
        delivered=counts["delivered"],
        muted=counts["muted"],
        errors=counts["errors"],
    )


@router.post(
    "/{event_id}/broadcasts",
    response_model=BroadcastResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_broadcast(
    event_id: UUID,
    payload: BroadcastCreateRequest,
    request: Request,
    admin: AdminAccount = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Создать рассылку по мероприятию. send_now → отправить сразу;
    send_at → запланировать; иначе — черновик."""
    event = (
        await db.execute(select(Event).where(Event.id == event_id))
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")

    custom_label = (payload.custom_topic_label or "").strip() or None
    if payload.kind == BroadcastKind.OTHER and not custom_label:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "custom_topic_label required when kind=other",
        )
    broadcast = Broadcast(
        event_id=event_id,
        kind=payload.kind,
        audience=payload.audience,
        context={},
        extra_text=payload.extra_text,
        custom_topic_label=custom_label if payload.kind == BroadcastKind.OTHER else None,
        status=BroadcastStatus.DRAFT,
        created_by=admin.id,
    )
    db.add(broadcast)
    await db.flush()

    if payload.send_now:
        client = getattr(request.app.state, "bot_client", None)
        if client is not None:
            await NotificationService(db, client).send_broadcast(broadcast)
        else:
            # нет живого MAX-клиента (например, тесты) — отдать планировщику
            broadcast.status = BroadcastStatus.SCHEDULED
            broadcast.send_at = datetime.now(UTC)
    elif payload.send_at is not None:
        broadcast.status = BroadcastStatus.SCHEDULED
        broadcast.send_at = payload.send_at

    await db.commit()
    await db.refresh(broadcast)
    counts = await _delivery_counts(db, broadcast.id)
    return _to_response(broadcast, counts)


@router.get("/{event_id}/broadcasts", response_model=list[BroadcastResponse])
async def list_broadcasts(
    event_id: UUID,
    admin: AdminAccount = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Список рассылок мероприятия (новые сверху)."""
    broadcasts = (
        await db.execute(
            select(Broadcast)
            .where(Broadcast.event_id == event_id)
            .order_by(Broadcast.created_at.desc())
        )
    ).scalars().all()
    result: list[BroadcastResponse] = []
    for b in broadcasts:
        counts = await _delivery_counts(db, b.id)
        result.append(_to_response(b, counts))
    return result
