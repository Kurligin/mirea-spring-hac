from datetime import UTC, datetime, timedelta

from app.bot.catalog_filter import CatalogFilter
from app.bot.dispatcher import dispatch
from app.bot.handlers.catalog import _count_filtered, _filtered_events
from app.models.event import Event, EventFormat, EventStatus, EventType, LateCancellationPolicy
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User
from tests.fixtures.bot_helpers import answer_texts, callback_update, make_ctx


def _event(title: str, status: EventStatus = EventStatus.PUBLISHED, days: int = 5) -> Event:
    return Event(
        title=title, event_type=EventType.OPEN_DAY, status=status,
        starts_at=datetime.now(UTC) + timedelta(days=days), duration_minutes=90,
        location="ауд. 101", capacity=30,
    )


async def test_catalog_lists_only_published_future(db):
    published = _event("День открытых дверей")
    draft = _event("Черновик", status=EventStatus.DRAFT)
    past = _event("Прошедшее", days=-3)
    db.add_all([published, draft, past])
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(820001, "m:cat"), ctx)
    body = mock.state.mock["answers"][-1]["body"]["message"]
    buttons = body["attachments"][0]["payload"]["buttons"]
    labels = [b["text"] for row in buttons for b in row]
    assert "День открытых дверей" in labels
    assert "Черновик" not in labels
    assert "Прошедшее" not in labels


async def test_event_card_not_registered_shows_signup(db):
    event = _event("Мастер-класс")
    db.add(event)
    await db.flush()
    ctx, mock = make_ctx(db)
    await dispatch(callback_update(820002, f"ev:{event.id}"), ctx)
    buttons = mock.state.mock["answers"][-1]["body"]["message"]["attachments"][0]["payload"]["buttons"]
    payloads = [b.get("payload") for row in buttons for b in row]
    assert f"rg:{event.id}" in payloads


async def test_event_card_confirmed_shows_cancel(db):
    user = User(max_user_id=820003)
    event = _event("Олимпиада")
    db.add_all([user, event])
    await db.flush()
    reg = Registration(
        user_id=user.id, event_id=event.id, status=RegistrationStatus.CONFIRMED,
        answers={}, short_code="ABC-1234",
    )
    db.add(reg)
    await db.flush()

    ctx, mock = make_ctx(db)
    await dispatch(callback_update(820003, f"ev:{event.id}"), ctx)
    buttons = mock.state.mock["answers"][-1]["body"]["message"]["attachments"][0]["payload"]["buttons"]
    payloads = [b.get("payload") for row in buttons for b in row]
    assert f"cn:{reg.id}" in payloads


async def test_help_callback_returns_help_text(db):
    ctx, mock = make_ctx(db)
    await dispatch(callback_update(820004, "m:help"), ctx)
    assert any("Помощь" in t for t in answer_texts(mock))


async def test_menu_home_callback(db):
    ctx, mock = make_ctx(db)
    await dispatch(callback_update(820005, "m:home"), ctx)
    assert any("меню" in t.lower() for t in answer_texts(mock))


async def test_catalog_paginates_when_many_events(db):
    for i in range(12):
        db.add(_event(f"Пагинация {i:02d}", days=3 + i))
    await db.flush()
    ctx, mock = make_ctx(db)
    await dispatch(callback_update(820010, "m:cat"), ctx)
    msg = mock.state.mock["answers"][-1]["body"]["message"]
    buttons = msg["attachments"][0]["payload"]["buttons"]
    event_btns = [b for row in buttons for b in row if (b.get("payload") or "").startswith("ev:")]
    assert len(event_btns) <= 10
    payloads = [b.get("payload") for row in buttons for b in row]
    assert any(p and p.startswith("m:cat:") for p in payloads)
    assert "стр." in msg["text"]


async def test_catalog_second_page_has_back_nav(db):
    for i in range(12):
        db.add(_event(f"Стр2 {i:02d}", days=3 + i))
    await db.flush()
    ctx, mock = make_ctx(db)
    await dispatch(callback_update(820011, "m:cat:1"), ctx)
    buttons = mock.state.mock["answers"][-1]["body"]["message"]["attachments"][0]["payload"]["buttons"]
    payloads = [b.get("payload") for row in buttons for b in row]
    assert "m:cat:0" in payloads


def test_event_card_text_includes_format_and_cancellation_policy():
    """_event_card_text показывает формат, лейбл мест и условия отмены."""
    from app.bot.handlers.catalog import _event_card_text

    event = Event(
        title="День открытых дверей",
        description=None,
        event_type=EventType.OPEN_DAY,
        format=EventFormat.OFFLINE,
        status=EventStatus.PUBLISHED,
        late_cancellation_policy=LateCancellationPolicy.FORBID,
        starts_at=datetime(2026, 5, 22, 14, 0, tzinfo=UTC),
        duration_minutes=60,
        location=None,
    )
    text = _event_card_text(event, None, seats_label="🟢 свободно мест: 5")
    assert "🖥 Очно" in text
    assert "Отмена возможна только до начала" in text
    assert "🟢 свободно мест: 5" in text


def test_msk_end_of_today_returns_end_of_msk_day_in_utc():
    from datetime import datetime, UTC, timedelta, timezone
    from app.bot.handlers.catalog import _msk_end_of_today

    msk = timezone(timedelta(hours=3))
    now_msk_morning = datetime(2026, 5, 18, 10, 0, 0, tzinfo=msk)
    end = _msk_end_of_today(now=now_msk_morning.astimezone(UTC))
    end_msk = end.astimezone(msk)
    assert end_msk.year == 2026 and end_msk.month == 5 and end_msk.day == 18
    assert end_msk.hour == 23 and end_msk.minute == 59


