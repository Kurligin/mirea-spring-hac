"""Эндпоинты управления контролёрами события (M2M event_controllers)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_db
from app.core.permissions import assert_can_access_event
from app.models.admin_account import AdminAccount, AdminRole
from app.models.event_controller import EventController
from app.services.event import EventService

router = APIRouter(prefix="/api/admin/events", tags=["admin-event-controllers"])


class ControllerEntry(BaseModel):
    admin_id: UUID
    email: str
    full_name: str | None = None


class AssignRequest(BaseModel):
    admin_id: UUID


async def _get_event_or_404(event_id: UUID, db: AsyncSession):
    event = await EventService(db).get(event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.get("/{event_id}/controllers", response_model=list[ControllerEntry])
async def list_controllers(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
) -> list[ControllerEntry]:
    event = await _get_event_or_404(event_id, db)
    assert_can_access_event(admin, event)

    # Загружаем admin_accounts для каждого назначенного контролёра.
    admin_ids = [c.admin_id for c in event.controllers]
    if not admin_ids:
        return []

    rows = (
        (await db.execute(select(AdminAccount).where(AdminAccount.id.in_(admin_ids))))
        .scalars()
        .all()
    )

    by_id: dict[UUID, AdminAccount] = {a.id: a for a in rows}
    return [
        ControllerEntry(
            admin_id=c.admin_id,
            email=by_id[c.admin_id].email,
            full_name=by_id[c.admin_id].full_name,
        )
        for c in event.controllers
        if c.admin_id in by_id
    ]


@router.post(
    "/{event_id}/controllers",
    response_model=ControllerEntry,
    status_code=status.HTTP_201_CREATED,
)
async def assign_controller(
    event_id: UUID,
    payload: AssignRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
) -> ControllerEntry:
    event = await _get_event_or_404(event_id, db)
    assert_can_access_event(admin, event)

    # Проверяем, что target — реальный CONTROLLER.
    target = (
        await db.execute(select(AdminAccount).where(AdminAccount.id == payload.admin_id))
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Admin not found")
    if target.role != AdminRole.CONTROLLER:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Target admin must have CONTROLLER role",
        )

    # Idempotent: если уже назначен — возвращаем 201 без дублирования.
    already = any(c.admin_id == payload.admin_id for c in event.controllers)
    if not already:
        db.add(EventController(event_id=event_id, admin_id=payload.admin_id))
        await db.commit()

    return ControllerEntry(
        admin_id=target.id,
        email=target.email,
        full_name=target.full_name,
    )


@router.delete(
    "/{event_id}/controllers/{admin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unassign_controller(
    event_id: UUID,
    admin_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
) -> None:
    event = await _get_event_or_404(event_id, db)
    assert_can_access_event(admin, event)

    row = (
        await db.execute(
            select(EventController).where(
                EventController.event_id == event_id,
                EventController.admin_id == admin_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Controller not assigned to event")

    await db.delete(row)
    await db.commit()
