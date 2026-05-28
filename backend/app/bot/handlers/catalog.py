"""Меню, каталог мероприятий, карточка события, помощь, share."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone as _tz

from sqlalchemy import func, select

from app.bot import texts
from app.bot.catalog_filter import CatalogFilter
from app.bot.context import BotContext
from app.bot.handlers.onboarding import _chat_id, _user_from_update
from app.bot.keyboards import (
    back_to_menu, catalog_keyboard, category_picker_keyboard,
    date_picker_keyboard, event_card_keyboard, format_picker_keyboard, main_menu,
    search_empty_keyboard, search_prompt_keyboard, search_results_keyboard,
)
from app.models.event import Event, EventStatus
from app.models.registration import Registration, RegistrationStatus
from app.services.capacity import CapacityService

_DATE_FMT = "%d.%m.%Y %H:%M"
_ACTIVE = (RegistrationStatus.CONFIRMED, RegistrationStatus.WAITLIST, RegistrationStatus.PENDING)
CATALOG_PAGE_SIZE = 8


def _format_dt(dt: datetime) -> str:
    return dt.strftime(_DATE_FMT)


_MSK = _tz(timedelta(hours=3))


def _msk_end_of_today(now: datetime | None = None) -> datetime:
    """Конец текущего московского дня (23:59:59.999999 МСК) в UTC.

    `now` — для тестов; иначе берём datetime.now(UTC).
    """
    base = now if now is not None else datetime.now(UTC)
    msk_now = base.astimezone(_MSK)
    end_msk = msk_now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return end_msk.astimezone(UTC)


async def _filtered_events(
    ctx: BotContext, filt: CatalogFilter, *, offset: int = 0, limit: int = 8
) -> list[Event]:
    now = datetime.now(UTC)
    stmt = (
        select(Event)
        .where(Event.status == EventStatus.PUBLISHED, Event.starts_at >= now)
        .order_by(Event.starts_at)
        .offset(offset)
        .limit(limit)
    )
    if filt.category is not None:
        stmt = stmt.where(Event.event_type == filt.category)
    if filt.format is not None:
        stmt = stmt.where(Event.format == filt.format)
    if filt.date == "today":
        stmt = stmt.where(Event.starts_at <= _msk_end_of_today(now))
    elif filt.date == "week":
        stmt = stmt.where(Event.starts_at <= now + timedelta(days=7))
    return list((await ctx.db.execute(stmt)).scalars().all())


async def _count_filtered(ctx: BotContext, filt: CatalogFilter) -> int:
    now = datetime.now(UTC)
    stmt = select(func.count(Event.id)).where(
        Event.status == EventStatus.PUBLISHED, Event.starts_at >= now
    )
    if filt.category is not None:
        stmt = stmt.where(Event.event_type == filt.category)
    if filt.format is not None:
        stmt = stmt.where(Event.format == filt.format)
    if filt.date == "today":
        stmt = stmt.where(Event.starts_at <= _msk_end_of_today(now))
    elif filt.date == "week":
        stmt = stmt.where(Event.starts_at <= now + timedelta(days=7))
    return int((await ctx.db.execute(stmt)).scalar() or 0)


def _escape_like(query: str) -> str:
    """Экранирует %, _, \\ для LIKE — иначе пользователь может «искать всё» вводом %."""
    return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


SEARCH_LIMIT = 12
MIN_QUERY_LEN = 2


async def _search_events(ctx: BotContext, query: str, *, limit: int = SEARCH_LIMIT) -> list[Event]:
    """ILIKE-поиск по title среди опубликованных будущих мероприятий, сорт. по дате."""
    needle = f"%{_escape_like(query.strip())}%"
    now = datetime.now(UTC)
    stmt = (
        select(Event)
        .where(
            Event.status == EventStatus.PUBLISHED,
            Event.starts_at >= now,
            Event.title.ilike(needle, escape="\\"),
        )
        .order_by(Event.starts_at)
        .limit(limit)
    )
    return list((await ctx.db.execute(stmt)).scalars().all())


async def render_search_results(ctx: BotContext, chat_id: int, query: str) -> None:
    """Отправляет новое сообщение с результатами поиска (для fallback-роутинга)."""
    results = await _search_events(ctx, query)
    if not results:
        await ctx.send(chat_id, texts.SEARCH_EMPTY.format(q=query), search_empty_keyboard())
        return
    header = texts.SEARCH_RESULTS_HEADER.format(q=query, n=len(results))
    body = header
    if len(results) >= SEARCH_LIMIT:
        body = body + "\n" + texts.SEARCH_LIMIT_HINT
    pairs = [(str(e.id), e.title) for e in results]
    await ctx.send(chat_id, body, search_results_keyboard(pairs))


async def _active_registration(ctx: BotContext, user_id, event_id) -> Registration | None:
    stmt = select(Registration).where(
        Registration.user_id == user_id,
        Registration.event_id == event_id,
        Registration.status.in_(_ACTIVE),
    )
    return (await ctx.db.execute(stmt)).scalar_one_or_none()


def _event_card_text(event: Event, reg: Registration | None, seats_label: str) -> str:
    lines = [f"📌 {event.title}", ""]
    if event.description:
        lines += [event.description, ""]
    lines.append(texts.FORMAT_LABELS[event.format.value])
    lines.append(f"🗓 {_format_dt(event.starts_at)} · {event.duration_minutes} мин")
    if event.location:
        lines.append(f"📍 {event.location}")
    lines.append(seats_label)
    lines.append(texts.CANCEL_POLICY_LABELS[event.late_cancellation_policy.value])
    if (
        reg is not None
        and reg.status == RegistrationStatus.CONFIRMED
        and event.format.value != "offline"
        and event.online_url
    ):
        lines += ["", f"🔗 Ссылка на подключение: {event.online_url}"]
    if reg is not None:
        status_ru = {
            RegistrationStatus.CONFIRMED: "вы записаны",
            RegistrationStatus.WAITLIST: "вы в листе ожидания",
            RegistrationStatus.PENDING: "запись на модерации",
        }[reg.status]
        lines += ["", f"✅ Статус: {status_ru}"]
        if reg.short_code:
            lines.append(f"Код записи: {reg.short_code}")
    return "\n".join(lines)


async def _seats_label(ctx: BotContext, event: Event) -> str:
    remaining = await CapacityService(ctx.db).remaining_seats(event.id)
    if remaining is None:
        return "🟢 без ограничения по местам"
    if remaining > 0:
        return f"🟢 свободно мест: {remaining}"
    if event.waitlist_enabled:
        return "🟡 мест нет — можно встать в лист ожидания"
    return "🔴 мест нет"


def _registration_window_status(event: Event, now: datetime) -> str | None:
    """None — окно открыто; 'not_yet' / 'late' — закрыто."""
    if event.registration_opens_at and now < event.registration_opens_at:
        return "not_yet"
    if event.registration_closes_at and now > event.registration_closes_at:
        return "late"
    return None


async def _show_catalog(
    ctx: BotContext, callback_id: str, page: int = 0, token: str = "---"
) -> None:
    filt = CatalogFilter.decode(token)
    total = await _count_filtered(ctx, filt)
    if total == 0:
        if filt.is_default:
            await ctx.edit(callback_id, texts.CATALOG_EMPTY, back_to_menu())
        else:
            kb = catalog_keyboard([], page=0, total_pages=1, token=token, show_reset=True)
            await ctx.edit(callback_id, texts.CATALOG_EMPTY_FILTERED, kb)
        return
    total_pages = (total + CATALOG_PAGE_SIZE - 1) // CATALOG_PAGE_SIZE
    page = max(0, min(page, total_pages - 1))
    events = await _filtered_events(
        ctx, filt, offset=page * CATALOG_PAGE_SIZE, limit=CATALOG_PAGE_SIZE
    )
    pairs = [(str(e.id), e.title) for e in events]
    header_lines = [texts.CATALOG_HEADER]
    if not filt.is_default:
        header_lines.append(texts.CATALOG_FILTER_LINE.format(summary=filt.summary_ru()))
    header_lines.append(texts.CATALOG_FOUND_LINE.format(n=total))
    header = "\n".join(header_lines)
    kb = catalog_keyboard(
        pairs, page=page, total_pages=total_pages, token=token, show_reset=not filt.is_default
    )
    await ctx.edit(callback_id, header, kb)


async def render_event_card_new(
    ctx: BotContext, chat_id: int, user_id, event_id_str: str
) -> bool:
    """Шлёт карточку события новым сообщением (для deep-link из /start).

    Возвращает True если карточка отправлена, False если событие недоступно.
    """
    try:
        event = (
            await ctx.db.execute(select(Event).where(Event.id == event_id_str))
        ).scalar_one_or_none()
    except Exception:
        event = None
    if event is None or event.status != EventStatus.PUBLISHED:
        return False
    reg = await _active_registration(ctx, user_id, event.id)
    seats_label = await _seats_label(ctx, event)
    now = datetime.now(UTC)
    window = _registration_window_status(event, now)
    remaining = await CapacityService(ctx.db).remaining_seats(event.id)
    can_register = (
        reg is None
        and window is None
        and (remaining is None or remaining > 0 or event.waitlist_enabled)
    )
    register_label = "✍️ Записаться"
    if can_register and remaining is not None and remaining <= 0 and event.waitlist_enabled:
        register_label = texts.WAITLIST_JOIN_HINT

    closed_text: str | None = None
    if reg is None:
        if window == "not_yet":
            closed_text = texts.REG_CLOSED_NOT_YET
        elif window == "late":
            closed_text = texts.REG_CLOSED_LATE
        elif remaining is not None and remaining <= 0 and not event.waitlist_enabled:
            closed_text = texts.SEATS_NONE_NO_WAITLIST

    reg_status = reg.status.value if reg is not None else None
    reg_id = str(reg.id) if reg is not None else None
    keyboard = event_card_keyboard(
        str(event.id),
        reg_status=reg_status,
        reg_id=reg_id,
        can_register=can_register,
        register_label=register_label,
        back_token="---",
    )
    text = _event_card_text(event, reg, seats_label)
    if closed_text:
        text = text + "\n\n" + closed_text
    await ctx.send(chat_id, text, keyboard)
    return True


async def _show_event_card(
    ctx: BotContext, callback_id: str, user_id, event_id_str: str, back_token: str = "---"
) -> None:
    from app.bot.analytics import log_bot_event
    await log_bot_event(ctx.db, user_id, event_id_str, "event_view")
    try:
        event = (
            await ctx.db.execute(select(Event).where(Event.id == event_id_str))
        ).scalar_one_or_none()
    except Exception:
        event = None
    if event is None or event.status != EventStatus.PUBLISHED:
        await ctx.edit(callback_id, "Мероприятие недоступно.", back_to_menu())
        return
    reg = await _active_registration(ctx, user_id, event.id)
    seats_label = await _seats_label(ctx, event)
    now = datetime.now(UTC)
    window = _registration_window_status(event, now)
    remaining = await CapacityService(ctx.db).remaining_seats(event.id)
    can_register = (
        reg is None
        and window is None
        and (remaining is None or remaining > 0 or event.waitlist_enabled)
    )
    register_label = "✍️ Записаться"
    if can_register and remaining is not None and remaining <= 0 and event.waitlist_enabled:
        register_label = texts.WAITLIST_JOIN_HINT

    closed_text: str | None = None
    if reg is None:
        if window == "not_yet":
            closed_text = texts.REG_CLOSED_NOT_YET
        elif window == "late":
            closed_text = texts.REG_CLOSED_LATE
        elif remaining is not None and remaining <= 0 and not event.waitlist_enabled:
            closed_text = texts.SEATS_NONE_NO_WAITLIST

    reg_status = reg.status.value if reg is not None else None
    reg_id = str(reg.id) if reg is not None else None
    keyboard = event_card_keyboard(
        str(event.id),
        reg_status=reg_status,
        reg_id=reg_id,
        can_register=can_register,
        register_label=register_label,
        back_token=back_token,
    )
    text = _event_card_text(event, reg, seats_label)
    if closed_text:
        text = text + "\n\n" + closed_text
    await ctx.edit(callback_id, text, keyboard)


async def handle_callback(update: dict, ctx: BotContext, action: str, args: list[str]) -> None:
    callback = update["callback"]
    callback_id = callback["callback_id"]
    info = _user_from_update(update)
    user = await ctx.get_or_create_user(
        info["user_id"], first_name=info["first_name"],
        last_name=info["last_name"], username=info["username"],
    )

    if action == "m":
        section = args[0] if args else "home"
        if section == "home":
            await ctx.edit(callback_id, texts.MENU, main_menu())
        elif section == "cat":
            page = int(args[1]) if len(args) > 1 and args[1].lstrip("-").isdigit() else 0
            token = args[2] if len(args) > 2 else "---"
            await _show_catalog(ctx, callback_id, page, token)
        elif section == "help":
            await ctx.edit(callback_id, texts.HELP, back_to_menu())
        elif section == "my":
            from app.bot.handlers import mine
            await mine.show_my_registrations(ctx, callback_id, user)
        return

    if action == "csrch":
        token = args[0] if args else "---"
        text = f"{texts.SEARCH_PROMPT_TITLE}\n\n{texts.SEARCH_PROMPT_BODY}"
        await ctx.edit(callback_id, text, search_prompt_keyboard(token))
        return

    if action in ("cpk", "dpk", "fpk"):
        page = int(args[0]) if args and args[0].lstrip("-").isdigit() else 0
        token = args[1] if len(args) > 1 else "---"
        if action == "cpk":
            await ctx.edit(callback_id, texts.PICKER_CATEGORY,
                           category_picker_keyboard(page=page, token=token, current_category_char=token[0]))
        elif action == "dpk":
            await ctx.edit(callback_id, texts.PICKER_DATE,
                           date_picker_keyboard(page=page, token=token, current_date_char=token[1]))
        else:
            await ctx.edit(callback_id, texts.PICKER_FORMAT,
                           format_picker_keyboard(page=page, token=token, current_format_char=token[2]))
        return

    if action == "ev":
        event_id_str = args[0]
        back_token = args[1] if len(args) > 1 else "---"
        await _show_event_card(ctx, callback_id, user.id, event_id_str, back_token)
        return

    if action == "sh":
        event = (
            await ctx.db.execute(select(Event).where(Event.id == args[0]))
        ).scalar_one_or_none()
        if event is None:
            await ctx.toast(callback_id, "Мероприятие не найдено.")
            return
        share = (
            f"📌 {event.title}\n"
            f"🗓 {_format_dt(event.starts_at)}\n"
        )
        if event.location:
            share += f"📍 {event.location}\n"
        share += "\nЗапись — в боте РТУ МИРЭА."
        chat_id = _chat_id(update)
        await ctx.send(chat_id, share)
        await ctx.toast(callback_id, "Сообщение отправлено — перешлите его другу.")
        return
