from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.bot.dispatcher import dispatch
from app.models.event import Event, EventStatus, EventType, LateCancellationPolicy
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User
from tests.fixtures.bot_helpers import answer_texts, callback_update, make_ctx


def _event(title="Событие", days=5, **kw) -> Event:
    base = dict(
        title=title, event_type=EventType.OPEN_DAY, status=EventStatus.PUBLISHED,
        starts_at=datetime.now(UTC) + timedelta(days=days), duration_minutes=60, capacity=30,
    )
    base.update(kw)
    return Event(**base)


async def test_my_registrations_empty(db):
    user = User(max_user_id=840001)
    db.add(user)
    await db.flush()
    ctx, mock = make_ctx(db)
    await dispatch(callback_update(840001, "m:my"), ctx)
    assert any("нет записей" in t.lower() for t in answer_texts(mock))


async def test_my_registrations_lists_event_title(db):
    """m:my → в тексте нет кода, но название мероприятия присутствует в кнопке."""
    user = User(max_user_id=840002)
    event = _event("День открытых дверей")
    db.add_all([user, event])
    await db.flush()
    db.add(Registration(
        user_id=user.id, event_id=event.id, status=RegistrationStatus.CONFIRMED,
        answers={}, short_code="QWE-7777",
    ))
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(840002, "m:my"), ctx)
    buttons = mock.state.mock["answers"][-1]["body"]["message"]["attachments"][0]["payload"]["buttons"]
    labels = [b.get("text") for row in buttons for b in row]
    assert any("День открытых дверей" in lbl for lbl in labels)


async def test_cancel_asks_confirmation(db):
    user = User(max_user_id=840003)
    event = _event()
    db.add_all([user, event])
    await db.flush()
    reg = Registration(
        user_id=user.id, event_id=event.id, status=RegistrationStatus.CONFIRMED,
        answers={}, short_code="AAA-1111",
    )
    db.add(reg)
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(840003, f"cn:{reg.id}"), ctx)
    buttons = mock.state.mock["answers"][-1]["body"]["message"]["attachments"][0]["payload"]["buttons"]
    payloads = [b.get("payload") for row in buttons for b in row]
    assert f"cy:{reg.id}" in payloads


async def test_cancel_confirmed_cancels_registration(db):
    user = User(max_user_id=840004)
    event = _event()
    db.add_all([user, event])
    await db.flush()
    reg = Registration(
        user_id=user.id, event_id=event.id, status=RegistrationStatus.CONFIRMED,
        answers={}, short_code="BBB-2222",
    )
    db.add(reg)
    await db.flush()

    ctx, _ = make_ctx(db)
    await dispatch(callback_update(840004, f"cy:{reg.id}"), ctx)
    refreshed = (await db.execute(
        select(Registration).where(Registration.id == reg.id)
    )).scalar_one()
    assert refreshed.status == RegistrationStatus.CANCELLED


async def test_cancel_late_forbidden_shows_message(db):
    user = User(max_user_id=840005)
    event = _event(days=-1, late_cancellation_policy=LateCancellationPolicy.FORBID)
    db.add_all([user, event])
    await db.flush()
    reg = Registration(
        user_id=user.id, event_id=event.id, status=RegistrationStatus.CONFIRMED,
        answers={}, short_code="CCC-3333",
    )
    db.add(reg)
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(840005, f"cy:{reg.id}"), ctx)
    refreshed = (await db.execute(
        select(Registration).where(Registration.id == reg.id)
    )).scalar_one()
    assert refreshed.status == RegistrationStatus.CONFIRMED
    assert any("позд" in t.lower() for t in answer_texts(mock))


async def test_my_registrations_shows_title_buttons(db):
    """m:my → список кнопок-названий (не «❌ Отменить»)."""
    user = User(max_user_id=840006)
    event = _event("Мастер-класс по Go")
    db.add_all([user, event])
    await db.flush()
    db.add(Registration(
        user_id=user.id, event_id=event.id, status=RegistrationStatus.CONFIRMED,
        answers={}, short_code="DDD-4444",
    ))
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(840006, "m:my"), ctx)
    buttons = mock.state.mock["answers"][-1]["body"]["message"]["attachments"][0]["payload"]["buttons"]
    labels = [b.get("text") for row in buttons for b in row]
    payloads = [b.get("payload") for row in buttons for b in row]
    # Кнопка называется названием мероприятия, а не «❌ Отменить: ...»
    assert any("Мастер-класс по Go" in lbl for lbl in labels)
    assert not any(lbl and lbl.startswith("❌ Отменить") for lbl in labels)
    # payload ведёт на экран rgd:<reg_id>
    assert any(p and p.startswith("rgd:") for p in payloads)


async def test_rgd_shows_registration_detail_with_qr_for_confirmed(db):
    """rgd → экран записи: содержит формат, код, кнопки «Показать QR», «Уведомления», «Отменить»."""
    user = User(max_user_id=840007)
    event = _event(
        "День открытых дверей ИТ",
        late_cancellation_policy=LateCancellationPolicy.FORBID,
    )
    db.add_all([user, event])
    await db.flush()
    reg = Registration(
        user_id=user.id, event_id=event.id, status=RegistrationStatus.CONFIRMED,
        answers={}, short_code="EEE-5555",
    )
    db.add(reg)
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(840007, f"rgd:{reg.id}"), ctx)

    text = answer_texts(mock)[-1]
    assert "День открытых дверей ИТ" in text
    assert "🖥 Очно" in text
    assert "EEE-5555" in text

    buttons = mock.state.mock["answers"][-1]["body"]["message"]["attachments"][0]["payload"]["buttons"]
    payloads = [b.get("payload") for row in buttons for b in row]
    assert f"qr:{reg.id}" in payloads
    assert f"mut:{reg.id}" in payloads
    # Запись в будущем, политика forbid — кнопка отмены есть (мероприятие ещё не началось)
    assert f"cn:{reg.id}" in payloads
    # Кнопка «Назад» ведёт обратно в список записей
    assert "m:my" in payloads


async def test_mut_toggles_notifications_muted(db):
    """mut переключает notifications_muted на записи и перерисовывает экран."""
    user = User(max_user_id=840008)
    event = _event("Вебинар по Python")
    db.add_all([user, event])
    await db.flush()
    reg = Registration(
        user_id=user.id, event_id=event.id, status=RegistrationStatus.CONFIRMED,
        answers={}, short_code="FFF-6666", notifications_muted=False,
    )
    db.add(reg)
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(840008, f"mut:{reg.id}"), ctx)

    # Проверяем, что notifications_muted переключён на True
    refreshed = (await db.execute(
        select(Registration).where(Registration.id == reg.id)
    )).scalar_one()
    assert refreshed.notifications_muted is True

    # Проверяем toast-сообщение
    texts = answer_texts(mock)
    assert any("Уведомления отключены" in t for t in texts)
