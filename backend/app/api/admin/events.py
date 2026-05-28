from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_admin, get_db
from app.core.permissions import assert_can_access_event
from app.core.qr_render import render_qr_png
from app.models.admin_account import AdminAccount, AdminRole
from app.models.event import EventStatus
from app.models.registration import Registration, RegistrationStatus
from app.schemas.event import EventCreate, EventResponse, EventUpdate
from app.services.audit import record_audit
from app.services.event import EventService

router = APIRouter(prefix="/api/admin/events", tags=["admin-events"])


@router.get("", response_model=list[EventResponse])
async def list_events(
    status: EventStatus | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    if admin.role == AdminRole.SUPER:
        events = await EventService(db).list(status=status, limit=limit, offset=offset)
    elif admin.role == AdminRole.EVENT_MANAGER:
        events = await EventService(db).list(
            status=status, limit=limit, offset=offset, owner_id=admin.id
        )
    elif admin.role == AdminRole.CONTROLLER:
        events = await EventService(db).list(
            status=status, limit=limit, offset=offset, controller_admin_id=admin.id
        )
    else:  # VIEWER или unknown
        events = []

    counts: dict[UUID, tuple[int, int]] = {}
    if events:
        event_ids = [e.id for e in events]
        agg = await db.execute(
            select(
                Registration.event_id,
                func.sum(case((Registration.status == RegistrationStatus.CONFIRMED, 1), else_=0)).label("c"),
                func.sum(case((Registration.status == RegistrationStatus.WAITLIST, 1), else_=0)).label("w"),
            )
            .where(Registration.event_id.in_(event_ids))
            .group_by(Registration.event_id)
        )
        for ev_id, c, w in agg.all():
            counts[ev_id] = (int(c), int(w))

    out: list[EventResponse] = []
    for e in events:
        c, w = counts.get(e.id, (0, 0))
        r = EventResponse.model_validate(e)
        r.confirmed_count = c
        r.waitlist_count = w
        out.append(r)
    return out


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    owner_id = None if admin.role.value == "super" else admin.id
    event = await EventService(db).create(payload, owner_id=owner_id)
    await db.commit()
    return EventResponse.model_validate(event)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    event = await EventService(db).get(event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    assert_can_access_event(admin, event)
    return EventResponse.model_validate(event)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: UUID,
    payload: EventUpdate,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    event = await EventService(db).get(event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    assert_can_access_event(admin, event)
    event = await EventService(db).update(event_id, payload)
    await db.commit()
    return EventResponse.model_validate(event)


@router.post("/{event_id}/publish", response_model=EventResponse)
async def publish_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    event = await EventService(db).get(event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    assert_can_access_event(admin, event)
    event = await EventService(db).publish(event_id)
    await record_audit(db, admin=admin, action="event.publish",
                       target_kind="event", target_id=event.id, payload={"title": event.title})
    await db.commit()
    return EventResponse.model_validate(event)


@router.post("/{event_id}/cancel", response_model=EventResponse)
async def cancel_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    event = await EventService(db).get(event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    assert_can_access_event(admin, event)
    event = await EventService(db).cancel(event_id)
    await record_audit(db, admin=admin, action="event.cancel",
                       target_kind="event", target_id=event.id, payload={"title": event.title})
    await db.commit()
    return EventResponse.model_validate(event)


@router.post("/{event_id}/restore", response_model=EventResponse)
async def restore_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    """Возвращает отменённое мероприятие в статус draft для повторного редактирования."""
    event = await EventService(db).get(event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    assert_can_access_event(admin, event)
    event = await EventService(db).restore(event_id)
    await record_audit(db, admin=admin, action="event.restore",
                       target_kind="event", target_id=event.id, payload={"title": event.title})
    await db.commit()
    return EventResponse.model_validate(event)


@router.post(
    "/{event_id}/duplicate", response_model=EventResponse, status_code=status.HTTP_201_CREATED
)
async def duplicate_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    """Создаёт копию мероприятия (draft, в названии « (копия)»)."""
    event = await EventService(db).get(event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    assert_can_access_event(admin, event)
    event = await EventService(db).duplicate(event_id)
    await db.commit()
    return EventResponse.model_validate(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    """Жёсткое удаление черновика. Опубликованные/отменённые удалять нельзя — используй cancel."""
    event = await EventService(db).get(event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    assert_can_access_event(admin, event)
    title = event.title
    try:
        await EventService(db).delete(event_id)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    await record_audit(db, admin=admin, action="event.delete",
                       target_kind="event", target_id=event_id, payload={"title": title})
    await db.commit()


@router.get("/{event_id}/share-qr.png")
async def share_qr(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
) -> Response:
    """PNG QR-приглашения: содержит ссылку на бота с deep-link start=event_<id>.
    Для печати/постера — большой и крупномодульный из-за короткого payload."""
    event = await EventService(db).get(event_id)
    if event is None:
        raise HTTPException(404, "Event not found")
    assert_can_access_event(admin, event)

    settings = get_settings()
    base = (settings.bot_share_url or "").rstrip("/")
    if base:
        payload = f"{base}?start=event_{event.id}"
    else:
        # Fallback — текстовый payload «event_<uuid>», который мы парсим в боте
        payload = f"event_{event.id}"
    png = render_qr_png(payload)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )
