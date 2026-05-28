"""Уведомление абитуриента о факте отметки на входе.

Отправляется после успешного check-in (QR-скан или ручная отметка контролёром),
чтобы юзер был уверен «прошёл», даже если QR-окно у него закрыто.
"""
from __future__ import annotations

import logging

from app.models.event import Event
from app.models.user import User

logger = logging.getLogger(__name__)


async def notify_user_checked_in(app_state, *, user: User, event: Event) -> None:
    """Шлём короткое сообщение в MAX. Тихо игнорим, если MAX-клиент не поднят
    (тесты, dev без бота)."""
    client = getattr(app_state, "bot_client", None)
    if client is None:
        return
    text = f"✅ Вы отмечены на входе — «{event.title}». Хорошего мероприятия!"
    try:
        await client.send_message(user_id=user.max_user_id, text=text)
    except Exception:
        logger.exception("checkin notify failed: user=%s event=%s", user.id, event.id)
