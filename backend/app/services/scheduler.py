"""Фоновый планировщик уведомлений: напоминания + отложенные рассылки."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.max_client import MaxClient
from app.models.ad_campaign import AdCampaign, AdCampaignStatus
from app.models.broadcast import Broadcast, BroadcastStatus
from app.models.event import Event, EventStatus
from app.services.ad_broadcast import AdBroadcastService
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)


async def run_tick(session_factory: async_sessionmaker[AsyncSession], client: MaxClient) -> dict:
    """Один проход планировщика: сгенерировать напоминания + разослать дозревшие.

    Возвращает счётчики для логов/тестов.
    """
    result = {"reminders_created": 0, "broadcasts_sent": 0, "ad_campaigns_sent": 0}
    async with session_factory() as db:
        notif = NotificationService(db, client)
        now = datetime.now(UTC)

        events = (
            await db.execute(
                select(Event).where(
                    Event.status == EventStatus.PUBLISHED,
                    Event.starts_at > now,
                )
            )
        ).scalars().all()
        for event in events:
            result["reminders_created"] += await notif.create_event_reminders(event)

        due = (
            await db.execute(
                select(Broadcast).where(
                    Broadcast.status == BroadcastStatus.SCHEDULED,
                    Broadcast.send_at.is_not(None),
                    Broadcast.send_at <= now,
                )
            )
        ).scalars().all()
        for broadcast in due:
            await notif.send_broadcast(broadcast)
            result["broadcasts_sent"] += 1

        ad_due = (
            await db.execute(
                select(AdCampaign).where(
                    AdCampaign.status == AdCampaignStatus.SCHEDULED,
                    AdCampaign.send_at.is_not(None),
                    AdCampaign.send_at <= now,
                )
            )
        ).scalars().all()
        ad_svc = AdBroadcastService(db, client)
        for campaign in ad_due:
            await ad_svc.send(campaign)
            result["ad_campaigns_sent"] += 1

        await db.commit()
    return result


class NotificationScheduler:
    """Обёртка над APScheduler: тик раз в 60 секунд."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], client: MaxClient):
        self.session_factory = session_factory
        self.client = client
        self._scheduler = AsyncIOScheduler()

    async def _job(self) -> None:
        try:
            result = await run_tick(self.session_factory, self.client)
            if result["reminders_created"] or result["broadcasts_sent"]:
                logger.info(
                    "notification tick: напоминаний создано=%s, рассылок отправлено=%s",
                    result["reminders_created"],
                    result["broadcasts_sent"],
                )
        except Exception:
            logger.exception("notification scheduler: ошибка тика")

    def start(self) -> None:
        self._scheduler.add_job(self._job, "interval", seconds=60, id="notification_tick")
        self._scheduler.start()
        logger.info("Notification scheduler started")

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
