import re
from datetime import UTC, datetime, timedelta

import pytest

from app.models.registration import RegistrationStatus
from app.services.registration import RegistrationService
from tests.factories import EventFactory, EventFieldFactory, UserFactory


async def test_register_creates_confirmed_when_seats_available(db):
    event = EventFactory(capacity=10, waitlist_enabled=True)
    user = UserFactory()
    db.add_all([event, user])
    await db.flush()
    fld = EventFieldFactory(event_id=event.id, key="name", required=True)
    db.add(fld)
    await db.flush()

    svc = RegistrationService(db)
    reg = await svc.register(user_id=user.id, event_id=event.id, answers={"name": "Иван"})
    assert reg.status == RegistrationStatus.CONFIRMED


async def test_register_creates_waitlist_when_full(db):
    event = EventFactory(capacity=1, waitlist_enabled=True)
    u1 = UserFactory(); u2 = UserFactory()
    db.add_all([event, u1, u2])
    await db.flush()
    fld = EventFieldFactory(event_id=event.id, key="name", required=True)
    db.add(fld)
    await db.flush()

    svc = RegistrationService(db)
    await svc.register(user_id=u1.id, event_id=event.id, answers={"name": "A"})
    reg2 = await svc.register(user_id=u2.id, event_id=event.id, answers={"name": "B"})
    assert reg2.status == RegistrationStatus.WAITLIST
    assert reg2.waitlist_position is not None


async def test_double_registration_returns_existing(db):
    event = EventFactory(capacity=10)
    user = UserFactory()
    db.add_all([event, user])
    await db.flush()
    fld = EventFieldFactory(event_id=event.id, key="name", required=True)
    db.add(fld)
    await db.flush()

    svc = RegistrationService(db)
    reg1 = await svc.register(user_id=user.id, event_id=event.id, answers={"name": "X"})
    reg2 = await svc.register(user_id=user.id, event_id=event.id, answers={"name": "Y"})
    assert reg1.id == reg2.id


async def test_cancel_promotes_waitlist(db):
    event = EventFactory(capacity=1, waitlist_enabled=True)
    u1 = UserFactory(); u2 = UserFactory()
    db.add_all([event, u1, u2])
    await db.flush()
    fld = EventFieldFactory(event_id=event.id, key="name", required=True)
    db.add(fld)
    await db.flush()

    svc = RegistrationService(db)
    confirmed = await svc.register(user_id=u1.id, event_id=event.id, answers={"name": "A"})
    waitlisted = await svc.register(user_id=u2.id, event_id=event.id, answers={"name": "B"})
    assert waitlisted.status == RegistrationStatus.WAITLIST

    await svc.cancel(confirmed.id)
    await db.refresh(waitlisted)
    assert waitlisted.status == RegistrationStatus.CONFIRMED


# === Plan 5a additions: slot_id, short_code, late cancellation ===

from app.models.event_slot import EventSlot


async def test_register_assigns_short_code(db):
    event = EventFactory(capacity=10)
    user = UserFactory()
    db.add_all([event, user])
    await db.flush()
    fld = EventFieldFactory(event_id=event.id, key="name", required=False)
    db.add(fld)
    await db.flush()

    svc = RegistrationService(db)
    reg = await svc.register(user_id=user.id, event_id=event.id, answers={})
    assert reg.short_code is not None
    assert re.fullmatch(r"[A-HJ-NP-Z]{3}-\d{4}", reg.short_code)


async def test_register_with_slot_id(db):
    event = EventFactory(slots_enabled=True, capacity=10)
    user = UserFactory()
    db.add_all([event, user])
    await db.flush()
    slot = EventSlot(
        event_id=event.id,
        starts_at=datetime.now(UTC) + timedelta(days=1),
        duration_minutes=30,
        capacity=5,
    )
    db.add(slot)
    await db.flush()

    svc = RegistrationService(db)
    reg = await svc.register(user_id=user.id, event_id=event.id, answers={}, slot_id=slot.id)
    assert reg.slot_id == slot.id
    assert reg.status == RegistrationStatus.CONFIRMED


async def test_register_slots_enabled_requires_slot_id(db):
    from app.services.capacity import RegistrationClosed

    event = EventFactory(slots_enabled=True, capacity=10)
    user = UserFactory()
    db.add_all([event, user])
    await db.flush()

    svc = RegistrationService(db)
    with pytest.raises(RegistrationClosed):
        await svc.register(user_id=user.id, event_id=event.id, answers={})


async def test_cancel_late_with_forbid_raises(db):
    from app.models.event import LateCancellationPolicy

    event = EventFactory(
        starts_at=datetime.now(UTC) - timedelta(hours=1),
        late_cancellation_policy=LateCancellationPolicy.FORBID,
        capacity=10,
    )
    user = UserFactory()
    db.add_all([event, user])
    await db.flush()

    svc = RegistrationService(db)
    reg = await svc.register(user_id=user.id, event_id=event.id, answers={})
    with pytest.raises(ValueError, match="запрещена"):
        await svc.cancel(reg.id)


async def test_cancel_late_with_allow_with_mark_marks_late(db):
    from app.models.event import LateCancellationPolicy

    event = EventFactory(
        starts_at=datetime.now(UTC) - timedelta(hours=1),
        late_cancellation_policy=LateCancellationPolicy.ALLOW_WITH_MARK,
        capacity=10,
    )
    user = UserFactory()
    db.add_all([event, user])
    await db.flush()

    svc = RegistrationService(db)
    reg = await svc.register(user_id=user.id, event_id=event.id, answers={})
    cancelled = await svc.cancel(reg.id)
    assert cancelled.is_late_cancellation is True
    assert cancelled.status == RegistrationStatus.CANCELLED
