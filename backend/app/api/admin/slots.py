from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_db
from app.models.admin_account import AdminAccount
from app.schemas.event_slot import EventSlotCreate, EventSlotResponse
from app.services.slot import SlotService

router = APIRouter(prefix="/api/admin/events", tags=["admin-slots"])


@router.get("/{event_id}/slots", response_model=list[EventSlotResponse])
async def list_slots(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: AdminAccount = Depends(get_current_admin),
):
    slots = await SlotService(db).list_for_event(event_id)
    return [EventSlotResponse.model_validate(s) for s in slots]


@router.put("/{event_id}/slots", response_model=list[EventSlotResponse])
async def replace_slots(
    event_id: UUID,
    payload: list[EventSlotCreate],
    db: AsyncSession = Depends(get_db),
    _admin: AdminAccount = Depends(get_current_admin),
):
    slots = await SlotService(db).replace_all(event_id, [p.model_dump() for p in payload])
    await db.commit()
    return [EventSlotResponse.model_validate(s) for s in slots]
