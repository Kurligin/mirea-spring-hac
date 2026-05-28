"""«Мои записи» и отмена регистрации из бота."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot import texts
from app.bot.context import BotContext
from app.bot.handlers.onboarding import _user_from_update
from app.bot.keyboards import (
    _callback,
    back_to_menu,
    cancel_confirm_keyboard,
    cb,
    main_menu,
    registration_detail_keyboard,
)
from app.core.event_time import EventPhase, compute_timing
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User
from app.services.notification import NotificationService
from app.services.registration import CancelError, RegistrationService

_ACTIVE = (RegistrationStatus.CONFIRMED, RegistrationStatus.WAITLIST, RegistrationStatus.PENDING)
_STATUS_RU = {
    RegistrationStatus.CONFIRMED: "✅ записаны",
    RegistrationStatus.WAITLIST: "⏳ лист ожидания",
    RegistrationStatus.PENDING: "🕓 на модерации",
    RegistrationStatus.CANCELLED: "❌ отменена",
    RegistrationStatus.REJECTED: "🚫 отклонена",
}


async def show_my_registrations(ctx: BotContext, callback_id: str, user: User) -> None:
    stmt = (
        select(Registration)
        .options(selectinload(Registration.event))
        .where(Registration.user_id == user.id)
        .order_by(Registration.created_at.desc())
    )
    regs = list((await ctx.db.execute(stmt)).scalars().all())
    active = [r for r in regs if r.status in _ACTIVE]
    if not active:
        await ctx.edit(callback_id, texts.MY_EMPTY, back_to_menu())
        return

    keyboard: list[list[dict]] = []
    for r in active:
        keyboard.append([_callback(r.event.title[:48], cb("rgd", str(r.id)))])
    keyboard.append([_callback("⬅️ В меню", cb("m", "home"))])
    await ctx.edit(callback_id, "📋 Ваши записи:", keyboard)


async def show_registration_detail(
    ctx: BotContext, callback_id: str, user: User, reg_id_str: str
) -> None:
    reg = await _load_own_registration(ctx, user.id, reg_id_str)
    if reg is None:
        await ctx.edit(callback_id, texts.REGISTRATION_NOT_FOUND, back_to_menu())
        return
    if reg.status in (RegistrationStatus.CANCELLED, RegistrationStatus.REJECTED):
        # Защита от старых callback-ов: запись уже неактивна — деталей не показываем,
        # ведём в каталог. Связано с B1 (см. post-demo scope).
        status_text = (
            "❌ Запись отменена."
            if reg.status == RegistrationStatus.CANCELLED
            else "🚫 Запись отклонена."
        )
        await ctx.edit(callback_id, status_text + "\n\nВыберите другое мероприятие.", main_menu())
        return
    event = reg.event
    status_ru = _STATUS_RU[reg.status]
    when = event.starts_at.strftime("%d.%m.%Y %H:%M")
    online_url = (
        event.online_url
        if event.format.value != "offline" and reg.status == RegistrationStatus.CONFIRMED
        else None
    )
    text = texts.reg_detail_text(
        title=event.title,
        format_label=texts.FORMAT_LABELS[event.format.value],
        when=when,
        place=event.location,
        status_ru=status_ru,
        short_code=reg.short_code,
        online_url=online_url,
        late_policy_label=texts.CANCEL_POLICY_LABELS[event.late_cancellation_policy.value],
    )
    now = datetime.now(UTC)
    timing = compute_timing(
        starts_at=event.starts_at, duration_minutes=event.duration_minutes, now=now,
    )
    # Отмена недоступна если: уже отметился, событие кончилось, или
    # идёт сейчас при политике FORBID.
    can_cancel = (
        reg.checked_in_at is None
        and timing.phase != EventPhase.FINISHED
        and not (
            timing.phase == EventPhase.IN_PROGRESS
            and event.late_cancellation_policy.value == "forbid"
        )
    )
    keyboard = registration_detail_keyboard(
        reg_id=str(reg.id),
        is_confirmed=(reg.status == RegistrationStatus.CONFIRMED),
        can_cancel=can_cancel,
        muted=reg.notifications_muted,
    )
    await ctx.edit(callback_id, text, keyboard)


async def handle_callback(update: dict, ctx: BotContext, action: str, args: list[str]) -> None:
    callback = update["callback"]
    callback_id = callback["callback_id"]
    info = _user_from_update(update)
    user = await ctx.get_or_create_user(
        info["user_id"], first_name=info["first_name"],
        last_name=info["last_name"], username=info["username"],
    )

    if action == "rgd":
        await show_registration_detail(ctx, callback_id, user, args[0])
        return

    if action == "mut":
        reg = await _load_own_registration(ctx, user.id, args[0])
        if reg is None or reg.status in (
            RegistrationStatus.CANCELLED,
            RegistrationStatus.REJECTED,
        ):
            await ctx.toast(callback_id, "Запись недоступна.")
            return
        reg.notifications_muted = not reg.notifications_muted
        await ctx.db.flush()
        await ctx.toast(
            callback_id,
            "Уведомления отключены." if reg.notifications_muted else "Уведомления включены.",
        )
        await show_registration_detail(ctx, callback_id, user, str(reg.id))
        return

    if action == "cn":
        reg = await _load_own_registration(ctx, user.id, args[0])
        if reg is None:
            await ctx.edit(callback_id, texts.REGISTRATION_NOT_FOUND, back_to_menu())
            return
        # Уже отметился на входе — отмена недоступна.
        if reg.checked_in_at is not None:
            await ctx.edit(callback_id, texts.CANCEL_AFTER_CHECKIN, back_to_menu())
            return
        event = reg.event
        timing = compute_timing(
            starts_at=event.starts_at,
            duration_minutes=event.duration_minutes,
            now=datetime.now(UTC),
        )
        # Уже закончилось → отменять нечего.
        if timing.phase == EventPhase.FINISHED:
            await ctx.edit(callback_id, texts.CANCEL_AFTER_END, back_to_menu())
            return
        # Идёт сейчас + forbid → запрещено.
        if (
            timing.phase == EventPhase.IN_PROGRESS
            and event.late_cancellation_policy.value == "forbid"
        ):
            await ctx.edit(callback_id, texts.CANCEL_LATE_FORBIDDEN, back_to_menu())
            return
        # Идёт сейчас + allow_with_mark → специальное предупреждение.
        if timing.phase == EventPhase.IN_PROGRESS:
            confirm_text = texts.CANCEL_CONFIRM_LATE.format(title=event.title)
        else:
            confirm_text = texts.CANCEL_CONFIRM.format(title=event.title)
        await ctx.edit(callback_id, confirm_text, cancel_confirm_keyboard(str(reg.id)))
        return

    if action == "cy":
        reg = await _load_own_registration(ctx, user.id, args[0])
        if reg is None:
            await ctx.edit(callback_id, texts.REGISTRATION_NOT_FOUND, back_to_menu())
            return
        if reg.status == RegistrationStatus.CANCELLED:
            await ctx.edit(callback_id, "Запись уже отменена.", back_to_menu())
            return
        title = reg.event.title
        service = RegistrationService(ctx.db)
        try:
            await service.cancel(reg.id)
        except CancelError as e:
            msg = {
                "ALREADY_CHECKED_IN": texts.CANCEL_AFTER_CHECKIN,
                "EVENT_FINISHED": texts.CANCEL_AFTER_END,
                "LATE_FORBIDDEN": texts.CANCEL_LATE_FORBIDDEN,
            }.get(e.code, texts.CANCEL_LATE_FORBIDDEN)
            await ctx.edit(callback_id, msg, back_to_menu())
            return
        if service.last_promoted is not None:
            try:
                await NotificationService(ctx.db, ctx.client).notify_promotion(service.last_promoted)
            except Exception:
                pass
        await ctx.edit(callback_id, texts.CANCEL_DONE.format(title=title), main_menu())
        return


async def _load_own_registration(ctx: BotContext, user_id, reg_id_str: str) -> Registration | None:
    try:
        stmt = (
            select(Registration)
            .options(selectinload(Registration.event))
            .where(Registration.id == reg_id_str, Registration.user_id == user_id)
        )
        return (await ctx.db.execute(stmt)).scalar_one_or_none()
    except Exception:
        return None
