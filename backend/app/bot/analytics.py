"""Лог действий пользователя в боте — для воронки и аналитики.

Используется в catalog (event_view), registration (form_start, confirm).
"""
from __future__ import annotations

import logging
from uuid import UUID

from app.models.bot_event import BotEvent

logger = logging.getLogger(__name__)


async def log_bot_event(db, user_id: UUID, event_id: UUID | str, action: str) -> None:
    """Лучше попытаться — если упало (например невалидный event_id), не блокируем основной поток."""
    try:
        if isinstance(event_id, str):
            event_id = UUID(event_id)
        db.add(BotEvent(user_id=user_id, event_id=event_id, action=action))
        await db.flush()
    except Exception:
        logger.exception("log_bot_event failed: action=%s", action)
