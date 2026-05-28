from datetime import UTC, datetime, timedelta

from app.models.event import Event
from app.models.event_slot import EventSlot


async def test_event_slot_persisted(db):
    e = Event(title="Y", starts_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=60, slots_enabled=True)
    db.add(e)
    await db.flush()
    slot = EventSlot(
        event_id=e.id,
        starts_at=datetime.now(UTC) + timedelta(days=1, hours=2),
        duration_minutes=30,
        capacity=20,
        label="Утро",
    )
    db.add(slot)
    await db.flush()
    assert slot.id is not None
    assert slot.label == "Утро"
    assert slot.capacity == 20


async def test_event_slot_cascade_delete(db):
    e = Event(title="Y", starts_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=60, slots_enabled=True)
    db.add(e); await db.flush()
    slot = EventSlot(event_id=e.id, starts_at=datetime.now(UTC) + timedelta(days=1, hours=1), duration_minutes=30)
    db.add(slot); await db.flush()
    slot_id = slot.id

    await db.delete(e)
    await db.flush()

    from sqlalchemy import select
    found = (await db.execute(select(EventSlot).where(EventSlot.id == slot_id))).scalar_one_or_none()
    assert found is None
