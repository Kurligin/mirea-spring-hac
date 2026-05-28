"""GET /api/calendar/{event_id}.ics — публичный .ics-файл для импорта в календарь.

Без авторизации (событие уже опубликовано, событие публичное).
Используется кнопкой «Apple» после подтверждения регистрации в боте, а также
из шаринга QR-приглашения.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.event import Event, EventStatus
from app.services.calendar_links import render_ics

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/{event_id}.ics")
async def event_ics(event_id: UUID, db: AsyncSession = Depends(get_db)) -> Response:
    event = (await db.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
    if event is None or event.status != EventStatus.PUBLISHED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    body = render_ics(event)
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="event_{event.id}.ics"',
            "Cache-Control": "no-cache",
        },
    )
