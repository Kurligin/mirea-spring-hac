"""Онбординг: bot_started, /start, согласие с условиями, bot_stopped."""
from __future__ import annotations

import uuid

from sqlalchemy import select

from app.bot import texts
from app.bot.context import BotContext
from app.bot.keyboards import consent_keyboard, main_menu
from app.models.consent_log import ConsentKind
from app.models.user import User
from app.services.consent import ConsentService


def _user_from_update(update: dict) -> dict:
    """Достаёт {user_id, first_name, last_name, username} из любого обновления."""
    if "user" in update:
        u = update["user"]
    elif "callback" in update:
        u = update["callback"].get("user", {})
    else:
        u = (update.get("message") or {}).get("sender", {})
    return {
        "user_id": u.get("user_id"),
        "first_name": u.get("first_name"),
        "last_name": u.get("last_name"),
        "username": u.get("username"),
    }


def _chat_id(update: dict) -> int:
    if "chat_id" in update:
        return update["chat_id"]
    message = update.get("message") or {}
    recipient = message.get("recipient") or {}
    if recipient.get("chat_id") is not None:
        return recipient["chat_id"]
    return _user_from_update(update)["user_id"]


async def _greet(update: dict, ctx: BotContext) -> None:
    """Создаёт/обновляет юзера и шлёт дисклеймер либо меню."""
    info = _user_from_update(update)
    user = await ctx.get_or_create_user(
        info["user_id"],
        first_name=info["first_name"],
        last_name=info["last_name"],
        username=info["username"],
    )
    chat_id = _chat_id(update)
    if await ConsentService(ctx.db).has_accepted_terms(user.id):
        await ctx.send(chat_id, texts.MENU, main_menu())
    else:
        await ctx.send(chat_id, texts.DISCLAIMER, consent_keyboard())


async def handle_bot_started(update: dict, ctx: BotContext) -> None:
    await _greet(update, ctx)


async def handle_start_command(update: dict, ctx: BotContext) -> None:
    # /start event_<uuid> — deep-link напрямую к карточке мероприятия
    message = update.get("message") or {}
    text = ((message.get("body") or {}).get("text") or "").strip()
    parts = text.split(maxsplit=1)
    payload = parts[1].strip() if len(parts) == 2 else ""
    if payload.startswith("event_"):
        event_id = payload[len("event_"):].strip()
        try:
            uuid.UUID(event_id)
        except ValueError:
            event_id = ""
        if event_id:
            await _deep_link_to_event(update, ctx, event_id)
            return
    await _greet(update, ctx)


async def _deep_link_to_event(update: dict, ctx: BotContext, event_id: str) -> None:
    """Юзер пришёл по /start event_<id> — показываем карточку события сразу после consent."""
    info = _user_from_update(update)
    user = await ctx.get_or_create_user(
        info["user_id"],
        first_name=info["first_name"],
        last_name=info["last_name"],
        username=info["username"],
    )
    chat_id = _chat_id(update)
    if not await ConsentService(ctx.db).has_accepted_terms(user.id):
        # Сначала consent; deep-link потеряется, но это вынужденный шаг
        await ctx.send(chat_id, texts.DISCLAIMER, consent_keyboard())
        return
    from app.bot.handlers.catalog import render_event_card_new

    rendered = await render_event_card_new(ctx, chat_id, user.id, event_id)
    if not rendered:
        await ctx.send(chat_id, texts.MENU, main_menu())


async def handle_fallback_message(update: dict, ctx: BotContext) -> None:
    """Свободное сообщение от юзера (вне диалога записи).

    - Нет согласия → дисклеймер.
    - Есть согласие, текст ≥2 символов → поиск по каталогу.
    - Иначе → меню (с подсказкой о минимуме 2 символов для коротких).
    """
    info = _user_from_update(update)
    user = await ctx.get_or_create_user(
        info["user_id"], first_name=info["first_name"],
        last_name=info["last_name"], username=info["username"],
    )
    chat_id = _chat_id(update)
    if not await ConsentService(ctx.db).has_accepted_terms(user.id):
        await ctx.send(chat_id, texts.DISCLAIMER, consent_keyboard())
        return
    message = update.get("message") or {}
    body = message.get("body") or {}
    raw_text = (body.get("text") or "").strip()
    if not raw_text:
        from app.bot.keyboards import main_menu
        await ctx.send(chat_id, texts.MENU, main_menu())
        return
    if len(raw_text) < 2:
        from app.bot.keyboards import main_menu
        await ctx.send(chat_id, texts.SEARCH_TOO_SHORT, main_menu())
        return
    from app.bot.handlers.catalog import render_search_results
    await render_search_results(ctx, chat_id, raw_text)


async def handle_bot_stopped(update: dict, ctx: BotContext) -> None:
    info = _user_from_update(update)
    user = (
        await ctx.db.execute(select(User).where(User.max_user_id == info["user_id"]))
    ).scalar_one_or_none()
    if user is not None:
        user.is_active = False
        await ctx.db.flush()


async def handle_callback(update: dict, ctx: BotContext, action: str, args: list[str]) -> None:
    """action == 'terms' — пользователь принял условия использования."""
    callback = update["callback"]
    info = _user_from_update(update)
    user = await ctx.get_or_create_user(
        info["user_id"],
        first_name=info["first_name"],
        last_name=info["last_name"],
        username=info["username"],
    )
    consent_svc = ConsentService(ctx.db)
    if not await consent_svc.has_accepted_terms(user.id):
        await consent_svc.record(
            user_id=user.id,
            kind=ConsentKind.TERMS,
            doc_version=ConsentService.CURRENT_TERMS_VERSION,
        )
        await ctx.db.flush()
    await ctx.edit(callback["callback_id"], texts.MENU, main_menu())
