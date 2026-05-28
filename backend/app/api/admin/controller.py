"""Эндпоинты для роли «контролёр на входе» — сканер QR + ручной фолбек."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_db
from app.core.permissions import assert_can_access_event
from app.models.admin_account import AdminAccount
from app.models.event import Event
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User
from app.services.checkin_notify import notify_user_checked_in

router = APIRouter(prefix="/api/admin/events", tags=["admin-controller"])


# ── responses ─────────────────────────────────────────────────────────


class EventCheckinStats(BaseModel):
    event_id: UUID
    event_title: str
    starts_at: datetime
    capacity: int | None
    confirmed: int
    checked_in: int
    remaining_confirmed: int
    waitlist: int
    cancelled: int


class CheckinRegistrationRow(BaseModel):
    id: UUID
    user_name: str
    short_code: str | None
    status: RegistrationStatus
    checked_in_at: datetime | None
    is_late_cancellation: bool
    created_at: datetime


class ManualCheckinResult(BaseModel):
    registration_id: UUID
    user_name: str
    event_title: str
    short_code: str | None
    status: RegistrationStatus
    checked_in_at: datetime
    already_checked_in: bool


# ── helpers ───────────────────────────────────────────────────────────


def _user_name(u: User) -> str:
    name = " ".join(p for p in (u.first_name, u.last_name) if p)
    return name or u.username or f"MAX {u.max_user_id}"


async def _get_event_or_404(db: AsyncSession, event_id: UUID, admin: AdminAccount) -> Event:
    ev = (await db.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()
    if ev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    assert_can_access_event(admin, ev)
    return ev


async def _get_reg_in_event(db: AsyncSession, *, event_id: UUID, reg_id: UUID) -> Registration:
    reg = (
        await db.execute(
            select(Registration).where(
                Registration.id == reg_id,
                Registration.event_id == event_id,
            )
        )
    ).scalar_one_or_none()
    if reg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registration not found")
    return reg


# ── endpoints ─────────────────────────────────────────────────────────


@router.get("/{event_id}/checkin/stats", response_model=EventCheckinStats)
async def get_event_checkin_stats(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    event = await _get_event_or_404(db, event_id, admin)

    confirmed_expr = func.count(case((Registration.status == RegistrationStatus.CONFIRMED, 1)))
    checked_in_expr = func.count(
        case(
            (
                (Registration.status == RegistrationStatus.CONFIRMED)
                & (Registration.checked_in_at.is_not(None)),
                1,
            )
        )
    )
    waitlist_expr = func.count(case((Registration.status == RegistrationStatus.WAITLIST, 1)))
    cancelled_expr = func.count(case((Registration.status == RegistrationStatus.CANCELLED, 1)))

    row = (
        await db.execute(
            select(confirmed_expr, checked_in_expr, waitlist_expr, cancelled_expr).where(
                Registration.event_id == event_id
            )
        )
    ).one()
    confirmed, checked_in, waitlist, cancelled = row

    return EventCheckinStats(
        event_id=event.id,
        event_title=event.title,
        starts_at=event.starts_at,
        capacity=event.capacity,
        confirmed=confirmed,
        checked_in=checked_in,
        remaining_confirmed=max(0, confirmed - checked_in),
        waitlist=waitlist,
        cancelled=cancelled,
    )


@router.get(
    "/{event_id}/checkin/registrations",
    response_model=list[CheckinRegistrationRow],
)
async def list_event_checkin_registrations(
    event_id: UUID,
    q: str | None = Query(None, description="Поиск по ФИО, username или short_code"),
    limit: int = Query(200, le=1000),
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    """Список confirmed-регистраций события + опционально waitlist (для прозрачности).

    Сортировка: не отмеченные сверху (по дате создания), потом отмеченные.
    """
    await _get_event_or_404(db, event_id, admin)

    stmt = (
        select(Registration, User)
        .join(User, User.id == Registration.user_id)
        .where(
            Registration.event_id == event_id,
            Registration.status.in_(
                [
                    RegistrationStatus.CONFIRMED,
                    RegistrationStatus.WAITLIST,
                    RegistrationStatus.CANCELLED,
                ]
            ),
        )
    )

    if q:
        like = f"%{q.strip()}%"
        code = q.strip().upper()
        stmt = stmt.where(
            or_(
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.username.ilike(like),
                Registration.short_code == code,
            )
        )

    # Сортировка: confirmed без отметки наверх, потом отмеченные,
    # cancelled (включая позднюю отмену) — в конец списка.
    status_priority = case(
        (Registration.status == RegistrationStatus.CANCELLED, 2),
        else_=case((Registration.checked_in_at.is_(None), 0), else_=1),
    )
    stmt = stmt.order_by(
        status_priority,
        Registration.created_at.asc(),
    ).limit(limit)

    rows = (await db.execute(stmt)).all()
    return [
        CheckinRegistrationRow(
            id=reg.id,
            user_name=_user_name(user),
            short_code=reg.short_code,
            status=reg.status,
            checked_in_at=reg.checked_in_at,
            is_late_cancellation=reg.is_late_cancellation,
            created_at=reg.created_at,
        )
        for reg, user in rows
    ]


class ManualCheckinByCodeRequest(BaseModel):
    short_code: str


@router.post(
    "/{event_id}/checkin/by-code",
    response_model=ManualCheckinResult,
)
async def checkin_by_short_code(
    event_id: UUID,
    body: ManualCheckinByCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    """Ручная отметка по короткому коду в пределах конкретного события."""
    event = await _get_event_or_404(db, event_id, admin)
    code = body.short_code.strip().upper()
    if not code:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "EMPTY_CODE")

    reg = (
        await db.execute(
            select(Registration).where(
                Registration.event_id == event_id,
                Registration.short_code == code,
            )
        )
    ).scalar_one_or_none()
    if reg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CODE_NOT_FOUND")
    if reg.status != RegistrationStatus.CONFIRMED:
        raise HTTPException(status.HTTP_409_CONFLICT, "NOT_CONFIRMED")

    user = (await db.execute(select(User).where(User.id == reg.user_id))).scalar_one()
    already = reg.checked_in_at is not None
    if not already:
        reg.checked_in_at = datetime.now(UTC)
        reg.checked_in_by = admin.id
        await db.commit()
        await notify_user_checked_in(request.app.state, user=user, event=event)

    return ManualCheckinResult(
        registration_id=reg.id,
        user_name=_user_name(user),
        event_title=event.title,
        short_code=reg.short_code,
        status=reg.status,
        checked_in_at=reg.checked_in_at,
        already_checked_in=already,
    )


@router.post(
    "/{event_id}/checkin/manual/{reg_id}",
    response_model=ManualCheckinResult,
)
async def manual_checkin(
    event_id: UUID,
    reg_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    """Ручная отметка по id регистрации (из списка контролёра)."""
    event = await _get_event_or_404(db, event_id, admin)
    reg = await _get_reg_in_event(db, event_id=event_id, reg_id=reg_id)
    if reg.status != RegistrationStatus.CONFIRMED:
        raise HTTPException(status.HTTP_409_CONFLICT, "NOT_CONFIRMED")

    user = (await db.execute(select(User).where(User.id == reg.user_id))).scalar_one()
    already = reg.checked_in_at is not None
    if not already:
        reg.checked_in_at = datetime.now(UTC)
        reg.checked_in_by = admin.id
        await db.commit()
        await notify_user_checked_in(request.app.state, user=user, event=event)

    return ManualCheckinResult(
        registration_id=reg.id,
        user_name=_user_name(user),
        event_title=event.title,
        short_code=reg.short_code,
        status=reg.status,
        checked_in_at=reg.checked_in_at,
        already_checked_in=already,
    )


@router.post(
    "/{event_id}/checkin/uncheck/{reg_id}",
    response_model=ManualCheckinResult,
)
async def undo_checkin(
    event_id: UUID,
    reg_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: AdminAccount = Depends(get_current_admin),
):
    """Снять отметку прихода (ошибочно нажали)."""
    event = await _get_event_or_404(db, event_id, admin)
    reg = await _get_reg_in_event(db, event_id=event_id, reg_id=reg_id)
    user = (await db.execute(select(User).where(User.id == reg.user_id))).scalar_one()
    if reg.checked_in_at is not None:
        reg.checked_in_at = None
        reg.checked_in_by = None
        reg.checked_in_qr_bucket = None
        await db.commit()
    return ManualCheckinResult(
        registration_id=reg.id,
        user_name=_user_name(user),
        event_title=event.title,
        short_code=reg.short_code,
        status=reg.status,
        checked_in_at=reg.checked_in_at or datetime.now(UTC),
        already_checked_in=False,
    )
