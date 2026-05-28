from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.event import Event
from app.models.event_slot import EventSlot
from app.models.registration import Registration
from app.models.user import User


async def test_registration_with_slot_and_short_code(db):
    e = Event(title="X", starts_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=60, slots_enabled=True)
    u = User(max_user_id=88001)
    db.add_all([e, u]); await db.flush()
    slot = EventSlot(event_id=e.id, starts_at=datetime.now(UTC) + timedelta(days=1, hours=2), duration_minutes=30)
    db.add(slot); await db.flush()

    reg = Registration(user_id=u.id, event_id=e.id, slot_id=slot.id, short_code="ABC-1234", answers={})
    db.add(reg)
    await db.flush()
    assert reg.slot_id == slot.id
    assert reg.short_code == "ABC-1234"
    assert reg.notifications_muted is False
    assert reg.is_late_cancellation is False


async def test_short_code_unique(db):
    e = Event(title="X", starts_at=datetime.now(UTC) + timedelta(days=1), duration_minutes=60)
    u1 = User(max_user_id=88002); u2 = User(max_user_id=88003)
    db.add_all([e, u1, u2]); await db.flush()

    db.add(Registration(user_id=u1.id, event_id=e.id, short_code="DUPLICATE", answers={}))
    await db.flush()
    db.add(Registration(user_id=u2.id, event_id=e.id, short_code="DUPLICATE", answers={}))
    with pytest.raises(IntegrityError):
        await db.flush()
