"""Тесты хендлеров QR-кода: qr (новое сообщение), qrr (ручное обновление)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.bot.handlers.qr import handle_callback
from app.bot.qr_rotation import qr_session_manager
from app.models.event import Event, EventStatus, EventType
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User
from tests.fixtures.bot_helpers import callback_update, make_ctx


# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------


def _event(title: str = "Тест-событие", days: int = 5, **kw) -> Event:
    base = dict(
        title=title,
        event_type=EventType.OPEN_DAY,
        status=EventStatus.PUBLISHED,
        starts_at=datetime.now(UTC) + timedelta(days=days),
        duration_minutes=60,
        capacity=30,
    )
    base.update(kw)
    return Event(**base)


@pytest.fixture(autouse=True)
def _clear_qr_sessions():
    qr_session_manager._sessions.clear()
    yield
    qr_session_manager._sessions.clear()


# ---------------------------------------------------------------------------
# Тест 1: qr на записи не в CONFIRMED → toast про подтверждённые
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_qr_on_non_confirmed_toasts(db):
    """qr на записи WAITLIST → toast с текстом про подтверждённые записи."""
    user = User(max_user_id=901001)
    event = _event("День открытых дверей QR")
    db.add_all([user, event])
    await db.flush()

    reg = Registration(
        user_id=user.id,
        event_id=event.id,
        status=RegistrationStatus.WAITLIST,
        answers={},
        waitlist_position=1,
    )
    db.add(reg)
    await db.flush()

    ctx, mock_app = make_ctx(db)
    update = callback_update(901001, f"qr:{reg.id}", callback_id="cb-qr-nc")

    await handle_callback(update, ctx, "qr", [str(reg.id)])

    # В ответах должен быть notification с текстом про подтверждённые
    answers = mock_app.state.mock["answers"]
    assert answers, "handle_callback не вызвал answer_callback"
    notifications = [a["body"].get("notification", "") for a in answers]
    assert any("подтверждённ" in n for n in notifications), (
        f"Ожидали toast про подтверждённые, получили: {notifications}"
    )
    # send_message не должен был вызываться — QR не показывается
    assert mock_app.state.mock["sent_messages"] == []


# ---------------------------------------------------------------------------
# Тест 2: qr на CONFIRMED → send_message с image-attachment + сессия открыта
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_qr_on_confirmed_sends_image_and_opens_session(db):
    """qr на CONFIRMED → send_message с image-attachment; сессия в qr_session_manager."""
    user = User(max_user_id=901002)
    event = _event("Мастер-класс QR", days=3)
    db.add_all([user, event])
    await db.flush()

    reg = Registration(
        user_id=user.id,
        event_id=event.id,
        status=RegistrationStatus.CONFIRMED,
        answers={},
        short_code="C-QR-1",
    )
    db.add(reg)
    await db.flush()

    ctx, mock_app = make_ctx(db)
    # Подменяем upload_image_for_attachment и send_message на AsyncMock,
    # чтобы не зависеть от реальной сети и render_qr_png.
    ctx.client.upload_image_for_attachment = AsyncMock(
        return_value={"type": "image", "payload": {"token": "T-test"}}
    )
    ctx.client.send_message = AsyncMock(
        return_value={"message": {"body": {"mid": "MID-TEST-1"}}}
    )
    # answer_callback нужен для первого toast("Открываю QR…")
    ctx.client.answer_callback = AsyncMock(return_value={"success": True})

    update = callback_update(901002, f"qr:{reg.id}", callback_id="cb-qr-c", chat_id=901002)

    # Патчим render_qr_png чтобы не нужен был реальный PNG-рендерер
    with patch("app.bot.handlers.qr.render_qr_png", return_value=b"\x89PNG"):
        await handle_callback(update, ctx, "qr", [str(reg.id)])

    # send_message вызван ровно один раз
    ctx.client.send_message.assert_called_once()
    call_kwargs = ctx.client.send_message.call_args.kwargs

    # Передан правильный chat_id
    assert call_kwargs["chat_id"] == 901002

    # В attachments есть image-вложение с нашим токеном
    attachments = call_kwargs.get("attachments", [])
    assert any(
        a.get("type") == "image" and (a.get("payload") or {}).get("token") == "T-test"
        for a in attachments
    ), f"image-attachment не найден в: {attachments}"

    # Сессия зарегистрирована в qr_session_manager
    session = qr_session_manager.get(reg.id)
    assert session is not None, "QR-сессия не была открыта в qr_session_manager"
    assert session.message_id == "MID-TEST-1"
    assert session.chat_id == 901002
