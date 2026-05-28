"""Хендлеры показа QR-кода в боте: qr (новое сообщение), qrr (ручное обновление)."""
from __future__ import annotations

import logging
import time

from app.bot import texts
from app.bot.context import BotContext
from app.bot.handlers.mine import _load_own_registration
from app.bot.handlers.onboarding import _chat_id, _user_from_update
from app.bot.keyboards import qr_keyboard
from app.bot.qr_rotation import qr_session_manager
from app.core.config import get_settings
from app.core.qr_render import render_qr_png
from app.models.registration import RegistrationStatus

logger = logging.getLogger(__name__)


def _qr_caption(reg, event, *, bucket: int | None = None) -> str:
    when = event.starts_at.strftime("%d.%m.%Y %H:%M")
    head = texts.QR_HEADER.format(title=event.title, when=when)
    code_line = (
        f"Код: {reg.short_code}\nПокажите его на входе."
        if reg.short_code else "Покажите код на входе."
    )
    hint = texts.QR_HINT
    if bucket is not None:
        hint = f"{hint}\n\n#{bucket % 1000}"
    return f"{head}\n\n{code_line}\n\n{hint}"


async def _generate_attachment(client, reg) -> dict:
    """QR содержит только short_code — короткий payload → крупные модули → лёгкий скан."""
    payload = reg.short_code or ""
    png = render_qr_png(payload)
    return await client.upload_image_for_attachment(data=png)


def _extract_mid(resp: dict) -> str | None:
    """MAX-ответ send_message: ищем mid в нескольких возможных местах."""
    if not isinstance(resp, dict):
        return None
    msg = resp.get("message") or {}
    body = msg.get("body") or {}
    return body.get("mid") or msg.get("mid")


async def handle_callback(update: dict, ctx: BotContext, action: str, args: list[str]) -> None:
    callback = update["callback"]
    callback_id = callback["callback_id"]
    chat_id = _chat_id(update)
    info = _user_from_update(update)
    user = await ctx.get_or_create_user(
        info["user_id"], first_name=info["first_name"],
        last_name=info["last_name"], username=info["username"],
    )

    if action == "qr":
        reg = await _load_own_registration(ctx, user.id, args[0])
        if reg is None:
            await ctx.toast(callback_id, "Запись не найдена.")
            return
        if reg.status != RegistrationStatus.CONFIRMED:
            await ctx.toast(callback_id, texts.QR_NOT_CONFIRMED)
            return
        await ctx.toast(callback_id, "Открываю QR…")
        att = await _generate_attachment(ctx.client, reg)
        caption = _qr_caption(reg, reg.event)
        resp = await ctx.client.send_message(
            chat_id=chat_id, text=caption, attachments=[att], keyboard=qr_keyboard(str(reg.id)),
        )
        mid = _extract_mid(resp)
        logger.info("qr open: reg_id=%s mid=%s send_resp=%r", reg.id, mid, resp)
        if mid:
            settings = get_settings()
            qr_session_manager.open(
                reg_id=reg.id, chat_id=chat_id, message_id=mid,
                ttl_seconds=settings.qr_session_ttl_seconds,
            )
        return

    if action == "qrr":
        reg = await _load_own_registration(ctx, user.id, args[0])
        if reg is None or reg.status != RegistrationStatus.CONFIRMED:
            await ctx.toast(callback_id, texts.QR_NOT_CONFIRMED)
            return
        att = await _generate_attachment(ctx.client, reg)
        session = qr_session_manager.get(reg.id)
        bucket = int(time.time()) // get_settings().qr_bucket_seconds
        edit_resp = None
        if session is not None:
            edit_resp = await ctx.client.edit_message(
                message_id=session.message_id,
                text=_qr_caption(reg, reg.event, bucket=bucket),
                attachments=[att],
                keyboard=qr_keyboard(str(reg.id)),
            )
            session.last_bucket = bucket
        logger.info("qrr manual: reg_id=%s mid=%s bucket=%d edit=%r",
                    reg.id, session.message_id if session else None, bucket, edit_resp)
        await ctx.client.answer_callback(callback_id=callback_id, notification="Обновлено.")
        return

    if action == "qrc":
        from uuid import UUID
        try:
            reg_uuid = UUID(args[0])
        except (ValueError, IndexError):
            await ctx.toast(callback_id, "Запись не найдена.")
            return
        session = qr_session_manager.get(reg_uuid)
        if session is not None:
            try:
                await ctx.client.edit_message(
                    message_id=session.message_id, text=texts.QR_CLOSED, attachments=[],
                )
            except Exception:
                logger.exception("qrc: edit failed")
            qr_session_manager.stop(reg_uuid)
        await ctx.client.answer_callback(callback_id=callback_id, notification="QR скрыт.")
        return
