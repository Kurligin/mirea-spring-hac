"""Callback-payload кодек и конструкторы inline-клавиатур MAX.

Клавиатура — list[list[dict]]; именно такую форму ждёт MaxClient.send_message.
Кнопка callback: {"type","text","payload","intent"}.
"""
from __future__ import annotations


def cb(action: str, *args: str) -> str:
    """Собрать callback-payload вида action:arg1:arg2 (≤64 байт)."""
    return ":".join([action, *args])


def parse_cb(payload: str) -> tuple[str, list[str]]:
    """Разобрать callback-payload в (action, args)."""
    parts = payload.split(":")
    return parts[0], parts[1:]


def _callback(text: str, payload: str, intent: str = "default") -> dict:
    return {"type": "callback", "text": text, "payload": payload, "intent": intent}


def _link(text: str, url: str) -> dict:
    return {"type": "link", "text": text, "url": url}


def main_menu() -> list[list[dict]]:
    return [
        [_callback("📅 Расписание", cb("m", "cat")), _callback("📋 Мои записи", cb("m", "my"))],
        [_callback("❓ Помощь", cb("m", "help"))],
    ]


def consent_keyboard() -> list[list[dict]]:
    return [[_callback("✅ Принимаю условия", cb("terms"), intent="positive")]]


def back_to_menu() -> list[list[dict]]:
    return [[_callback("⬅️ В меню", cb("m", "home"))]]


def catalog_keyboard(
    events: list[tuple[str, str]],
    *,
    page: int = 0,
    total_pages: int = 1,
    token: str = "---",
    show_reset: bool = False,
) -> list[list[dict]]:
    """events — (event_id, title) текущей страницы.

    token — 3-символьный токен фильтра (несётся в payload всех кнопок страницы).
    show_reset — отрисовать ряд «♻️ Сбросить фильтры» (только когда фильтр не дефолт).
    """
    rows: list[list[dict]] = [
        [_callback("🔎 Поиск", cb("csrch", token))],
        [
            _callback("📂 Категория", cb("cpk", str(page), token)),
            _callback("📅 Когда", cb("dpk", str(page), token)),
            _callback("🖥 Формат", cb("fpk", str(page), token)),
        ],
    ]
    for event_id, title in events:
        rows.append([_callback(title[:48], cb("ev", event_id, token))])
    if total_pages > 1:
        nav: list[dict] = []
        if page > 0:
            nav.append(_callback("◀", cb("m", "cat", str(page - 1), token)))
        nav.append(_callback(f"{page + 1}/{total_pages}", cb("m", "cat", str(page), token)))
        if page < total_pages - 1:
            nav.append(_callback("▶", cb("m", "cat", str(page + 1), token)))
        rows.append(nav)
    if show_reset:
        rows.append([_callback("♻️ Сбросить фильтры", cb("m", "cat", "0", "---"))])
    rows.append([_callback("⬅️ В меню", cb("m", "home"))])
    return rows


def category_picker_keyboard(*, page: int, token: str, current_category_char: str) -> list[list[dict]]:
    opts = [
        ("Все", "-"),
        ("День открытых дверей", "o"),
        ("Мастер-класс", "m"),
        ("Олимпиада", "l"),
        ("Консультация", "c"),
        ("Прочее", "e"),
    ]
    rows: list[list[dict]] = []
    for label, code in opts:
        new_token = code + token[1] + token[2]
        mark = "✅ " if code == current_category_char else ""
        rows.append([_callback(mark + label, cb("m", "cat", "0", new_token))])
    rows.append([_callback("⬅️ Назад", cb("m", "cat", str(page), token))])
    return rows


def date_picker_keyboard(*, page: int, token: str, current_date_char: str) -> list[list[dict]]:
    opts = [("Все", "-"), ("Сегодня", "t"), ("На этой неделе", "w")]
    rows: list[list[dict]] = []
    for label, code in opts:
        new_token = token[0] + code + token[2]
        mark = "✅ " if code == current_date_char else ""
        rows.append([_callback(mark + label, cb("m", "cat", "0", new_token))])
    rows.append([_callback("⬅️ Назад", cb("m", "cat", str(page), token))])
    return rows


