from datetime import UTC, datetime, timedelta

import pytest

from app.models.registration import RegistrationStatus
from app.services.capacity import CapacityService, RegistrationClosed
from tests.factories import EventFactory, RegistrationFactory, UserFactory


async def test_unlimited_capacity_always_admits(db):
    event = EventFactory(capacity=None)
    db.add(event)
    await db.flush()
    svc = CapacityService(db)
    decision = await svc.decide(event.id)
    assert decision == RegistrationStatus.CONFIRMED


async def test_full_capacity_with_waitlist_returns_waitlist(db):
    event = EventFactory(capacity=2, waitlist_enabled=True)
    u1 = UserFactory(); u2 = UserFactory()
    db.add_all([event, u1, u2])
    await db.flush()
    db.add(RegistrationFactory(user_id=u1.id, event_id=event.id, status=RegistrationStatus.CONFIRMED))
    db.add(RegistrationFactory(user_id=u2.id, event_id=event.id, status=RegistrationStatus.CONFIRMED))
    await db.flush()

    svc = CapacityService(db)
    decision = await svc.decide(event.id)
    assert decision == RegistrationStatus.WAITLIST


async def test_full_no_waitlist_raises(db):
    event = EventFactory(capacity=1, waitlist_enabled=False)
    u1 = UserFactory()
    db.add_all([event, u1])
    await db.flush()
    db.add(RegistrationFactory(user_id=u1.id, event_id=event.id, status=RegistrationStatus.CONFIRMED))
    await db.flush()

    svc = CapacityService(db)
    with pytest.raises(RegistrationClosed):
        await svc.decide(event.id)


async def test_window_closed_raises(db):
    event = EventFactory(
        capacity=10,
        registration_closes_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db.add(event)
    await db.flush()
    svc = CapacityService(db)
    with pytest.raises(RegistrationClosed):
        await svc.decide(event.id)
