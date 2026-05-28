from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event, EventStatus
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User


class DashboardStatsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def collect(self) -> dict:
        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)
        prev_week_ago = now - timedelta(days=14)

        async def _scalar(stmt) -> int:
            return int((await self.db.execute(stmt)).scalar() or 0)

        upcoming = await _scalar(
            select(func.count(Event.id)).where(
                Event.status == EventStatus.PUBLISHED, Event.starts_at >= now
            )
        )
        confirmed_total = await _scalar(
            select(func.count(Registration.id)).where(Registration.status == RegistrationStatus.CONFIRMED)
        )
        waitlist_total = await _scalar(
            select(func.count(Registration.id)).where(Registration.status == RegistrationStatus.WAITLIST)
        )
        cancelled_week = await _scalar(
            select(func.count(Registration.id)).where(
                Registration.status == RegistrationStatus.CANCELLED,
                Registration.cancelled_at >= week_ago,
            )
        )
        active_users = await _scalar(select(func.count(User.id)).where(User.is_active.is_(True)))

        # Тренды: считаем дельту за последние 7 дней vs предыдущие 7 дней.
        confirmed_week = await _scalar(
            select(func.count(Registration.id)).where(
                Registration.status == RegistrationStatus.CONFIRMED,
                Registration.created_at >= week_ago,
            )
        )
        confirmed_prev_week = await _scalar(
            select(func.count(Registration.id)).where(
                Registration.status == RegistrationStatus.CONFIRMED,
                Registration.created_at >= prev_week_ago,
                Registration.created_at < week_ago,
            )
        )
        cancelled_prev_week = await _scalar(
            select(func.count(Registration.id)).where(
                Registration.status == RegistrationStatus.CANCELLED,
                Registration.cancelled_at >= prev_week_ago,
                Registration.cancelled_at < week_ago,
            )
        )
        upcoming_prev = await _scalar(
            select(func.count(Event.id)).where(
                Event.status == EventStatus.PUBLISHED,
                Event.starts_at >= prev_week_ago,
                Event.starts_at < week_ago,
            )
        )
        active_users_prev_week = await _scalar(
            select(func.count(User.id)).where(
                User.is_active.is_(True),
                User.created_at < week_ago,
            )
        )

        return {
            "upcoming_events": upcoming,
            "confirmed_total": confirmed_total,
            "waitlist_total": waitlist_total,
            "cancelled_week": cancelled_week,
            "active_users": active_users,
            "confirmed_week": confirmed_week,
            "confirmed_prev_week": confirmed_prev_week,
            "cancelled_prev_week": cancelled_prev_week,
            "upcoming_prev_week": upcoming_prev,
            "active_users_prev_week": active_users_prev_week,
        }