def format_picker_keyboard(*, page: int, token: str, current_format_char: str) -> list[list[dict]]:
    opts = [("Все", "-"), ("Очно", "f"), ("Онлайн", "n"), ("Гибрид", "h")]
    rows: list[list[dict]] = []
    for label, code in opts:
        new_token = token[0] + token[1] + code
        mark = "✅ " if code == current_format_char else ""
        rows.append([_callback(mark + label, cb("m", "cat", "0", new_token))])
    rows.append([_callback("⬅️ Назад", cb("m", "cat", str(page), token))])
    return rows


def search_prompt_keyboard(token: str) -> list[list[dict]]:
    """Экран-приглашение к поиску — одна кнопка «Назад к каталогу»."""
    return [[_callback("⬅️ Назад к каталогу", cb("m", "cat", "0", token))]]


def search_results_keyboard(events: list[tuple[str, str]]) -> list[list[dict]]:
    """Список результатов поиска без токена в payload — возврат из карточки → дефолтный каталог."""
    rows = [[_callback(title[:48], cb("ev", event_id))] for event_id, title in events]
    rows.append([_callback("⬅️ В меню", cb("m", "home"))])
    return rows


def search_empty_keyboard() -> list[list[dict]]:
    return [
        [_callback("📅 Открыть каталог", cb("m", "cat", "0", "---"))],
        [_callback("⬅️ В меню", cb("m", "home"))],
    ]


def event_card_keyboard(
    event_id: str,
    *,
    reg_status: str | None,
    reg_id: str | None,
    can_register: bool = True,
    register_label: str = "✍️ Записаться",
    back_token: str = "---",
) -> list[list[dict]]:
    """reg_status — None | 'confirmed' | 'waitlist' | 'pending'.

    can_register=False прячет кнопку записи (нет мест без waitlist / закрытая регистрация).
    register_label — лейбл кнопки записи (например, «⏳ Встать в лист ожидания»).
    back_token — токен фильтра в кнопке «К расписанию» (чтобы вернуть на отфильтрованный список).
    """
    rows: list[list[dict]] = []
    if reg_status is None:
        if can_register:
            rows.append([_callback(register_label, cb("rg", event_id), intent="positive")])
    elif reg_status == "confirmed":
        rows.append([_callback("❌ Отменить запись", cb("cn", reg_id or ""), intent="negative")])
    else:
        rows.append([_callback("⏳ Отменить (я в очереди)", cb("cn", reg_id or ""), intent="negative")])
    rows.append([_callback("🔗 Поделиться", cb("sh", event_id))])
    rows.append([_callback("⬅️ К расписанию", cb("m", "cat", "0", back_token))])
    return rows


def slot_keyboard(slots: list[tuple[str, str]]) -> list[list[dict]]:
    """slots — список (slot_id, label)."""
    rows = [[_callback(label, cb("sl", slot_id))] for slot_id, label in slots]
    rows.append([_callback("❌ Отмена", cb("ab"))])
    return rows


def phone_consent_keyboard(event_id: str) -> list[list[dict]]:
    return [
        [_callback("✅ Дать согласие", cb("ph", event_id), intent="positive")],
        [_callback("➡️ Без телефона, продолжить", cb("phx", event_id))],
        [_callback("⬅️ К мероприятию", cb("ev", event_id))],
    ]


def request_contact_keyboard() -> list[list[dict]]:
    return [
        [{"type": "request_contact", "text": "📱 Поделиться контактом"}],
        [_callback("❌ Отмена", cb("ab"))],
    ]


def select_field_keyboard(options: list[dict]) -> list[list[dict]]:
    """options — список {"value","label"}; payload — индекс опции."""
    rows = [[_callback(opt["label"], cb("fv", str(i)))] for i, opt in enumerate(options)]
    rows.append([_callback("❌ Отмена", cb("ab"))])
    return rows


