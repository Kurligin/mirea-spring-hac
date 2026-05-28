from app.bot.keyboards import (
    cb, parse_cb, main_menu, catalog_keyboard, event_card_keyboard,
    slot_keyboard, confirm_keyboard, select_field_keyboard,
)


def test_cb_roundtrip():
    assert cb("ev", "abc-123") == "ev:abc-123"
    action, args = parse_cb("ev:abc-123")
    assert action == "ev"
    assert args == ["abc-123"]


def test_parse_cb_no_args():
    action, args = parse_cb("m:home")
    assert action == "m"
    assert args == ["home"]


def test_parse_cb_single_token():
    action, args = parse_cb("fdone")
    assert action == "fdone"
    assert args == []


def test_main_menu_has_catalog_and_my():
    kb = main_menu()
    payloads = [b["payload"] for row in kb for b in row if b["type"] == "callback"]
    assert "m:cat" in payloads
    assert "m:my" in payloads


def test_catalog_keyboard_one_button_per_event():
    events = [("id-1", "Событие А"), ("id-2", "Событие Б")]
    kb = catalog_keyboard(events)
    payloads = [b["payload"] for row in kb for b in row if b["type"] == "callback"]
    # токен по умолчанию "---" несётся в payload
    assert "ev:id-1:---" in payloads
    assert "ev:id-2:---" in payloads


def test_event_card_not_registered_shows_signup():
    kb = event_card_keyboard("ev-1", reg_status=None, reg_id=None)
    payloads = [b["payload"] for row in kb for b in row if b.get("payload")]
    assert "rg:ev-1" in payloads


def test_event_card_confirmed_shows_cancel_negative():
    kb = event_card_keyboard("ev-1", reg_status="confirmed", reg_id="r-9")
    flat = [b for row in kb for b in row]
    cancel = [b for b in flat if b.get("payload") == "cn:r-9"]
    assert cancel and cancel[0]["intent"] == "negative"


def test_slot_keyboard_buttons_reference_slot_ids():
    kb = slot_keyboard([("s-1", "10:00 · 5 мест"), ("s-2", "11:00 · нет мест")])
    payloads = [b["payload"] for row in kb for b in row if b["type"] == "callback"]
    assert "sl:s-1" in payloads and "sl:s-2" in payloads


def test_confirm_keyboard_positive_intent():
    kb = confirm_keyboard("ev-7")
    flat = [b for row in kb for b in row]
    ok = [b for b in flat if b.get("payload") == "ok:ev-7"]
    assert ok and ok[0]["intent"] == "positive"


def test_select_field_keyboard_indexes_options():
    kb = select_field_keyboard([{"value": "a", "label": "А"}, {"value": "b", "label": "Б"}])
    payloads = [b["payload"] for row in kb for b in row if b["type"] == "callback"]
    assert "fv:0" in payloads and "fv:1" in payloads


def test_event_card_keyboard_hides_register_when_cannot():
    from app.bot.keyboards import event_card_keyboard
    kb = event_card_keyboard(
        "evt1", reg_status=None, reg_id=None, can_register=False
    )
    flat = [b["text"] for row in kb for b in row]
    assert not any("Записаться" in t or "лист ожидания" in t for t in flat)


def test_event_card_keyboard_uses_waitlist_label():
    from app.bot.keyboards import event_card_keyboard
    kb = event_card_keyboard(
        "evt1", reg_status=None, reg_id=None,
        can_register=True, register_label="⏳ Встать в лист ожидания",
    )
    flat = [b["text"] for row in kb for b in row]
    assert any("лист ожидания" in t for t in flat)


def test_confirmed_registration_keyboard_has_show_qr_and_cancel():
    from app.bot.keyboards import confirmed_registration_keyboard
    kb = confirmed_registration_keyboard("reg-uuid")
    flat = [b for row in kb for b in row]
    texts_ = [b["text"] for b in flat]
    payloads = [b["payload"] for b in flat if "payload" in b]
    assert any("Показать QR" in t for t in texts_)
    assert any("Отменить запись" in t for t in texts_)
    assert "qr:reg-uuid" in payloads
    assert "cn:reg-uuid" in payloads


def test_catalog_keyboard_carries_token_in_event_buttons():
    from app.bot.keyboards import catalog_keyboard
    kb = catalog_keyboard(
        [("e1", "Event 1"), ("e2", "Event 2")],
        page=0, total_pages=1, token="mw-",
    )
    flat = [b for row in kb for b in row]
    payloads = [b["payload"] for b in flat if "payload" in b]
    assert "ev:e1:mw-" in payloads
    assert "ev:e2:mw-" in payloads
    assert "csrch:mw-" in payloads


def test_catalog_keyboard_reset_only_when_non_default():
    from app.bot.keyboards import catalog_keyboard
    kb_default = catalog_keyboard([("e1", "E")], token="---", show_reset=False)
    flat = [b["text"] for row in kb_default for b in row]
    assert not any("Сбросить" in t for t in flat)
    kb_filtered = catalog_keyboard([("e1", "E")], token="mw-", show_reset=True)
    flat = [b["text"] for row in kb_filtered for b in row]
    assert any("Сбросить" in t for t in flat)


def test_category_picker_marks_current_value():
    from app.bot.keyboards import category_picker_keyboard
    kb = category_picker_keyboard(page=0, token="m--", current_category_char="m")
    flat = [b["text"] for row in kb for b in row]
    assert any("✅ Мастер-класс" in t for t in flat)
    assert not any("✅ День открытых дверей" in t for t in flat)


def test_picker_option_applies_only_its_dimension():
    """Тап по «Сегодня» меняет date-чар, оставляет cat/format нетронутыми."""
    from app.bot.keyboards import date_picker_keyboard
    kb = date_picker_keyboard(page=2, token="mwh", current_date_char="w")
    payloads = [b["payload"] for row in kb for b in row if "payload" in b]
    assert "m:cat:0:mth" in payloads
    assert "m:cat:0:m-h" in payloads


def test_search_prompt_keyboard_back_to_catalog():
    from app.bot.keyboards import search_prompt_keyboard
    kb = search_prompt_keyboard("mw-")
    payloads = [b["payload"] for row in kb for b in row if "payload" in b]
    assert payloads == ["m:cat:0:mw-"]
