from datetime import UTC, datetime, timedelta

from app.models.event import Event, EventFormat, LateCancellationPolicy


async def test_event_format_default_offline(db):
    e = Event(title="X", starts_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=60)
    db.add(e)
    await db.flush()
    assert e.format == EventFormat.OFFLINE
    assert e.online_url is None
    assert e.late_cancellation_policy == LateCancellationPolicy.FORBID
    assert e.slots_enabled is False


async def test_event_online_with_url(db):
    e = Event(
        title="Online lecture",
        starts_at=datetime.now(UTC) + timedelta(days=1),
        duration_minutes=60,
        format=EventFormat.ONLINE,
        online_url="https://max.ru/call/abc",
        late_cancellation_policy=LateCancellationPolicy.ALLOW_WITH_MARK,
        slots_enabled=True,
    )
    db.add(e)
    await db.flush()
    assert e.format == EventFormat.ONLINE
    assert e.online_url == "https://max.ru/call/abc"
    assert e.late_cancellation_policy == LateCancellationPolicy.ALLOW_WITH_MARK
    assert e.slots_enabled is True
