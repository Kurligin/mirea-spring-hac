from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import distinct, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_db
from app.models.admin_account import AdminAccount
from app.models.bot_event import BotEvent
from app.models.registration import Registration, RegistrationStatus
from app.services.stats import DashboardStatsService

router = APIRouter(prefix="/api/admin/dashboard", tags=["admin-dashboard"])


class StatsResponse(BaseModel):
    upcoming_events: int
    confirmed_total: int
    waitlist_total: int
    cancelled_week: int
    active_users: int
    # тренды
    confirmed_week: int = 0
    confirmed_prev_week: int = 0
    cancelled_prev_week: int = 0
    upcoming_prev_week: int = 0
    active_users_prev_week: int = 0


@router.get("/stats", response_model=StatsResponse)
async def stats(
    db: AsyncSession = Depends(get_db),
    _admin: AdminAccount = Depends(get_current_admin),
):
    return StatsResponse(**await DashboardStatsService(db).collect())


class TimeseriesPoint(BaseModel):
    date: str  # YYYY-MM-DD
    confirmed: int
    cancelled: int
    waitlist: int


@router.get("/timeseries", response_model=list[TimeseriesPoint])
async def timeseries(
    window: str = Query("7d", alias="range", pattern="^(7d|30d|90d)$"),
    db: AsyncSession = Depends(get_db),
    _admin: AdminAccount = Depends(get_current_admin),
):
    """Дневные суммы: подтверждено / отменено / в waitlist по дате создания."""
    days = {"7d": 7, "30d": 30, "90d": 90}[window]
    now = datetime.now(UTC)
    start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    bucket = func.date_trunc("day", Registration.created_at).label("day")
    rows = (
        await db.execute(
            select(bucket, Registration.status, func.count())
            .where(Registration.created_at >= start)
            .group_by(bucket, Registration.status)
        )
    ).all()
    aggregate: dict[str, dict[str, int]] = {}
    for day, status, count in rows:
        key = day.date().isoformat()
        if key not in aggregate:
            aggregate[key] = {"confirmed": 0, "cancelled": 0, "waitlist": 0}
        if status == RegistrationStatus.CONFIRMED:
            aggregate[key]["confirmed"] += int(count)
        elif status == RegistrationStatus.CANCELLED:
            aggregate[key]["cancelled"] += int(count)
        elif status == RegistrationStatus.WAITLIST:
            aggregate[key]["waitlist"] += int(count)

    out: list[TimeseriesPoint] = []
    for i in range(days):
        d = (start + timedelta(days=i)).date().isoformat()
        bucket_data = aggregate.get(d, {"confirmed": 0, "cancelled": 0, "waitlist": 0})
        out.append(TimeseriesPoint(date=d, **bucket_data))
    return out


class FunnelResponse(BaseModel):
    event_view: int
    form_start: int
    confirm: int


@router.get("/funnel", response_model=FunnelResponse)
async def funnel(
    window: str = Query("7d", alias="range", pattern="^(7d|30d|90d)$"),
    db: AsyncSession = Depends(get_db),
    _admin: AdminAccount = Depends(get_current_admin),
):
    """Воронка: уникальные пары (user_id, event_id) по типам действий за окно."""
    days = {"7d": 7, "30d": 30, "90d": 90}[window]
    start = datetime.now(UTC) - timedelta(days=days)

    async def _count(action: str) -> int:
        stmt = (
            select(func.count(distinct(tuple_(BotEvent.user_id, BotEvent.event_id))))
            .where(BotEvent.action == action, BotEvent.ts >= start)
        )
        return int((await db.execute(stmt)).scalar() or 0)

    return FunnelResponse(
        event_view=await _count("event_view"),
        form_start=await _count("form_start"),
        confirm=await _count("confirm"),
    )