def test_msk_end_of_today_handles_utc_around_midnight_msk():
    """В 22:30 UTC уже 01:30 MSK следующего дня → end_of_today указывает на этот следующий день."""
    from datetime import datetime, UTC
    from app.bot.handlers.catalog import _msk_end_of_today

    now_utc = datetime(2026, 5, 17, 22, 30, 0, tzinfo=UTC)  # это 18 мая 01:30 МСК
    end = _msk_end_of_today(now=now_utc)
    assert end.day == 18 and end.month == 5


# ---------------------------------------------------------------------------
# Task 3: _filtered_events / _count_filtered
# ---------------------------------------------------------------------------

class _FakeCtx:
    def __init__(self, db):
        self.db = db


async def test_filtered_events_filters_by_category(db):
    mc = Event(
        title="Мастер-класс фильтр",
        event_type=EventType.MASTER_CLASS,
        format=EventFormat.OFFLINE,
        status=EventStatus.PUBLISHED,
        late_cancellation_policy=LateCancellationPolicy.FORBID,
        starts_at=datetime.now(UTC) + timedelta(days=3),
        duration_minutes=60,
    )
    od = Event(
        title="День открытых дверей фильтр",
        event_type=EventType.OPEN_DAY,
        format=EventFormat.OFFLINE,
        status=EventStatus.PUBLISHED,
        late_cancellation_policy=LateCancellationPolicy.FORBID,
        starts_at=datetime.now(UTC) + timedelta(days=4),
        duration_minutes=90,
    )
    db.add_all([mc, od])
    await db.flush()

    ctx = _FakeCtx(db)
    result = await _filtered_events(ctx, CatalogFilter(category=EventType.MASTER_CLASS), limit=100)
    titles = [e.title for e in result]
    assert "Мастер-класс фильтр" in titles
    assert "День открытых дверей фильтр" not in titles


async def test_filtered_events_filters_by_date_week(db):
    near = Event(
        title="Ближайшее фильтр",
        event_type=EventType.OTHER,
        format=EventFormat.ONLINE,
        status=EventStatus.PUBLISHED,
        late_cancellation_policy=LateCancellationPolicy.FORBID,
        starts_at=datetime.now(UTC) + timedelta(days=3),
        duration_minutes=60,
    )
    far = Event(
        title="Далёкое фильтр",
        event_type=EventType.OTHER,
        format=EventFormat.ONLINE,
        status=EventStatus.PUBLISHED,
        late_cancellation_policy=LateCancellationPolicy.FORBID,
        starts_at=datetime.now(UTC) + timedelta(days=14),
        duration_minutes=60,
    )
    db.add_all([near, far])
    await db.flush()

    ctx = _FakeCtx(db)
    result = await _filtered_events(ctx, CatalogFilter(date="week"), limit=100)
    titles = [e.title for e in result]
    assert "Ближайшее фильтр" in titles
    assert "Далёкое фильтр" not in titles


async def test_count_filtered_matches_query(db):
    for i in range(5):
        db.add(Event(
            title=f"Событие счёт {i}",
            event_type=EventType.CONSULTATION,
            format=EventFormat.HYBRID,
            status=EventStatus.PUBLISHED,
            late_cancellation_policy=LateCancellationPolicy.FORBID,
            starts_at=datetime.now(UTC) + timedelta(days=5 + i),
            duration_minutes=45,
        ))
    await db.flush()

    ctx = _FakeCtx(db)
    filt = CatalogFilter()
    total = await _count_filtered(ctx, filt)
    events = await _filtered_events(ctx, filt, limit=100)
    assert total == len(events)


async def test_search_finds_by_title_case_insensitive(db):
    from datetime import datetime, UTC, timedelta
    from app.bot.handlers.catalog import _search_events
    from app.models.event import Event, EventFormat, EventStatus, EventType, LateCancellationPolicy

    future = datetime.now(UTC) + timedelta(days=2)
    db.add(Event(title="Мастер-класс: Нейросети", event_type=EventType.MASTER_CLASS,
                 format=EventFormat.OFFLINE, status=EventStatus.PUBLISHED,
                 late_cancellation_policy=LateCancellationPolicy.FORBID,
                 starts_at=future, duration_minutes=60))
    db.add(Event(title="День открытых дверей", event_type=EventType.OPEN_DAY,
                 format=EventFormat.OFFLINE, status=EventStatus.PUBLISHED,
                 late_cancellation_policy=LateCancellationPolicy.FORBID,
                 starts_at=future + timedelta(hours=1), duration_minutes=60))
    await db.commit()
    ctx = _FakeCtx(db)
    found = await _search_events(ctx, "нейро")
    assert len(found) == 1 and "Нейросети" in found[0].title


async def test_search_returns_empty_on_no_match(db):
    from app.bot.handlers.catalog import _search_events
    ctx = _FakeCtx(db)
    assert await _search_events(ctx, "xyzxyz") == []


async def test_search_treats_percent_as_literal(db):
    """% в запросе не должен матчить всё."""
    from datetime import datetime, UTC, timedelta
    from app.bot.handlers.catalog import _search_events
    from app.models.event import Event, EventFormat, EventStatus, EventType, LateCancellationPolicy

    future = datetime.now(UTC) + timedelta(days=2)
    db.add(Event(title="Тестовое название", event_type=EventType.OTHER, format=EventFormat.OFFLINE,
                 status=EventStatus.PUBLISHED, late_cancellation_policy=LateCancellationPolicy.FORBID,
                 starts_at=future, duration_minutes=60))
    await db.commit()
    ctx = _FakeCtx(db)
    assert await _search_events(ctx, "%") == []
