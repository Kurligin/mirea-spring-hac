from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.bot.dispatcher import dispatch
from app.models.bot_dialog import BotDialog, DialogState
from app.models.consent_log import ConsentKind, ConsentLog
from app.models.event import Event, EventStatus, EventType
from app.models.event_field import EventField, FieldType
from app.models.event_slot import EventSlot
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User
from app.services.consent import ConsentService
from tests.fixtures.bot_helpers import answer_texts, callback_update, make_ctx, sent_texts


def _event(**kw) -> Event:
    base = dict(
        title="Тест-событие", event_type=EventType.OPEN_DAY, status=EventStatus.PUBLISHED,
        starts_at=datetime.now(UTC) + timedelta(days=5), duration_minutes=90, capacity=30,
    )
    base.update(kw)
    return Event(**base)


async def _accept_terms(db, user: User) -> None:
    await ConsentService(db).record(
        user_id=user.id, kind=ConsentKind.TERMS, doc_version=ConsentService.CURRENT_TERMS_VERSION
    )
    await db.flush()


async def test_rg_without_terms_prompts_onboarding(db):
    event = _event()
    db.add(event)
    await db.flush()
    ctx, mock = make_ctx(db)
    await dispatch(callback_update(830001, f"rg:{event.id}"), ctx)
    assert any("примите условия" in t.lower() for t in answer_texts(mock) + sent_texts(mock))


async def test_rg_with_phone_field_requires_phone_consent(db):
    user = User(max_user_id=830002)
    event = _event()
    db.add_all([user, event])
    await db.flush()
    await _accept_terms(db, user)
    db.add(EventField(
        event_id=event.id, order=0, key="phone", label="Телефон",
        field_type=FieldType.PHONE, required=True,
    ))
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(830002, f"rg:{event.id}"), ctx)
    texts_all = answer_texts(mock) + sent_texts(mock)
    assert any("телефон" in t.lower() for t in texts_all)


async def test_ph_callback_records_phone_consent(db):
    user = User(max_user_id=830003)
    event = _event()
    db.add_all([user, event])
    await db.flush()
    await _accept_terms(db, user)
    db.add(EventField(
        event_id=event.id, order=0, key="phone", label="Телефон",
        field_type=FieldType.PHONE, required=True,
    ))
    await db.flush()

    ctx, _ = make_ctx(db)
    await dispatch(callback_update(830003, f"ph:{event.id}"), ctx)
    logs = (await db.execute(
        select(ConsentLog).where(ConsentLog.user_id == user.id, ConsentLog.doc_kind == ConsentKind.PHONE)
    )).scalars().all()
    assert len(logs) >= 1


async def test_rg_with_slots_shows_slot_picker(db):
    user = User(max_user_id=830004)
    event = _event(slots_enabled=True)
    db.add_all([user, event])
    await db.flush()
    await _accept_terms(db, user)
    db.add(EventSlot(
        event_id=event.id, starts_at=datetime.now(UTC) + timedelta(days=5),
        duration_minutes=30, capacity=10, label="10:00",
    ))
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(830004, f"rg:{event.id}"), ctx)
    buttons_msgs = [
        m for m in mock.state.mock["answers"]
        if m["body"].get("message", {}).get("attachments")
    ]
    assert buttons_msgs or mock.state.mock["sent_messages"]
    payloads = []
    for m in mock.state.mock["sent_messages"]:
        for att in m["body"].get("attachments", []):
            for row in att.get("payload", {}).get("buttons", []):
                for b in row:
                    payloads.append(b.get("payload"))
    assert any(p and p.startswith("sl:") for p in payloads)


async def test_sl_callback_sets_slot_and_asks_first_field(db):
    user = User(max_user_id=830005)
    event = _event(slots_enabled=True)
    db.add_all([user, event])
    await db.flush()
    await _accept_terms(db, user)
    slot = EventSlot(
        event_id=event.id, starts_at=datetime.now(UTC) + timedelta(days=5),
        duration_minutes=30, capacity=10, label="10:00",
    )
    db.add(slot)
    db.add(EventField(
        event_id=event.id, order=0, key="full_name", label="ФИО",
        field_type=FieldType.TEXT, required=True,
    ))
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(830005, f"rg:{event.id}"), ctx)
    await dispatch(callback_update(830005, f"sl:{slot.id}"), ctx)

    dialog = (await db.execute(
        select(BotDialog).where(BotDialog.user_id == user.id, BotDialog.event_id == event.id)
    )).scalar_one()
    assert dialog.slot_id == slot.id
    assert dialog.state == DialogState.ASKING_FIELD
    assert any("ФИО" in t for t in answer_texts(mock) + sent_texts(mock))


from tests.fixtures.bot_helpers import message_update  # noqa: E402