def multi_select_keyboard(options: list[dict], selected: list[str]) -> list[list[dict]]:
    rows = []
    for i, opt in enumerate(options):
        mark = "☑️ " if opt["value"] in selected else "⬜️ "
        rows.append([_callback(mark + opt["label"], cb("fv", str(i)))])
    rows.append([_callback("✅ Готово", cb("fdone"), intent="positive")])
    rows.append([_callback("❌ Отмена", cb("ab"))])
    return rows


def consent_field_keyboard() -> list[list[dict]]:
    return [
        [_callback("✅ Подтверждаю", cb("fv", "1"), intent="positive")],
        [_callback("❌ Отмена", cb("ab"))],
    ]


def confirm_keyboard(event_id: str) -> list[list[dict]]:
    return [
        [_callback("✅ Подтвердить запись", cb("ok", event_id), intent="positive")],
        [_callback("❌ Отмена", cb("ab"), intent="negative")],
    ]


def free_input_cancel() -> list[list[dict]]:
    """Клавиатура для шага со свободным вводом — только «Отмена»."""
    return [[_callback("❌ Отмена", cb("ab"))]]


def my_registration_keyboard(reg_id: str, can_cancel: bool) -> list[list[dict]]:
    rows: list[list[dict]] = []
    if can_cancel:
        rows.append([_callback("❌ Отменить", cb("cn", reg_id), intent="negative")])
    return rows


def cancel_confirm_keyboard(reg_id: str) -> list[list[dict]]:
    return [
        [_callback("Да, отменить", cb("cy", reg_id), intent="negative")],
        [_callback("Оставить запись", cb("m", "my"))],
    ]


def qr_keyboard(reg_id: str) -> list[list[dict]]:
    """Клавиатура под QR-сообщением: ручной рефреш + закрыть + меню."""
    return [
        [_callback("🔄 Обновить", cb("qrr", reg_id))],
        [_callback("🙈 Скрыть QR", cb("qrc", reg_id))],
        [_callback("⬅️ В меню", cb("m", "home"))],
    ]


def confirmed_registration_keyboard(
    reg_id: str,
    *,
    calendar_links: list[tuple[str, str]] | None = None,
) -> list[list[dict]]:
    """Клавиатура итогового сообщения после успешной записи (CONFIRMED).

    calendar_links — опционально список (label, url) для добавления в календарь;
    дорисовываем их парами в конце клавиатуры. Невалидные (не https) фильтруются
    — MAX отвергает кнопки с относительным URL и ломает всю клавиатуру.
    """
    rows: list[list[dict]] = [
        [_callback("🎫 Показать QR", cb("qr", reg_id), intent="positive")],
        [_callback("❌ Отменить запись", cb("cn", reg_id), intent="negative")],
        [_callback("⬅️ В меню", cb("m", "home"))],
    ]
    if calendar_links:
        valid = [(t, u) for t, u in calendar_links if u.startswith("https://")]
        for i in range(0, len(valid), 2):
            rows.append([_link(t, u) for t, u in valid[i:i + 2]])
    return rows


def registration_detail_keyboard(
    *,
    reg_id: str,
    is_confirmed: bool,
    can_cancel: bool,
    muted: bool,
) -> list[list[dict]]:
    rows: list[list[dict]] = []
    if is_confirmed:
        rows.append([_callback("🎫 Показать QR", cb("qr", reg_id), intent="positive")])
    mute_label = "🔕 Уведомления: выкл" if muted else "🔔 Уведомления: вкл"
    rows.append([_callback(mute_label, cb("mut", reg_id))])
    cancel_row: list[dict] = []
    if can_cancel:
        cancel_row.append(_callback("❌ Отменить", cb("cn", reg_id), intent="negative"))
    cancel_row.append(_callback("⬅️ Назад", cb("m", "my")))
    rows.append(cancel_row)
    return rows
