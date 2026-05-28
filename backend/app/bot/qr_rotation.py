"""In-memory сессии активных QR-сообщений + фоновый воркер ротации."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.keyboards import qr_keyboard
from app.core.config import get_settings
from app.core.max_client import MaxApiError, MaxClient
from app.core.qr import QRService
from app.core.qr_render import render_qr_png
from app.models.event import Event
from app.models.registration import Registration, RegistrationStatus

logger = logging.getLogger(__name__)


@dataclass
class QrSession:
    reg_id: UUID
    chat_id: int
    message_id: str
    expires_at: float
    last_bucket: int = -1


class QrSessionManager:
    """In-memory dict; одна сессия на reg_id."""

    def __init__(self) -> None:
        self._sessions: dict[UUID, QrSession] = {}

    def open(self, *, reg_id: UUID, chat_id: int, message_id: str, ttl_seconds: int) -> QrSession:
        s = QrSession(
            reg_id=reg_id,
            chat_id=chat_id,
            message_id=message_id,
            expires_at=time.time() + ttl_seconds,
        )
        self._sessions[reg_id] = s
        return s

    def stop(self, reg_id: UUID) -> None:
        self._sessions.pop(reg_id, None)

    def get(self, reg_id: UUID) -> QrSession | None:
        return self._sessions.get(reg_id)

    def active(self) -> list[QrSession]:
        return list(self._sessions.values())


# Глобальный singleton — бот в одном процессе.
qr_session_manager = QrSessionManager()


class QrRotationWorker:
    """Фоновый цикл: раз в tick_seconds проходит по активным сессиям,
    при смене бакета — генерит новый QR и правит сообщение.
    Останавливает сессию при checked_in_at, истёкшем TTL, не-CONFIRMED статусе, окончании события.
    """

    def __init__(
        self,
        *,
        client: MaxClient,
        session_factory: async_sessionmaker[AsyncSession],
        manager: QrSessionManager,
    ):
        self.client = client
        self.session_factory = session_factory
        self.manager = manager
        self._stop = asyncio.Event()

    async def run(self) -> None:
        settings = get_settings()
        while not self._stop.is_set():
            try:
                await self._tick()
            except Exception:
                logger.exception("qr_rotation_worker: tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=settings.qr_rotation_tick_seconds)
            except asyncio.TimeoutError:
                pass

    async def _tick(self) -> None:
        settings = get_settings()
        qr = QRService(
            secret=settings.qr_server_secret,
            bucket_seconds=settings.qr_bucket_seconds,
            fuzz_window=settings.qr_fuzz_window,
        )
        now_ts = time.time()
        current_bucket = int(now_ts) // settings.qr_bucket_seconds
        active = self.manager.active()
        if active:
            logger.info("qr_rotation tick: active=%d bucket=%d", len(active), current_bucket)

        for session in active:
            async with self.session_factory() as db:
                reg = (await db.execute(
                    select(Registration).where(Registration.id == session.reg_id)
                )).scalar_one_or_none()
                if reg is None or reg.status != RegistrationStatus.CONFIRMED:
                    await self._finalize(session, "Запись неактивна. Откройте QR заново при необходимости.")
                    continue
                if reg.checked_in_at is not None:
                    await self._finalize(session, "✅ Вы отмечены на входе!")
                    continue
                if now_ts >= session.expires_at:
                    await self._finalize(session, "Сессия QR истекла. Откройте QR заново.")
                    continue
                event = (await db.execute(select(Event).where(Event.id == reg.event_id))).scalar_one_or_none()
                if event is not None:
                    event_end_ts = event.starts_at.timestamp() + event.duration_minutes * 60
                    if now_ts >= event_end_ts:
                        await self._finalize(session, "Мероприятие завершено.")
                        continue
                if current_bucket == session.last_bucket:
                    continue

                # Короткий payload: только short_code (QR крупнее → проще сканировать)
                png = render_qr_png(reg.short_code or "")
                try:
                    att = await self.client.upload_image_for_attachment(data=png)
                    from app.bot.handlers.qr import _qr_caption
                    caption = _qr_caption(reg, event, bucket=current_bucket)
                    resp = await self.client.edit_message(
                        message_id=session.message_id,
                        text=caption,
                        attachments=[att],
                        keyboard=qr_keyboard(str(session.reg_id)),
                    )
                    logger.info(
                        "qr_rotation: edited reg_id=%s mid=%s bucket=%d resp=%r",
                        session.reg_id, session.message_id, current_bucket, resp,
                    )
                except MaxApiError as e:
                    logger.warning("qr_rotation: edit failed reg_id=%s mid=%s: %s",
                                   session.reg_id, session.message_id, e)
                    self.manager.stop(session.reg_id)
                    continue
                session.last_bucket = current_bucket

    async def _finalize(self, session: QrSession, final_text: str) -> None:
        try:
            await self.client.edit_message(
                message_id=session.message_id, text=final_text, attachments=[],
            )
        except MaxApiError:
            pass
        self.manager.stop(session.reg_id)

    def stop(self) -> None:
        self._stop.set()