async def _event_with_text_field(db, user: User, key="full_name", label="ФИО") -> Event:
    event = _event()
    db.add(event)
    await db.flush()
    await _accept_terms(db, user)
    db.add(EventField(
        event_id=event.id, order=0, key=key, label=label,
        field_type=FieldType.TEXT, required=True,
    ))
    await db.flush()
    return event


async def test_text_field_input_advances_dialog(db):
    user = User(max_user_id=831001)
    db.add(user)
    await db.flush()
    event = await _event_with_text_field(db, user)

    ctx, _ = make_ctx(db)
    await dispatch(callback_update(831001, f"rg:{event.id}"), ctx)
    await dispatch(message_update(831001, "Иванов Иван Иванович"), ctx)

    dialog = (await db.execute(
        select(BotDialog).where(BotDialog.user_id == user.id, BotDialog.event_id == event.id)
    )).scalar_one()
    assert dialog.answers.get("full_name") == "Иванов Иван Иванович"
    assert dialog.state == DialogState.CONFIRMING


async def test_invalid_email_reasks_field(db):
    user = User(max_user_id=831002)
    db.add(user)
    await db.flush()
    event = _event()
    db.add(event)
    await db.flush()
    await _accept_terms(db, user)
    db.add(EventField(
        event_id=event.id, order=0, key="email", label="Почта",
        field_type=FieldType.EMAIL, required=True,
    ))
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(831002, f"rg:{event.id}"), ctx)
    await dispatch(message_update(831002, "не-почта"), ctx)

    dialog = (await db.execute(
        select(BotDialog).where(BotDialog.user_id == user.id)
    )).scalar_one()
    assert dialog.current_field_index == 0
    assert any("email" in t.lower() or "почт" in t.lower() for t in sent_texts(mock))


async def test_select_field_via_callback(db):
    user = User(max_user_id=831003)
    db.add(user)
    await db.flush()
    event = _event()
    db.add(event)
    await db.flush()
    await _accept_terms(db, user)
    db.add(EventField(
        event_id=event.id, order=0, key="faculty", label="Факультет",
        field_type=FieldType.SELECT, required=True,
        options=[{"value": "iit", "label": "ИИТ"}, {"value": "kb", "label": "КБ"}],
    ))
    await db.flush()

    ctx, _ = make_ctx(db)
    await dispatch(callback_update(831003, f"rg:{event.id}"), ctx)
    await dispatch(callback_update(831003, "fv:1"), ctx)

    dialog = (await db.execute(
        select(BotDialog).where(BotDialog.user_id == user.id)
    )).scalar_one()
    assert dialog.answers.get("faculty") == "kb"


async def test_phone_via_contact_attachment(db):
    user = User(max_user_id=831004)
    db.add(user)
    await db.flush()
    event = _event()
    db.add(event)
    await db.flush()
    await _accept_terms(db, user)
    await ConsentService(db).record(
        user_id=user.id, kind=ConsentKind.PHONE, doc_version=ConsentService.CURRENT_PHONE_VERSION
    )
    db.add(EventField(
        event_id=event.id, order=0, key="phone", label="Телефон",
        field_type=FieldType.PHONE, required=True,
    ))
    await db.flush()

    ctx, _ = make_ctx(db)
    await dispatch(callback_update(831004, f"rg:{event.id}"), ctx)
    contact = [{"type": "contact", "payload": {"vcf_info": "BEGIN:VCARD\nTEL:+79991234567\nEND:VCARD"}}]
    await dispatch(message_update(831004, "", attachments=contact), ctx)

    dialog = (await db.execute(
        select(BotDialog).where(BotDialog.user_id == user.id)
    )).scalar_one()
    assert dialog.answers.get("phone") == "+79991234567"


async def test_full_flow_text_field_to_confirmation(db):
    user = User(max_user_id=832001)
    db.add(user)
    await db.flush()
    event = await _event_with_text_field(db, user)

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(832001, f"rg:{event.id}"), ctx)
    await dispatch(message_update(832001, "Петров Пётр"), ctx)
    await dispatch(callback_update(832001, f"ok:{event.id}"), ctx)

    reg = (await db.execute(
        select(Registration).where(
            Registration.user_id == user.id, Registration.event_id == event.id
        )
    )).scalar_one()
    assert reg.status == RegistrationStatus.CONFIRMED
    assert reg.short_code is not None
    assert reg.answers.get("full_name") == "Петров Пётр"
    dialog = (await db.execute(
        select(BotDialog).where(BotDialog.user_id == user.id, BotDialog.event_id == event.id)
    )).scalar_one_or_none()
    assert dialog is None
    all_text = " ".join(sent_texts(mock) + answer_texts(mock))
    assert reg.short_code in all_text


