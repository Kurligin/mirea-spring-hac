"""Маршрутизация обновлений MAX в хендлеры + фоновый BotWorker."""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.context import BotContext
from app.bot.keyboards import parse_cb
from app.bot.update_queue import update_queue
from app.core.max_client import MaxClient

logger = logging.getLogger(__name__)


def _update_summary(update: dict) -> str:
    """Краткое описание обновления для логов: тип, MAX user_id, контент."""
    ut = update.get("update_type")
    if "callback" in update:
        cb = update.get("callback") or {}
        uid = (cb.get("user") or {}).get("user_id")
        return f"type={ut} max_user_id={uid} payload={cb.get('payload')!r}"
    if "message" in update:
        msg = update.get("message") or {}
        uid = (msg.get("sender") or {}).get("user_id")
        text = ((msg.get("body") or {}).get("text") or "")[:60]
        return f"type={ut} max_user_id={uid} text={text!r}"
    if "user" in update:
        uid = (update.get("user") or {}).get("user_id")
        return f"type={ut} max_user_id={uid}"
    return f"type={ut}"


async def dispatch(update: dict, ctx: BotContext) -> None:
    """Маршрутизирует одно обновление. Неизвестные типы тихо игнорирует."""
    from app.bot.handlers import onboarding

    logger.info("bot update: %s", _update_summary(update))

    update_type = update.get("update_type")

    if update_type == "bot_started":
        await onboarding.handle_bot_started(update, ctx)
        return
    if update_type in ("bot_stopped", "bot_stopped_from_chat"):
        await onboarding.handle_bot_stopped(update, ctx)
        return
    if update_type == "message_created":
        await _route_message(update, ctx)
        return
    if update_type == "message_callback":
        await _route_callback(update, ctx)
        return
    logger.info("bot: пропущен неизвестный update_type=%s", update_type)


async def _route_message(update: dict, ctx: BotContext) -> None:
    from app.bot.handlers import onboarding, registration

    message = update.get("message") or {}
    text = (message.get("body") or {}).get("text") or ""
    if text.strip().lower().startswith("/start"):
        await onboarding.handle_start_command(update, ctx)
        return
    handled = await registration.handle_dialog_message(update, ctx)
    if not handled:
        await onboarding.handle_fallback_message(update, ctx)


_CALLBACK_ROUTES: dict[str, str] = {
    "m": "catalog",
    "terms": "onboarding",
    "ev": "catalog",
    "sh": "catalog",
    "cpk": "catalog",
    "dpk": "catalog",
    "fpk": "catalog",
    "csrch": "catalog",
    "rg": "registration",
    "ph": "registration",
    "phx": "registration",
    "sl": "registration",
    "fv": "registration",
    "fdone": "registration",
    "ok": "registration",
    "ab": "registration",
    "cn": "mine",
    "cy": "mine",
    "mut": "mine",
    "rgd": "mine",
    "qr": "qr",
    "qrr": "qr",
    "qrc": "qr",
}


async def _route_callback(update: dict, ctx: BotContext) -> None:
    from app.bot.handlers import catalog, mine, onboarding, qr, registration

    callback = update.get("callback") or {}
    payload = callback.get("payload") or ""
    action, args = parse_cb(payload)
    module_name = _CALLBACK_ROUTES.get(action)
    modules = {
        "catalog": catalog,
        "onboarding": onboarding,
        "registration": registration,
        "mine": mine,
        "qr": qr,
    }
    module = modules.get(module_name)
    if module is None:
        logger.info("bot: неизвестный callback action=%s", action)
        callback_id = callback.get("callback_id")
        if callback_id:
            await ctx.toast(callback_id, "Кнопка устарела, откройте меню заново.")
        return
    await module.handle_callback(update, ctx, action, args)


class BotWorker:
    """Забирает обновления из update_queue и обрабатывает их.

    Каждое обновление — своя БД-сессия и транзакция: commit при успехе,
    rollback + лог при ошибке. Падение хендлера не валит воркер.
    """

    def __init__(self, client: MaxClient, session_factory: async_sessionmaker[AsyncSession]):
        self.client = client
        self.session_factory = session_factory
        self._stop = asyncio.Event()

    async def run(self) -> None:
        while not self._stop.is_set():
            update = await update_queue.get()
            await self._handle(update)

    async def _handle(self, update: dict) -> None:
        try:
            async with self.session_factory() as db:
                ctx = BotContext(self.client, db)
                try:
                    await dispatch(update, ctx)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    logger.exception(
                        "bot: хендлер упал на update_type=%s", update.get("update_type")
                    )
        except Exception:
            logger.exception("bot: ошибка воркера на обновлении")

    def stop(self) -> None:
        self._stop.set()
