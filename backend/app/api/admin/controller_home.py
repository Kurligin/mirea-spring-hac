"""GET /api/admin/controller/my-events — события, где текущий админ назначен CONTROLLER."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_db
from app.models.admin_account import AdminAccount
from app.models.event import Event
from app.models.event_controller import EventController

router = APIRouter(prefix="/api/admin/controller", tags=["admin-controller-home"])


class MyEventEntry(BaseModel):
    id: UUID
    title: str
    starts_at: datetime
    location: str | None
    duration_minutes: int


@router.get("/my-events", response_model=list[MyEventEntry])
async def list_my_events(
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
) -> list[MyEventEntry]:
    """Список событий, на которые текущий администратор назначен контролёром."""
    stmt = (
        select(Event)
        .join(EventController, EventController.event_id == Event.id)
        .where(EventController.admin_id == admin.id)
        .order_by(Event.starts_at.asc())
    )
    events = (await db.execute(stmt)).scalars().all()
    return [
        MyEventEntry(
            id=ev.id,
            title=ev.title,
            starts_at=ev.starts_at,
            location=ev.location,
            duration_minutes=ev.duration_minutes,
        )
        for ev in events
    ]