async def test_summary_shown_before_confirm(db):
    user = User(max_user_id=832002)
    db.add(user)
    await db.flush()
    event = await _event_with_text_field(db, user)

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(832002, f"rg:{event.id}"), ctx)
    await dispatch(message_update(832002, "Сидоров Сидор"), ctx)

    dialog = (await db.execute(
        select(BotDialog).where(BotDialog.user_id == user.id)
    )).scalar_one()
    assert dialog.state == DialogState.CONFIRMING
    last = mock.state.mock["sent_messages"][-1]
    buttons = last["body"]["attachments"][0]["payload"]["buttons"]
    payloads = [b.get("payload") for row in buttons for b in row]
    assert f"ok:{event.id}" in payloads
    assert "Сидоров Сидор" in last["body"]["text"]


async def test_confirm_waitlist_when_full(db):
    user = User(max_user_id=832003)
    other = User(max_user_id=832099)
    db.add_all([user, other])
    await db.flush()
    event = _event(capacity=1)
    db.add(event)
    await db.flush()
    await _accept_terms(db, user)
    db.add(EventField(
        event_id=event.id, order=0, key="full_name", label="ФИО",
        field_type=FieldType.TEXT, required=True,
    ))
    await db.flush()
    db.add(Registration(
        user_id=other.id, event_id=event.id, status=RegistrationStatus.CONFIRMED,
        answers={}, short_code="ZZZ-0001",
    ))
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(832003, f"rg:{event.id}"), ctx)
    await dispatch(message_update(832003, "Новиков Новик"), ctx)
    await dispatch(callback_update(832003, f"ok:{event.id}"), ctx)

    reg = (await db.execute(
        select(Registration).where(Registration.user_id == user.id)
    )).scalar_one()
    assert reg.status == RegistrationStatus.WAITLIST
    assert any("ожидани" in t.lower() for t in sent_texts(mock) + answer_texts(mock))


async def test_abort_deletes_dialog(db):
    user = User(max_user_id=832004)
    db.add(user)
    await db.flush()
    event = await _event_with_text_field(db, user)

    ctx, _ = make_ctx(db)
    await dispatch(callback_update(832004, f"rg:{event.id}"), ctx)
    await dispatch(callback_update(832004, "ab"), ctx)

    dialog = (await db.execute(
        select(BotDialog).where(BotDialog.user_id == user.id)
    )).scalar_one_or_none()
    assert dialog is None


async def test_show_summary_includes_format_and_cancel_reminder(db):
    """Сводка перед подтверждением показывает формат и напоминание об отмене (§10.3)."""
    from app.models.event import EventFormat

    user = User(max_user_id=833001)
    db.add(user)
    await db.flush()
    event = _event(format=EventFormat.ONLINE)
    db.add(event)
    await db.flush()
    await _accept_terms(db, user)
    db.add(EventField(
        event_id=event.id, order=0, key="full_name", label="ФИО",
        field_type=FieldType.TEXT, required=True,
    ))
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(833001, f"rg:{event.id}"), ctx)
    await dispatch(message_update(833001, "Тестов Тест"), ctx)

    dialog = (await db.execute(
        select(BotDialog).where(BotDialog.user_id == user.id, BotDialog.event_id == event.id)
    )).scalar_one()
    assert dialog.state == DialogState.CONFIRMING

    all_texts = " ".join(sent_texts(mock) + answer_texts(mock))
    assert "Формат: 💻 Онлайн" in all_texts
    assert "место освободится для других" in all_texts


async def test_phx_callback_skips_phone_and_starts_registration(db):
    """phx-колбэк запускает регистрацию с skip_phone=True, минуя phone-consent."""
    user = User(max_user_id=834001)
    event = _event()
    db.add_all([user, event])
    await db.flush()
    await _accept_terms(db, user)
    db.add(EventField(
        event_id=event.id, order=0, key="phone", label="Телефон",
        field_type=FieldType.PHONE, required=True,
    ))
    db.add(EventField(
        event_id=event.id, order=1, key="note", label="Комментарий",
        field_type=FieldType.TEXT, required=False,
    ))
    await db.flush()

    ctx, mock = make_ctx(db)
    # Сначала пробуем записаться — бот должен запросить phone-consent.
    await dispatch(callback_update(834001, f"rg:{event.id}"), ctx)
    texts_after_rg = sent_texts(mock) + answer_texts(mock)
    assert any("телефон" in t.lower() for t in texts_after_rg)

    # Нажимаем «Без телефона, продолжить».
    await dispatch(callback_update(834001, f"phx:{event.id}"), ctx)

    dialog = (await db.execute(
        select(BotDialog).where(BotDialog.user_id == user.id, BotDialog.event_id == event.id)
    )).scalar_one()
    # Диалог создан, phone-поле (idx=0) пропущено, спрашивается TEXT-поле (idx=1).
    assert dialog.skip_phone is True
    assert dialog.state == DialogState.ASKING_FIELD
    assert dialog.current_field_index == 1
    assert any("Комментарий" in t for t in sent_texts(mock) + answer_texts(mock))
