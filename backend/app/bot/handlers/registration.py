"""Диалог регистрации: старт, phone-consent, слоты, форма по шагам, подтверждение."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.bot import texts
from app.bot.context import BotContext, extract_phone_from_contact
from app.bot.handlers.onboarding import _chat_id, _user_from_update
from app.bot.keyboards import (
    confirm_keyboard, consent_field_keyboard, consent_keyboard, free_input_cancel,
    main_menu, multi_select_keyboard, phone_consent_keyboard, request_contact_keyboard,
    select_field_keyboard, slot_keyboard,
)
from app.models.bot_dialog import BotDialog, DialogState
from app.models.consent_log import ConsentKind
from app.models.event import Event, EventStatus
from app.models.event_field import EventField, FieldType
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User
from app.services.consent import ConsentService
from app.services.form_field import FormFieldService, ValidationError
from app.services.registration import RegistrationService
from app.services.slot import SlotService

logger = logging.getLogger(__name__)
_ACTIVE_DIALOG = (DialogState.ASKING_FIELD, DialogState.CONFIRMING)
_FREE_INPUT_TYPES = (
    FieldType.TEXT, FieldType.TEXTAREA, FieldType.EMAIL, FieldType.NUMBER, FieldType.DATE,
)


async def _event_fields(ctx: BotContext, event_id) -> list[EventField]:
    stmt = select(EventField).where(EventField.event_id == event_id).order_by(EventField.order)
    return list((await ctx.db.execute(stmt)).scalars().all())


async def _get_dialog(ctx: BotContext, user_id, event_id) -> BotDialog | None:
    stmt = select(BotDialog).where(
        BotDialog.user_id == user_id, BotDialog.event_id == event_id
    )
    return (await ctx.db.execute(stmt)).scalar_one_or_none()


async def _active_dialog(ctx: BotContext, user_id) -> BotDialog | None:
    """Единственный активный диалог регистрации пользователя (если есть)."""
    stmt = (
        select(BotDialog)
        .where(BotDialog.user_id == user_id, BotDialog.state.in_(_ACTIVE_DIALOG))
        .order_by(BotDialog.updated_at.desc())
        .limit(1)
    )
    return (await ctx.db.execute(stmt)).scalar_one_or_none()


async def _drop_other_dialogs(ctx: BotContext, user_id, keep_event_id) -> None:
    """Один активный диалог на юзера: прочие незавершённые — удаляем."""
    stmt = select(BotDialog).where(
        BotDialog.user_id == user_id, BotDialog.event_id != keep_event_id
    )
    for d in (await ctx.db.execute(stmt)).scalars().all():
        if d.state in _ACTIVE_DIALOG:
            await ctx.db.delete(d)
    await ctx.db.flush()


async def _start_registration(
    ctx: BotContext, user: User, event: Event, chat_id: int, *, skip_phone: bool = False
) -> None:
    """Проверяет согласия, заводит диалог, показывает слоты или первое поле."""
    consent_svc = ConsentService(ctx.db)
    if not await consent_svc.has_accepted_terms(user.id):
        await ctx.send(chat_id, texts.TERMS_REQUIRED, consent_keyboard())
        return

    fields = await _event_fields(ctx, event.id)
    has_phone = any(f.field_type == FieldType.PHONE for f in fields)
    if has_phone and not await consent_svc.has_accepted_phone(user.id) and not skip_phone:
        await ctx.send(chat_id, texts.PHONE_CONSENT, phone_consent_keyboard(str(event.id)))
        return

    existing = (await ctx.db.execute(
        select(Registration).where(
            Registration.user_id == user.id,
            Registration.event_id == event.id,
            Registration.status.in_(
                [RegistrationStatus.CONFIRMED, RegistrationStatus.WAITLIST, RegistrationStatus.PENDING]
            ),
        )
    )).scalar_one_or_none()
    if existing is not None:
        await ctx.send(chat_id, texts.ALREADY_REGISTERED, main_menu())
        return

    await _drop_other_dialogs(ctx, user.id, event.id)
    dialog = await _get_dialog(ctx, user.id, event.id)
    if dialog is None:
        dialog = BotDialog(user_id=user.id, event_id=event.id, answers={})
        ctx.db.add(dialog)
    dialog.state = DialogState.ASKING_FIELD
    dialog.current_field_index = 0
    dialog.answers = {}
    dialog.slot_id = None
    dialog.skip_phone = skip_phone
    await ctx.db.flush()

    from app.bot.analytics import log_bot_event
    await log_bot_event(ctx.db, user.id, event.id, "form_start")

    if event.slots_enabled and dialog.slot_id is None:
        await _show_slots(ctx, event, chat_id)
        return
    await _ask_current_field(ctx, dialog, event, fields, chat_id)


async def _show_slots(ctx: BotContext, event: Event, chat_id: int) -> None:
    slots = await SlotService(ctx.db).list_for_event(event.id)
    pairs: list[tuple[str, str]] = []
    for s in slots:
        remaining = await SlotService(ctx.db).remaining_seats(s.id)
        cap = "без ограничений" if remaining is None else f"{remaining} мест"
        label = s.label or s.starts_at.strftime("%d.%m %H:%M")
        pairs.append((str(s.id), f"{label} · {cap}"))
    if not pairs:
        await ctx.send(chat_id, "Для мероприятия пока нет доступных слотов.", main_menu())
        return
    await ctx.send(chat_id, texts.SLOT_PICK, slot_keyboard(pairs))


async def _ask_current_field(
    ctx: BotContext, dialog: BotDialog, event: Event, fields: list[EventField], chat_id: int
) -> None:
    """Шлёт вопрос по текущему полю; если поля кончились — сводку."""
    idx = dialog.current_field_index

    # Пропуск phone-поля если пользователь отказался от телефона.
    while idx < len(fields) and fields[idx].field_type == FieldType.PHONE and dialog.skip_phone:
        idx += 1
    if idx != dialog.current_field_index:
        dialog.current_field_index = idx
        await ctx.db.flush()

    if idx >= len(fields):
        await _show_summary(ctx, dialog, event, fields, chat_id)
        return
    field = fields[idx]
    prompt = f"Шаг {idx + 1}/{len(fields)}\n\n{field.label}"
    if field.required:
        prompt += " *"
    if field.hint:
        prompt += f"\n{field.hint}"

    if field.field_type == FieldType.PHONE:
        await ctx.send(chat_id, prompt + "\n\nНажмите кнопку ниже или введите номер вручную.",
                       request_contact_keyboard())
    elif field.field_type == FieldType.SELECT:
        await ctx.send(chat_id, prompt, select_field_keyboard(field.options or []))
    elif field.field_type == FieldType.MULTI_SELECT:
        selected = dialog.answers.get(field.key) or []
        await ctx.send(chat_id, prompt, multi_select_keyboard(field.options or [], selected))
    elif field.field_type == FieldType.CONSENT:
        await ctx.send(chat_id, prompt, consent_field_keyboard())
    else:
        await ctx.send(chat_id, prompt, free_input_cancel())


async def _show_summary(ctx, dialog, event, fields, chat_id) -> None:
    """Сводка ответов + кнопки подтверждения. Состояние → CONFIRMING."""
    dialog.state = DialogState.CONFIRMING
    await ctx.db.flush()

    lines = ["📝 Проверьте данные записи:", ""]
    lines.append(f"Мероприятие: {event.title}")
    lines.append(f"Дата: {event.starts_at.strftime('%d.%m.%Y %H:%M')}")
    lines.append(f"Формат: {texts.FORMAT_LABELS[event.format.value]}")
    if dialog.slot_id is not None:
        slot = await SlotService(ctx.db).get(dialog.slot_id)
        if slot is not None:
            label = slot.label or slot.starts_at.strftime("%d.%m %H:%M")
            lines.append(f"Время: {label}")
    by_key = {f.key: f for f in fields}
    for key, value in dialog.answers.items():
        field = by_key.get(key)
        label = field.label if field is not None else key
        if isinstance(value, list):
            shown = ", ".join(str(v) for v in value)
        elif value is True:
            shown = "да"
        else:
            shown = str(value)
        lines.append(f"{label}: {shown}")
    lines += ["", texts.SUMMARY_CANCEL_REMINDER, "", "Всё верно?"]
    await ctx.send(chat_id, "\n".join(lines), confirm_keyboard(str(event.id)))


async def handle_callback(update: dict, ctx: BotContext, action: str, args: list[str]) -> None:
    callback = update["callback"]
    callback_id = callback["callback_id"]
    chat_id = _chat_id(update)
    info = _user_from_update(update)
    user = await ctx.get_or_create_user(
        info["user_id"], first_name=info["first_name"],
        last_name=info["last_name"], username=info["username"],
    )

    if action == "rg":
        event = (await ctx.db.execute(
            select(Event).where(Event.id == args[0])
        )).scalar_one_or_none()
        if event is None or event.status != EventStatus.PUBLISHED:
            await ctx.toast(callback_id, "Мероприятие недоступно.")
            return
        await ctx.toast(callback_id, "Начинаем запись…")
        await _start_registration(ctx, user, event, chat_id)
        return

    if action == "phx":
        event = (await ctx.db.execute(
            select(Event).where(Event.id == args[0])
        )).scalar_one_or_none()
        if event is None or event.status != EventStatus.PUBLISHED:
            await ctx.toast(callback_id, "Мероприятие недоступно.")
            return
        await ctx.toast(callback_id, "Продолжаем без телефона.")
        await _start_registration(ctx, user, event, chat_id, skip_phone=True)
        return

    if action == "ph":
        consent_svc = ConsentService(ctx.db)
        if not await consent_svc.has_accepted_phone(user.id):
            await consent_svc.record(
                user_id=user.id, kind=ConsentKind.PHONE,
                doc_version=ConsentService.CURRENT_PHONE_VERSION,
            )
            await ctx.db.flush()
        event = (await ctx.db.execute(
            select(Event).where(Event.id == args[0])
        )).scalar_one_or_none()
        if event is None:
            await ctx.toast(callback_id, "Мероприятие недоступно.")
            return
        await ctx.toast(callback_id, "Согласие сохранено.")
        await _start_registration(ctx, user, event, chat_id)
        return

    if action == "sl":
        slot = await SlotService(ctx.db).get(args[0])
        if slot is None:
            await ctx.toast(callback_id, "Слот не найден.")
            return
        event = (await ctx.db.execute(
            select(Event).where(Event.id == slot.event_id)
        )).scalar_one()
        dialog = await _get_dialog(ctx, user.id, event.id)
        if dialog is None or dialog.state not in _ACTIVE_DIALOG:
            await ctx.toast(callback_id, "Диалог записи не найден, начните заново.")
            return
        dialog.slot_id = slot.id
        await ctx.db.flush()
        await ctx.toast(callback_id, "Время выбрано.")
        fields = await _event_fields(ctx, event.id)
        await _ask_current_field(ctx, dialog, event, fields, chat_id)
        return

    await _handle_dialog_callback(update, ctx, action, args)


async def handle_dialog_message(update: dict, ctx: BotContext) -> bool:
    """True, если сообщение — ответ в активном диалоге регистрации."""
    message = update.get("message") or {}
    sender = message.get("sender") or {}
    user_id = sender.get("user_id")
    if user_id is None:
        return False
    user = (await ctx.db.execute(
        select(User).where(User.max_user_id == user_id)
    )).scalar_one_or_none()
    if user is None:
        return False
    dialog = await _active_dialog(ctx, user.id)
    if dialog is None:
        return False

    chat_id = _chat_id(update)
    event = (await ctx.db.execute(
        select(Event).where(Event.id == dialog.event_id)
    )).scalar_one()
    fields = await _event_fields(ctx, event.id)

    if dialog.state == DialogState.CONFIRMING:
        await ctx.send(chat_id, texts.CONFIRM_HINT, confirm_keyboard(str(event.id)))
        return True

    if event.slots_enabled and dialog.slot_id is None:
        await ctx.send(chat_id, texts.SLOT_REQUIRED_RETRY)
        await _show_slots(ctx, event, chat_id)
        return True

    idx = dialog.current_field_index
    if idx >= len(fields):
        await _show_summary(ctx, dialog, event, fields, chat_id)
        return True
    field = fields[idx]

    if field.field_type in (FieldType.SELECT, FieldType.MULTI_SELECT, FieldType.CONSENT):
        await ctx.send(chat_id, "Выберите вариант кнопкой ниже.")
        await _ask_current_field(ctx, dialog, event, fields, chat_id)
        return True

    body = message.get("body") or {}
    raw_value: str | None
    if field.field_type == FieldType.PHONE:
        raw_value = extract_phone_from_contact(body.get("attachments") or [])
        if raw_value is None:
            raw_value = (body.get("text") or "").strip()
    else:
        raw_value = (body.get("text") or "").strip()

    try:
        coerced = FormFieldService(ctx.db).validate_value(field, raw_value)
    except ValidationError as e:
        await ctx.send(chat_id, f"⚠️ {field.label}: {e.message}. Попробуйте ещё раз.")
        await _ask_current_field(ctx, dialog, event, fields, chat_id)
        return True

    answers = dict(dialog.answers)
    answers[field.key] = coerced
    dialog.answers = answers
    dialog.current_field_index = idx + 1
    await ctx.db.flush()
    await _ask_current_field(ctx, dialog, event, fields, chat_id)
    return True


async def _handle_dialog_callback(update, ctx, action, args) -> None:
    """fv: / fdone: ввод select/multi_select/consent; ab: прервать; ok: Task 8."""
    callback = update["callback"]
    callback_id = callback["callback_id"]
    chat_id = _chat_id(update)
    info = _user_from_update(update)
    user = (await ctx.db.execute(
        select(User).where(User.max_user_id == info["user_id"])
    )).scalar_one_or_none()

    if action == "ab":
        if user is not None:
            dialog = await _active_dialog(ctx, user.id)
            if dialog is not None:
                await ctx.db.delete(dialog)
                await ctx.db.flush()
        await ctx.edit(callback_id, texts.DIALOG_ABORTED, main_menu())
        return

    if user is None:
        await ctx.toast(callback_id, "Диалог не найден, начните заново.")
        return
    dialog = await _active_dialog(ctx, user.id)
    if dialog is None:
        await ctx.toast(callback_id, "Диалог записи не найден, начните заново.")
        return
    event = (await ctx.db.execute(
        select(Event).where(Event.id == dialog.event_id)
    )).scalar_one()
    fields = await _event_fields(ctx, event.id)

    if action == "ok":
        await _handle_confirm(ctx, dialog, event, fields, callback_id, chat_id)
        return

    idx = dialog.current_field_index
    if idx >= len(fields):
        await ctx.toast(callback_id, "Все поля заполнены.")
        return
    field = fields[idx]

    if action == "fv":
        opt_index = int(args[0]) if args and args[0].isdigit() else -1
        if field.field_type == FieldType.SELECT:
            options = field.options or []
            if not (0 <= opt_index < len(options)):
                await ctx.toast(callback_id, "Вариант не найден.")
                return
            answers = dict(dialog.answers)
            answers[field.key] = options[opt_index]["value"]
            dialog.answers = answers
            dialog.current_field_index = idx + 1
            await ctx.db.flush()
            await ctx.toast(callback_id, "Принято.")
            await _ask_current_field(ctx, dialog, event, fields, chat_id)
            return
        if field.field_type == FieldType.CONSENT:
            answers = dict(dialog.answers)
            answers[field.key] = True
            dialog.answers = answers
            dialog.current_field_index = idx + 1
            await ctx.db.flush()
            await ctx.toast(callback_id, "Принято.")
            await _ask_current_field(ctx, dialog, event, fields, chat_id)
            return
        if field.field_type == FieldType.MULTI_SELECT:
            options = field.options or []
            if not (0 <= opt_index < len(options)):
                await ctx.toast(callback_id, "Вариант не найден.")
                return
            value = options[opt_index]["value"]
            current = list(dialog.answers.get(field.key) or [])
            if value in current:
                current.remove(value)
            else:
                current.append(value)
            answers = dict(dialog.answers)
            answers[field.key] = current
            dialog.answers = answers
            await ctx.db.flush()
            await ctx.edit(
                callback_id,
                f"{field.label}{' *' if field.required else ''}",
                multi_select_keyboard(options, current),
            )
            return
        await ctx.toast(callback_id, "Это поле вводится иначе.")
        return

    if action == "fdone":
        if field.field_type != FieldType.MULTI_SELECT:
            await ctx.toast(callback_id, "Кнопка недоступна для этого поля.")
            return
        chosen = list(dialog.answers.get(field.key) or [])
        if field.required and not chosen:
            await ctx.toast(callback_id, "Выберите хотя бы один вариант.")
            return
        dialog.current_field_index = idx + 1
        await ctx.db.flush()
        await ctx.toast(callback_id, "Принято.")
        await _ask_current_field(ctx, dialog, event, fields, chat_id)
        return

    await ctx.toast(callback_id, "Неизвестное действие.")


async def _handle_confirm(ctx, dialog, event, fields, callback_id, chat_id) -> None:
    """ok: создать регистрацию, сообщить short_code/waitlist, удалить диалог."""
    if dialog.state != DialogState.CONFIRMING:
        await ctx.toast(callback_id, "Сначала заполните форму.")
        return
    reg_svc = RegistrationService(ctx.db)
    try:
        reg = await reg_svc.register(
            user_id=dialog.user_id,
            event_id=event.id,
            answers=dialog.answers,
            slot_id=dialog.slot_id,
        )
    except ValidationError as e:
        await ctx.toast(callback_id, f"Ошибка в поле «{e.field_key}»: {e.message}")
        return

    from app.bot.analytics import log_bot_event
    await log_bot_event(ctx.db, dialog.user_id, event.id, "confirm")

    await ctx.db.delete(dialog)
    await ctx.db.flush()

    if reg.status == RegistrationStatus.WAITLIST:
        position = reg.waitlist_position or 1
        await ctx.edit(callback_id, texts.waitlist_text(event.title, position), main_menu())
        return

    when = event.starts_at.strftime("%d.%m.%Y %H:%M")
    text = texts.confirmed_text(
        event.title, reg.short_code or "—", when, event.location
    )
    from app.bot.keyboards import confirmed_registration_keyboard
    from app.services.calendar_links import apple_ics_url, google_url, outlook_url, yandex_url

    cal_links: list[tuple[str, str]] = []
    try:
        cal_links = [
            ("📅 Google", google_url(event)),
            ("📅 Яндекс", yandex_url(event)),
            ("📅 Outlook", outlook_url(event)),
            ("🍏 Apple (.ics)", apple_ics_url(event.id)),
        ]
    except Exception:
        logger.exception("calendar links build failed for event=%s", event.id)

    await ctx.edit(
        callback_id,
        text,
        confirmed_registration_keyboard(str(reg.id), calendar_links=cal_links),
    )
