from datetime import UTC, datetime, timedelta

from app.models.event import Event
from app.models.registration import Registration, RegistrationStatus
from app.models.user import User
from app.services.slot import SlotService


async def test_list_slots_for_event(db):
    e = Event(title="X", starts_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=60, slots_enabled=True)
    db.add(e); await db.flush()

    svc = SlotService(db)
    await svc.replace_all(e.id, [
        {"starts_at": datetime.now(UTC) + timedelta(days=1, hours=2), "duration_minutes": 30, "label": "Утро"},
        {"starts_at": datetime.now(UTC) + timedelta(days=1, hours=4), "duration_minutes": 30, "label": "День"},
    ])
    slots = await svc.list_for_event(e.id)
    assert len(slots) == 2
    assert {s.label for s in slots} == {"Утро", "День"}


async def test_remaining_seats_per_slot(db):
    e = Event(title="X", starts_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=60, slots_enabled=True)
    u1 = User(max_user_id=77001); u2 = User(max_user_id=77002)
    db.add_all([e, u1, u2]); await db.flush()

    svc = SlotService(db)
    [slot] = await svc.replace_all(e.id, [
        {"starts_at": datetime.now(UTC) + timedelta(days=1, hours=2), "duration_minutes": 30, "capacity": 5},
    ])
    db.add(Registration(
        user_id=u1.id, event_id=e.id, slot_id=slot.id,
        status=RegistrationStatus.CONFIRMED, answers={}, short_code="AAA-1111",
    ))
    await db.flush()
    remaining = await svc.remaining_seats(slot.id)
    assert remaining == 4


async def test_remaining_seats_unlimited_slot(db):
    e = Event(title="X", starts_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=60, slots_enabled=True)
    db.add(e); await db.flush()
    svc = SlotService(db)
    [slot] = await svc.replace_all(e.id, [
        {"starts_at": datetime.now(UTC) + timedelta(days=1, hours=2), "duration_minutes": 30, "capacity": None},
    ])
    assert await svc.remaining_seats(slot.id) is None


async def test_replace_all_removes_old_slots(db):
    e = Event(title="X", starts_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=60, slots_enabled=True)
    db.add(e); await db.flush()
    svc = SlotService(db)
    await svc.replace_all(e.id, [
        {"starts_at": datetime.now(UTC) + timedelta(days=1, hours=2), "duration_minutes": 30, "label": "A"},
        {"starts_at": datetime.now(UTC) + timedelta(days=1, hours=4), "duration_minutes": 30, "label": "B"},
    ])
    assert len(await svc.list_for_event(e.id)) == 2
    # Replace with single
    await svc.replace_all(e.id, [
        {"starts_at": datetime.now(UTC) + timedelta(days=1, hours=6), "duration_minutes": 30, "label": "C"},
    ])
    slots = await svc.list_for_event(e.id)
    assert len(slots) == 1
    assert slots[0].label == "C"
