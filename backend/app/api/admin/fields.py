from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_db
from app.models.admin_account import AdminAccount
from app.schemas.event_field import EventFieldCreate, EventFieldResponse
from app.services.form_field import FormFieldService

router = APIRouter(prefix="/api/admin/events", tags=["admin-fields"])


@router.get("/{event_id}/fields", response_model=list[EventFieldResponse])
async def list_fields(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin: AdminAccount = Depends(get_current_admin),
) -> list[EventFieldResponse]:
    fields = await FormFieldService(db).list_for_event(event_id)
    return [EventFieldResponse.model_validate(f) for f in fields]


@router.put("/{event_id}/fields", response_model=list[EventFieldResponse])
async def replace_fields(
    event_id: UUID,
    payload: list[EventFieldCreate],
    db: AsyncSession = Depends(get_db),
    _admin: AdminAccount = Depends(get_current_admin),
) -> list[EventFieldResponse]:
    fields = await FormFieldService(db).replace_all(event_id, payload)
    await db.commit()
    return [EventFieldResponse.model_validate(f) for f in fields]
